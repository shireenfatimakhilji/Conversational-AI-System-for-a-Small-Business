"""
utils.py — Shared helpers for the Crochetzies performance evaluation suite.

Responsibilities:
  - Session lifecycle (create / delete via REST)
  - WebSocket streaming with timing instrumentation
  - Statistical aggregation (mean, median, p90, p99)
  - Structured result types
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

# ---------------------------------------------------------------------------
# Configuration — change these if your server runs elsewhere
# ---------------------------------------------------------------------------

BASE_URL    = "http://localhost:8000"
WS_BASE_URL = "ws://localhost:8000"

# Per-turn timeout: how long to wait before declaring a turn failed (seconds)
TURN_TIMEOUT_SECONDS = 60.0

# How long to wait between scenario trials to avoid thermal throttling
INTER_TRIAL_SLEEP = 0.05   # seconds


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class TurnTimings:
    """Raw timing measurements for one chatbot turn."""
    ttft:             float        # Time To First Token  (seconds)
    inter_token_avg:  float        # Mean inter-token gap (seconds)
    end_to_end:       float        # Total wall-clock time (seconds)
    token_count:      int          # Number of tokens received
    ok:               bool = True  # False if the turn timed-out or errored
    error:            str  = ""


@dataclass
class ScenarioResult:
    """Aggregated statistics for one scenario over N trials."""
    scenario:    str
    trials:      int
    failed:      int

    # TTFT stats
    ttft_mean:   float
    ttft_median: float
    ttft_p90:    float
    ttft_p99:    float

    # Inter-token latency stats
    itl_mean:    float
    itl_median:  float
    itl_p90:     float
    itl_p99:     float

    # End-to-end stats
    e2e_mean:    float
    e2e_median:  float
    e2e_p90:     float
    e2e_p99:     float

    raw: list[TurnTimings] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario":  self.scenario,
            "trials":    self.trials,
            "failed":    self.failed,
            "ttft":      {"mean": self.ttft_mean,  "median": self.ttft_median,
                          "p90":  self.ttft_p90,   "p99":    self.ttft_p99},
            "inter_token_latency": {
                          "mean": self.itl_mean,   "median": self.itl_median,
                          "p90":  self.itl_p90,    "p99":    self.itl_p99},
            "end_to_end":{"mean": self.e2e_mean,   "median": self.e2e_median,
                          "p90":  self.e2e_p90,    "p99":    self.e2e_p99},
        }


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

async def create_session(session: aiohttp.ClientSession) -> tuple[str, str]:
    """
    POST /session/new  →  (session_id, greeting)

    Raises RuntimeError if the server returns a non-200 status.
    """
    async with session.post(f"{BASE_URL}/session/new") as resp:
        if resp.status != 200:
            body = await resp.text()
            raise RuntimeError(f"Failed to create session (HTTP {resp.status}): {body}")
        data = await resp.json()
    return data["session_id"], data.get("greeting", "")


async def delete_session(session: aiohttp.ClientSession, session_id: str) -> None:
    """DELETE /session/{session_id}  — best-effort cleanup.

    404 is expected: api.py already deletes the session when the WebSocket
    closes (WebSocketDisconnect handler), so the evals script's explicit
    cleanup call will often find it already gone. This is harmless.
    """
    try:
        async with session.delete(f"{BASE_URL}/session/{session_id}") as resp:
            if resp.status not in (200, 404):
                # 404 = already deleted by api.py (expected). Anything else is odd.
                print(f"[cleanup] Unexpected status {resp.status} deleting {session_id}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core streaming measurement
# ---------------------------------------------------------------------------

async def measure_turn(
    session_id: str,
    message:    str,
    http:       aiohttp.ClientSession,
) -> TurnTimings:
    """
    Open a WebSocket, send one user message, and collect timing data.

    Protocol (matches api.py):
      send  → {"message": "<text>"}
      recv  → {"type": "token", "data": "<tok>"}  (repeating)
      recv  → {"type": "done",  "data": ""}
      recv  → {"type": "session_end", ...}  (optional, on order completion)
      recv  → {"type": "error", "data": "..."}  (on failure)
    """
    ws_url = f"{WS_BASE_URL}/ws/chat/{session_id}"

    t_send           = 0.0
    t_first_token    = 0.0
    t_last_token     = 0.0
    token_timestamps: list[float] = []
    token_count      = 0

    try:
        async with asyncio.timeout(TURN_TIMEOUT_SECONDS):
            async with http.ws_connect(ws_url) as ws:
                # ── Send the user message ──────────────────────────────────
                t_send = time.perf_counter()
                await ws.send_str(json.dumps({"message": message}))

                # ── Receive until "done" ───────────────────────────────────
                async for raw_msg in ws:
                    if raw_msg.type == aiohttp.WSMsgType.TEXT:
                        frame = json.loads(raw_msg.data)
                        ftype = frame.get("type", "")

                        if ftype == "token":
                            now = time.perf_counter()
                            token_count += 1
                            token_timestamps.append(now)
                            if token_count == 1:
                                t_first_token = now

                        elif ftype in ("done", "session_end"):
                            t_last_token = time.perf_counter()
                            break

                        elif ftype == "error":
                            return TurnTimings(
                                ttft=0, inter_token_avg=0, end_to_end=0,
                                token_count=0, ok=False,
                                error=frame.get("data", "server error"),
                            )

                    elif raw_msg.type in (
                        aiohttp.WSMsgType.ERROR,
                        aiohttp.WSMsgType.CLOSED,
                    ):
                        return TurnTimings(
                            ttft=0, inter_token_avg=0, end_to_end=0,
                            token_count=0, ok=False,
                            error="WebSocket closed unexpectedly",
                        )

    except asyncio.TimeoutError:
        return TurnTimings(
            ttft=0, inter_token_avg=0, end_to_end=0,
            token_count=0, ok=False,
            error=f"Turn timed out after {TURN_TIMEOUT_SECONDS}s",
        )
    except Exception as exc:
        return TurnTimings(
            ttft=0, inter_token_avg=0, end_to_end=0,
            token_count=0, ok=False,
            error=str(exc),
        )

    # ── Compute metrics ────────────────────────────────────────────────────
    ttft       = t_first_token - t_send if t_first_token else 0.0
    end_to_end = t_last_token  - t_send if t_last_token  else 0.0

    # Inter-token gaps: differences between consecutive token timestamps
    if len(token_timestamps) >= 2:
        gaps = [
            token_timestamps[i] - token_timestamps[i - 1]
            for i in range(1, len(token_timestamps))
        ]
        inter_token_avg = statistics.mean(gaps)
    else:
        inter_token_avg = 0.0

    return TurnTimings(
        ttft            = round(ttft,            4),
        inter_token_avg = round(inter_token_avg, 4),
        end_to_end      = round(end_to_end,      4),
        token_count     = token_count,
        ok              = True,
    )


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def _percentile(data: list[float], pct: float) -> float:
    """Return the p-th percentile of *data* (0–100). Requires ≥1 element."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    index = (pct / 100) * (len(sorted_data) - 1)
    lower = int(index)
    upper = min(lower + 1, len(sorted_data) - 1)
    frac  = index - lower
    return round(sorted_data[lower] * (1 - frac) + sorted_data[upper] * frac, 4)


def aggregate(scenario: str, timings: list[TurnTimings]) -> ScenarioResult:
    """
    Compute mean / median / p90 / p99 for TTFT, inter-token latency,
    and end-to-end latency over a list of TurnTimings.

    Failed trials are counted but excluded from statistics so they don't
    skew the numbers.
    """
    failed  = [t for t in timings if not t.ok]
    success = [t for t in timings if t.ok]

    def _stats(values: list[float]) -> tuple[float, float, float, float]:
        if not values:
            return 0.0, 0.0, 0.0, 0.0
        return (
            round(statistics.mean(values),   4),
            round(statistics.median(values), 4),
            _percentile(values, 90),
            _percentile(values, 99),
        )

    ttft_vals = [t.ttft            for t in success]
    itl_vals  = [t.inter_token_avg for t in success]
    e2e_vals  = [t.end_to_end      for t in success]

    tm, tmed, tp90, tp99 = _stats(ttft_vals)
    im, imed, ip90, ip99 = _stats(itl_vals)
    em, emed, ep90, ep99 = _stats(e2e_vals)

    return ScenarioResult(
        scenario    = scenario,
        trials      = len(timings),
        failed      = len(failed),
        ttft_mean   = tm,  ttft_median = tmed, ttft_p90 = tp90, ttft_p99 = tp99,
        itl_mean    = im,  itl_median  = imed, itl_p90  = ip90, itl_p99  = ip99,
        e2e_mean    = em,  e2e_median  = emed, e2e_p90  = ep90, e2e_p99  = ep99,
        raw         = timings,
    )


# ---------------------------------------------------------------------------
# Latency threshold checker
# ---------------------------------------------------------------------------

THRESHOLDS = {
    "ttft_median_max":  2.0,   # seconds
    "e2e_median_max":  10.0,   # seconds
}


def check_thresholds(result: ScenarioResult) -> list[str]:
    """
    Return a list of human-readable violations.
    Empty list means the scenario passed all thresholds.
    """
    violations: list[str] = []
    if result.ttft_median > THRESHOLDS["ttft_median_max"]:
        violations.append(
            f"[{result.scenario}] median TTFT {result.ttft_median:.2f}s "
            f"> threshold {THRESHOLDS['ttft_median_max']}s"
        )
    if result.e2e_median > THRESHOLDS["e2e_median_max"]:
        violations.append(
            f"[{result.scenario}] median E2E {result.e2e_median:.2f}s "
            f"> threshold {THRESHOLDS['e2e_median_max']}s"
        )
    return violations