"""
latency.py — Single-user latency evaluation for Crochetzies chatbot.

Scenarios
---------
  simple  – plain conversation, no RAG retrieval, no tool trigger
  rag     – question that hits the RAG knowledge base
  tool    – message that triggers a tool (calendar or weather)
  mixed   – message that retrieves RAG docs AND triggers a tool

Each scenario runs TRIALS = 30 turns by default.

Usage
-----
    python latency.py                  # run all 4 scenarios, print + save JSON
    python latency.py --trials 10      # quick smoke-test with fewer trials
    python latency.py --scenario rag   # run only the "rag" scenario
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import aiohttp

from utils import (
    INTER_TRIAL_SLEEP,
    ScenarioResult,
    TurnTimings,
    aggregate,
    check_thresholds,
    create_session,
    delete_session,
    measure_turn,
)

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

# Each entry is (scenario_key, message_to_send).
#
# Prompts are chosen so the server-side routing behaves predictably:
#   simple → generic greeting; unlikely to hit RAG or tools
#   rag    → asks about pricing/customization; hits ChromaDB docs
#   tool   → asks for delivery date; triggers calendar tool
#   mixed  → asks about delivery timing with context; hits RAG + calendar tool

SCENARIO_MESSAGES: dict[str, str] = {
    "simple": "Hello! Can you help me with my order?",
    "rag":    "What are your customization options and pricing for crochet items?",
    "tool":   "When will my order arrive if I place it today with 7 processing days?",
    "mixed":  "I'd like to know about bulk order pricing and when I can expect delivery.",
}

TRIALS = 30   # trials per scenario (increase for tighter confidence intervals)


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

async def run_scenario(
    scenario:  str,
    message:   str,
    trials:    int,
) -> ScenarioResult:
    """
    Run *trials* turns for one scenario.

    A fresh HTTP session is created once for the whole scenario run.
    Each trial creates its own chatbot session so conversation state
    never bleeds between trials.
    """
    print(f"\n[latency] Scenario: {scenario!r}  ({trials} trials)")
    timings: list[TurnTimings] = []

    async with aiohttp.ClientSession() as http:
        for i in range(trials):
            # ── Create a fresh chatbot session for each trial ──────────────
            try:
                session_id, _ = await create_session(http)
            except RuntimeError as exc:
                print(f"  trial {i+1:>3}/{trials}  SKIP — could not create session: {exc}")
                timings.append(TurnTimings(
                    ttft=0, inter_token_avg=0, end_to_end=0,
                    token_count=0, ok=False, error=str(exc),
                ))
                continue

            # ── Measure one turn ───────────────────────────────────────────
            t = await measure_turn(session_id, message, http)
            timings.append(t)

            status = (
                f"ttft={t.ttft:.3f}s  e2e={t.end_to_end:.3f}s  "
                f"tokens={t.token_count}"
                if t.ok
                else f"FAILED — {t.error}"
            )
            print(f"  trial {i+1:>3}/{trials}  {status}")

            # ── Clean up ───────────────────────────────────────────────────
            await delete_session(http, session_id)

            # Small sleep to avoid hammering the server back-to-back
            await asyncio.sleep(INTER_TRIAL_SLEEP)

    result = aggregate(scenario, timings)
    _print_scenario_summary(result)
    return result


# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------

def _print_scenario_summary(r: ScenarioResult) -> None:
    print(f"\n  ── {r.scenario.upper()} summary ({r.trials - r.failed}/{r.trials} successful) ──")
    print(f"  {'metric':<22} {'mean':>8} {'median':>8} {'p90':>8} {'p99':>8}")
    print(f"  {'-'*58}")
    print(f"  {'TTFT (s)':<22} {r.ttft_mean:>8.3f} {r.ttft_median:>8.3f} "
          f"{r.ttft_p90:>8.3f} {r.ttft_p99:>8.3f}")
    print(f"  {'Inter-token (s)':<22} {r.itl_mean:>8.3f} {r.itl_median:>8.3f} "
          f"{r.itl_p90:>8.3f} {r.itl_p99:>8.3f}")
    print(f"  {'End-to-end (s)':<22} {r.e2e_mean:>8.3f} {r.e2e_median:>8.3f} "
          f"{r.e2e_p90:>8.3f} {r.e2e_p99:>8.3f}")

    violations = check_thresholds(r)
    if violations:
        print("\n  ⚠  THRESHOLD VIOLATIONS:")
        for v in violations:
            print(f"     {v}")
    else:
        print("\n  ✓  All thresholds passed.")


# ---------------------------------------------------------------------------
# Public entry point (called by run_performance.py or directly)
# ---------------------------------------------------------------------------

async def run_all_latency_scenarios(
    trials: int = TRIALS,
    scenarios: list[str] | None = None,
) -> dict[str, ScenarioResult]:
    """
    Run every requested scenario and return a dict of ScenarioResult objects.

    Parameters
    ----------
    trials    : number of trials per scenario
    scenarios : subset of scenario keys to run; None = run all four
    """
    keys_to_run = scenarios or list(SCENARIO_MESSAGES.keys())
    results: dict[str, ScenarioResult] = {}

    for key in keys_to_run:
        if key not in SCENARIO_MESSAGES:
            print(f"[latency] Unknown scenario {key!r} — skipping.")
            continue
        result = await run_scenario(key, SCENARIO_MESSAGES[key], trials)
        results[key] = result

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def _main() -> None:
    parser = argparse.ArgumentParser(description="Crochetzies latency evaluator")
    parser.add_argument("--trials",   type=int, default=TRIALS,
                        help=f"Trials per scenario (default {TRIALS})")
    parser.add_argument("--scenario", type=str, default=None,
                        choices=list(SCENARIO_MESSAGES.keys()),
                        help="Run only this scenario")
    parser.add_argument("--out",      type=str, default="latency_results.json",
                        help="Output JSON file path")
    args = parser.parse_args()

    scenarios = [args.scenario] if args.scenario else None

    print("=" * 60)
    print("  Crochetzies — Latency Evaluation")
    print("=" * 60)
    t0 = time.perf_counter()

    results = await run_all_latency_scenarios(args.trials, scenarios)

    elapsed = time.perf_counter() - t0
    print(f"\n[latency] Total wall time: {elapsed:.1f}s")

    # ── Serialise to JSON ──────────────────────────────────────────────────
    output = {k: v.to_dict() for k, v in results.items()}
    Path(args.out).write_text(json.dumps(output, indent=2))
    print(f"[latency] Results written → {args.out}")


if __name__ == "__main__":
    asyncio.run(_main())