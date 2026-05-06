"""
throughput.py — Concurrency / throughput load test for Crochetzies chatbot.

Strategy
--------
  Simulate virtual users (VUs), each conducting a short multi-turn
  conversation (3–5 turns). Start at 1 VU, ramp up gradually, and
  detect the breakpoint where:
    • median TTFT  exceeds TTFT_THRESHOLD_S, or
    • median E2E   exceeds E2E_THRESHOLD_S,  or
    • error rate   exceeds ERROR_RATE_MAX.

Output includes:
  - per-level measurements (concurrency → latency + errors)
  - max sustainable concurrency
  - identified breakpoint
  - aggregate throughput (turns / second)

Usage
-----
    python throughput.py                      # default ramp-up
    python throughput.py --max-users 20       # stop ramp at 20 VUs
    python throughput.py --step 2             # increase by 2 VUs each level
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import aiohttp

from utils import (
    create_session,
    delete_session,
    measure_turn,
    TurnTimings,
    TURN_TIMEOUT_SECONDS,
)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

TTFT_THRESHOLD_S  = 8.0  # median TTFT must stay below this
E2E_THRESHOLD_S   = 20.0 # median E2E must stay below this   
   
ERROR_RATE_MAX    = 0.20   # 20 % error rate triggers breakpoint

# ---------------------------------------------------------------------------
# Ramp-up configuration
# ---------------------------------------------------------------------------

CONCURRENCY_LEVELS = [1, 2, 4, 6, 8, 10, 15, 20]  # VUs to test
TURNS_PER_USER     = 4    # turns per virtual user per level
RAMP_PAUSE_S       = 1.0  # pause between concurrency levels (seconds)

# The same conversation script is used for all VUs.
# Turns are chosen to cover simple, RAG, and tool paths.
CONVERSATION_SCRIPT = [
    "Hello, I'm interested in placing an order.",
    "What crochet items do you offer and what are the prices?",
    "I'd like a medium blue bunny. When will it be delivered if I order today?",
    "My name is Test User and my address is 123 Test Street, Lahore.",
]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class LevelResult:
    """Aggregated stats for one concurrency level."""
    concurrency:    int
    total_turns:    int
    failed_turns:   int
    error_rate:     float      # 0.0–1.0

    ttft_median:    float
    ttft_p90:       float
    e2e_median:     float
    e2e_p90:        float

    wall_time_s:    float      # total wall time for this level
    turns_per_sec:  float      # throughput

    threshold_breach: bool     # True if any threshold was exceeded

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ThroughputResult:
    """Overall throughput test result."""
    levels:               list[LevelResult]
    max_concurrency:      int    # highest level without a breach
    breakpoint:           int    # first level that breached (0 = never)
    peak_turns_per_sec:   float
    total_turns:          int
    total_failed:         int

    def to_dict(self) -> dict[str, Any]:
        return {
            "levels":             [lv.to_dict() for lv in self.levels],
            "max_concurrency":    self.max_concurrency,
            "breakpoint":         self.breakpoint,
            "peak_turns_per_sec": round(self.peak_turns_per_sec, 3),
            "total_turns":        self.total_turns,
            "total_failed":       self.total_failed,
        }


# ---------------------------------------------------------------------------
# Virtual user simulation
# ---------------------------------------------------------------------------

async def _run_virtual_user(
    user_id:  int,
    http:     aiohttp.ClientSession,
    results:  list[TurnTimings],
    lock:     asyncio.Lock,
) -> None:
    """
    Simulate one virtual user: create a session, run TURNS_PER_USER turns,
    then clean up. All timings are appended to *results* under *lock*.
    """
    try:
        session_id, _ = await create_session(http)
    except RuntimeError as exc:
        # Count session-creation failure as one failed turn per planned turn
        async with lock:
            for _ in range(TURNS_PER_USER):
                results.append(TurnTimings(
                    ttft=0, inter_token_avg=0, end_to_end=0,
                    token_count=0, ok=False,
                    error=f"session create failed: {exc}",
                ))
        return

    for i, message in enumerate(CONVERSATION_SCRIPT[:TURNS_PER_USER]):
        t = await measure_turn(session_id, message, http)
        async with lock:
            results.append(t)

        # Small yield between turns so the event loop stays healthy
        await asyncio.sleep(0.01)

    await delete_session(http, session_id)


# ---------------------------------------------------------------------------
# Level runner
# ---------------------------------------------------------------------------

async def _run_level(concurrency: int) -> LevelResult:
    """
    Spawn *concurrency* virtual users concurrently, collect timings,
    and compute the level summary.
    """
    timings: list[TurnTimings] = []
    lock = asyncio.Lock()

    print(f"  [level] concurrency={concurrency} ... ", end="", flush=True)
    t_start = time.perf_counter()

    async with aiohttp.ClientSession() as http:
        tasks = [
            asyncio.create_task(
                _run_virtual_user(uid, http, timings, lock)
            )
            for uid in range(concurrency)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    wall_time = time.perf_counter() - t_start

    # ── Aggregate ──────────────────────────────────────────────────────────
    failed  = [t for t in timings if not t.ok]
    success = [t for t in timings if t.ok]

    total_turns  = len(timings)
    failed_turns = len(failed)
    error_rate   = failed_turns / total_turns if total_turns else 1.0

    def _med(vals: list[float]) -> float:
        return round(statistics.median(vals), 4) if vals else 0.0

    def _p90(vals: list[float]) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        idx = int(0.90 * (len(s) - 1))
        return round(s[idx], 4)

    ttft_vals = [t.ttft        for t in success]
    e2e_vals  = [t.end_to_end  for t in success]

    ttft_median = _med(ttft_vals)
    ttft_p90    = _p90(ttft_vals)
    e2e_median  = _med(e2e_vals)
    e2e_p90     = _p90(e2e_vals)

    turns_per_sec = round(total_turns / wall_time, 3) if wall_time > 0 else 0.0

    # ── Threshold check ────────────────────────────────────────────────────
    breach = (
        ttft_median > TTFT_THRESHOLD_S
        or e2e_median > E2E_THRESHOLD_S
        or error_rate > ERROR_RATE_MAX
    )

    reasons = []
    if ttft_median > TTFT_THRESHOLD_S:
        reasons.append(f"TTFT {ttft_median:.2f}s>{TTFT_THRESHOLD_S}s")
    if e2e_median > E2E_THRESHOLD_S:
        reasons.append(f"E2E {e2e_median:.2f}s>{E2E_THRESHOLD_S}s")
    if error_rate > ERROR_RATE_MAX:
        reasons.append(f"errors {error_rate:.0%}>{ERROR_RATE_MAX:.0%}")

    status = "BREACH: " + ", ".join(reasons) if breach else "OK"
    print(
        f"ttft_med={ttft_median:.2f}s  e2e_med={e2e_median:.2f}s  "
        f"err={error_rate:.0%}  tps={turns_per_sec:.2f}  [{status}]"
    )

    return LevelResult(
        concurrency      = concurrency,
        total_turns      = total_turns,
        failed_turns     = failed_turns,
        error_rate       = round(error_rate, 4),
        ttft_median      = ttft_median,
        ttft_p90         = ttft_p90,
        e2e_median       = e2e_median,
        e2e_p90          = e2e_p90,
        wall_time_s      = round(wall_time, 3),
        turns_per_sec    = turns_per_sec,
        threshold_breach = breach,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_throughput_test(
    levels: list[int] | None = None,
) -> ThroughputResult:
    """
    Execute the full ramp-up and return a ThroughputResult.

    Parameters
    ----------
    levels : concurrency levels to test; None = use CONCURRENCY_LEVELS default
    """
    concurrency_levels = levels or CONCURRENCY_LEVELS
    level_results: list[LevelResult] = []

    print("\n[throughput] Starting ramp-up test")
    print(f"  Levels: {concurrency_levels}")
    print(f"  Turns/user: {TURNS_PER_USER}  |  TTFT threshold: {TTFT_THRESHOLD_S}s  "
          f"|  E2E threshold: {E2E_THRESHOLD_S}s  |  Error-rate max: {ERROR_RATE_MAX:.0%}\n")

    breakpoint_level = 0

    for concurrency in concurrency_levels:
        result = await _run_level(concurrency)
        level_results.append(result)

        if result.threshold_breach and breakpoint_level == 0:
            breakpoint_level = concurrency
            print(f"\n  ⚠  Breakpoint detected at concurrency={concurrency}. "
                  "Stopping ramp-up.\n")
            break

        # Pause before the next level to let the server settle
        await asyncio.sleep(RAMP_PAUSE_S)

    # ── Summarise ──────────────────────────────────────────────────────────
    healthy = [lv for lv in level_results if not lv.threshold_breach]
    max_concurrency   = healthy[-1].concurrency if healthy else 0
    peak_turns_per_sec = max((lv.turns_per_sec for lv in healthy), default=0.0)
    total_turns  = sum(lv.total_turns  for lv in level_results)
    total_failed = sum(lv.failed_turns for lv in level_results)

    print(f"\n[throughput] Max sustainable concurrency : {max_concurrency}")
    print(f"[throughput] Breakpoint                  : "
          f"{breakpoint_level if breakpoint_level else 'not reached'}")
    print(f"[throughput] Peak throughput              : {peak_turns_per_sec:.2f} turns/s")
    print(f"[throughput] Total turns / failed         : {total_turns} / {total_failed}")

    return ThroughputResult(
        levels             = level_results,
        max_concurrency    = max_concurrency,
        breakpoint         = breakpoint_level,
        peak_turns_per_sec = peak_turns_per_sec,
        total_turns        = total_turns,
        total_failed       = total_failed,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def _main() -> None:
    parser = argparse.ArgumentParser(description="Crochetzies throughput / load tester")
    parser.add_argument("--max-users", type=int, default=None,
                        help="Stop ramp-up at this concurrency level")
    parser.add_argument("--step",      type=int, default=None,
                        help="Generate levels 1,1+step,1+2*step,... up to max-users")
    parser.add_argument("--out",       type=str, default="throughput_results.json",
                        help="Output JSON file path")
    args = parser.parse_args()

    if args.step and args.max_users:
        levels = list(range(1, args.max_users + 1, args.step))
    elif args.max_users:
        levels = [lv for lv in CONCURRENCY_LEVELS if lv <= args.max_users]
    else:
        levels = None

    result = await run_throughput_test(levels)

    Path(args.out).write_text(json.dumps(result.to_dict(), indent=2))
    print(f"\n[throughput] Results written → {args.out}")


if __name__ == "__main__":
    asyncio.run(_main())