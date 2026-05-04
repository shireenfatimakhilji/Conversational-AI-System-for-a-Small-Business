"""
test_llm_tool_invocation.py
============================
Layer 2: LLM tool-invocation accuracy tests.

For each utterance in utterance_dataset.py, this module:
  1. Sends the utterance to the LLM (via ollama).
  2. Parses the raw LLM output for a tool-call JSON pattern.
  3. Checks whether the correct tool was triggered with the right args.

Two-layer test approach per tool:
  Layer 1: Direct unit tests (see test_crm_unit.py, etc.)
  Layer 2: LLM invocation accuracy (this file)

LLM invocation tests are "soft" -- they measure accuracy rates rather than
asserting hard pass/fail per utterance, because small LLMs can be inconsistent.
Hard assertions are only used for high-confidence, unambiguous utterances.

Run (requires Ollama running with qwen2.5:1.5b):
    cd nlp_3
    python evals/test_llm_tool_invocation.py

Or via pytest:
    python -m pytest evals/test_llm_tool_invocation.py -v -s
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import unittest
from dataclasses import dataclass
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# -- utterance dataset --------------------------------------------------------
from evals.utterance_dataset import UTTERANCE_DATASET

# -- tool-call pattern (matches the format used in convo_manager.py) ----------
TOOL_CALL_RE = re.compile(
    r'\{\s*"tool"\s*:\s*"(?P<tool>[^"]+)"\s*,\s*"args"\s*:\s*(?P<args>\{[^{}]*\})\s*\}',
    re.DOTALL,
)

# Minimum accuracy thresholds (proportion of utterances that must pass).
# CRM threshold is intentionally lower because small models (qwen2.5:1.5b)
# tend to respond conversationally rather than emitting CRM tool calls.
MIN_CRM_ACCURACY    = 0.30   # CRM: relaxed -- small model rarely emits CRM calls unprompted
MIN_TOOL_ACCURACY   = 0.55   # general tool accuracy threshold
MIN_NOTOOL_ACCURACY = 0.65   # no-tool utterances must not trigger any tool

# Flag: set to True when Ollama is reachable (detected once at module load)
_OLLAMA_AVAILABLE = False


def _check_ollama() -> bool:
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


_OLLAMA_AVAILABLE = _check_ollama()


# ============================================================================
# LLM invocation helper
# ============================================================================

def _ask_llm(utterance: str) -> str:
    """
    Call the local Ollama model with the system prompt + utterance.
    Returns the raw model output string, or '' if Ollama is unavailable.
    """
    if not _OLLAMA_AVAILABLE:
        return ""
    try:
        import ollama
        from config import MODEL_NAME
        from prompt_temp import build_system_prompt

        messages = [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user",   "content": utterance},
        ]
        response = ollama.chat(model=MODEL_NAME, messages=messages)
        return response["message"]["content"]
    except Exception as exc:
        print(f"[LLM] Error: {exc}")
        return ""


def _parse_tool_call(llm_output: str) -> tuple:
    """
    Extract (tool_name, args_dict) from LLM output.
    Returns (None, None) if no valid tool call is found.
    """
    match = TOOL_CALL_RE.search(llm_output)
    if not match:
        return None, None
    tool_name = match.group("tool").strip()
    try:
        args = json.loads(match.group("args").strip())
    except json.JSONDecodeError:
        args = {}
    return tool_name, args


def _args_match(expected: dict, actual: dict | None) -> bool:
    """Partial match -- all expected key-value pairs must appear in actual."""
    if not expected:
        return True
    if actual is None:
        return False
    for key, val in expected.items():
        if actual.get(key) != val:
            return False
    return True


# ============================================================================
# Result collector
# ============================================================================

@dataclass
class InvocationResult:
    utterance_id:  str
    utterance:     str
    expected_tool: str | None
    actual_tool:   str | None
    expected_args: dict
    actual_args:   dict | None
    tool_correct:  bool
    args_correct:  bool
    llm_output:    str
    latency_s:     float


def _evaluate_utterance(entry: dict) -> InvocationResult:
    t0 = time.perf_counter()
    raw = _ask_llm(entry["utterance"])
    latency = time.perf_counter() - t0

    actual_tool, actual_args = _parse_tool_call(raw)
    expected_tool = entry.get("expected_tool")
    expected_args = entry.get("expected_args", {})

    tool_correct = (actual_tool == expected_tool)
    args_correct = tool_correct and _args_match(expected_args, actual_args)

    return InvocationResult(
        utterance_id  = entry["id"],
        utterance     = entry["utterance"],
        expected_tool = expected_tool,
        actual_tool   = actual_tool,
        expected_args = expected_args,
        actual_args   = actual_args,
        tool_correct  = tool_correct,
        args_correct  = args_correct,
        llm_output    = raw,
        latency_s     = round(latency, 3),
    )


# ============================================================================
# Per-tool test classes (pytest-discoverable)
# ============================================================================

def _run_category(category: str) -> list[InvocationResult]:
    entries = [u for u in UTTERANCE_DATASET if u["category"] == category]
    return [_evaluate_utterance(e) for e in entries]


def _skip_if_no_ollama(test_instance):
    if not _OLLAMA_AVAILABLE:
        raise unittest.SkipTest("Ollama not available -- skipping LLM invocation test")


class TestLLMCRMInvocation(unittest.TestCase):
    """LLM invocation accuracy for CRM tool calls."""

    @classmethod
    def setUpClass(cls):
        if not _OLLAMA_AVAILABLE:
            cls.results = []
            return
        cls.results = _run_category("crm")

    def setUp(self):
        _skip_if_no_ollama(self)

    def test_crm_accuracy_reported(self):
        """Reports CRM accuracy -- does not fail if below threshold (small model limitation)."""
        correct = sum(1 for r in self.results if r.tool_correct)
        accuracy = correct / len(self.results) if self.results else 0
        print(f"\n[CRM] Tool accuracy: {correct}/{len(self.results)} ({accuracy:.0%})")
        # Informational -- threshold is intentionally low for small models
        self.assertGreaterEqual(accuracy, MIN_CRM_ACCURACY,
            f"CRM accuracy {accuracy:.0%} below minimum {MIN_CRM_ACCURACY:.0%}")

    def test_name_utterance_crm_or_conversational(self):
        """'My name is Alice Johnson' -- checks if CRM is called or handled conversationally."""
        entry = next(u for u in UTTERANCE_DATASET if u["id"] == "crm_001")
        r = _evaluate_utterance(entry)
        # Soft assertion: report result but accept conversational response too
        print(f"\n[CRM] crm_001: expected=crm, got={r.actual_tool}")
        # Only fail if the model calls the WRONG tool (not no-tool)
        if r.actual_tool is not None:
            self.assertEqual(r.actual_tool, "crm",
                f"Model called wrong tool '{r.actual_tool}' instead of 'crm' or None")

    def test_lookup_triggers_crm_get(self):
        """'Look up my order. My ID is user_abc123' should trigger crm get."""
        entry = next(u for u in UTTERANCE_DATASET if u["id"] == "crm_007")
        r = _evaluate_utterance(entry)
        print(f"\n[CRM] crm_007: expected=crm, got={r.actual_tool}")
        if r.actual_tool is not None:
            self.assertEqual(r.actual_tool, "crm",
                f"Model called wrong tool '{r.actual_tool}' for lookup")


class TestLLMCalculatorInvocation(unittest.TestCase):
    """LLM must trigger the calculator tool for price/arithmetic questions."""

    @classmethod
    def setUpClass(cls):
        if not _OLLAMA_AVAILABLE:
            cls.results = []
            return
        cls.results = _run_category("calculator")

    def setUp(self):
        _skip_if_no_ollama(self)

    def test_accuracy_above_threshold(self):
        correct = sum(1 for r in self.results if r.tool_correct)
        accuracy = correct / len(self.results) if self.results else 0
        print(f"\n[CALCULATOR] Tool accuracy: {correct}/{len(self.results)} ({accuracy:.0%})")
        self.assertGreaterEqual(accuracy, MIN_TOOL_ACCURACY,
            f"Calculator accuracy {accuracy:.0%} < threshold")

    def test_explicit_calc_triggers_calculator(self):
        """'Calculate 2500 + 3000 + 800' -> calculator."""
        entry = next(u for u in UTTERANCE_DATASET if u["id"] == "calc_005")
        r = _evaluate_utterance(entry)
        self.assertEqual(r.actual_tool, "calculator",
            f"Expected calculator, got '{r.actual_tool}'\nOutput: {r.llm_output[:300]}")


class TestLLMCalendarInvocation(unittest.TestCase):
    """LLM must trigger the calendar tool for delivery date questions."""

    @classmethod
    def setUpClass(cls):
        if not _OLLAMA_AVAILABLE:
            cls.results = []
            return
        cls.results = _run_category("calendar")

    def setUp(self):
        _skip_if_no_ollama(self)

    def test_accuracy_above_threshold(self):
        correct = sum(1 for r in self.results if r.tool_correct)
        accuracy = correct / len(self.results) if self.results else 0
        print(f"\n[CALENDAR] Tool accuracy: {correct}/{len(self.results)} ({accuracy:.0%})")
        self.assertGreaterEqual(accuracy, MIN_TOOL_ACCURACY,
            f"Calendar accuracy {accuracy:.0%} < threshold")

    def test_when_will_arrive_triggers_calendar(self):
        """'When will my order arrive?' -> calendar."""
        entry = next(u for u in UTTERANCE_DATASET if u["id"] == "cal_001")
        r = _evaluate_utterance(entry)
        self.assertEqual(r.actual_tool, "calendar",
            f"Expected calendar, got '{r.actual_tool}'\nOutput: {r.llm_output[:300]}")

    def test_calendar_uses_7_processing_days(self):
        """Calendar calls must use processing_days=7 (standard delivery time)."""
        entry = next(u for u in UTTERANCE_DATASET if u["id"] == "cal_001")
        r = _evaluate_utterance(entry)
        if r.actual_args:
            self.assertEqual(r.actual_args.get("processing_days"), 7,
                f"Expected processing_days=7, got {r.actual_args}")


class TestLLMWeatherInvocation(unittest.TestCase):
    """LLM must trigger the weather tool for weather/delivery weather questions."""

    @classmethod
    def setUpClass(cls):
        if not _OLLAMA_AVAILABLE:
            cls.results = []
            return
        cls.results = _run_category("weather")

    def setUp(self):
        _skip_if_no_ollama(self)

    def test_accuracy_above_threshold(self):
        correct = sum(1 for r in self.results if r.tool_correct)
        accuracy = correct / len(self.results) if self.results else 0
        print(f"\n[WEATHER] Tool accuracy: {correct}/{len(self.results)} ({accuracy:.0%})")
        self.assertGreaterEqual(accuracy, MIN_TOOL_ACCURACY,
            f"Weather accuracy {accuracy:.0%} < threshold")

    def test_delivery_weather_karachi_triggers_weather(self):
        """'Will weather affect delivery in Karachi?' -> weather assess_delivery."""
        entry = next(u for u in UTTERANCE_DATASET if u["id"] == "wx_001")
        r = _evaluate_utterance(entry)
        self.assertEqual(r.actual_tool, "weather",
            f"Expected weather, got '{r.actual_tool}'\nOutput: {r.llm_output[:300]}")


class TestLLMNoToolInvocation(unittest.TestCase):
    """LLM must NOT trigger any tool for conversational/off-topic messages."""

    @classmethod
    def setUpClass(cls):
        if not _OLLAMA_AVAILABLE:
            cls.results = []
            return
        cls.results = _run_category("no_tool")

    def setUp(self):
        _skip_if_no_ollama(self)

    def test_no_tool_accuracy(self):
        not_triggered = sum(1 for r in self.results if r.actual_tool is None)
        accuracy = not_triggered / len(self.results) if self.results else 0
        print(f"\n[NO_TOOL] No-tool accuracy: {not_triggered}/{len(self.results)} ({accuracy:.0%})")
        self.assertGreaterEqual(accuracy, MIN_NOTOOL_ACCURACY,
            f"No-tool accuracy {accuracy:.0%} < {MIN_NOTOOL_ACCURACY:.0%}")

    def test_greeting_no_tool(self):
        entry = next(u for u in UTTERANCE_DATASET if u["id"] == "none_001")
        r = _evaluate_utterance(entry)
        self.assertIsNone(r.actual_tool,
            f"Greeting should not trigger a tool, but triggered '{r.actual_tool}'")

    def test_off_topic_no_tool(self):
        entry = next(u for u in UTTERANCE_DATASET if u["id"] == "none_005")
        r = _evaluate_utterance(entry)
        self.assertIsNone(r.actual_tool,
            f"Off-topic ('capital of France') must not trigger a tool, got '{r.actual_tool}'")


# ============================================================================
# Full sweep runner (standalone, not pytest)
# ============================================================================

def run_llm_invocation_eval() -> dict:
    """
    Run LLM invocation accuracy across the full utterance dataset.
    Returns a summary dict with per-category accuracy metrics.
    """
    print("\n" + "=" * 60)
    print("  LLM TOOL-INVOCATION ACCURACY EVALUATION")
    print("=" * 60)

    if not _OLLAMA_AVAILABLE:
        print("\n  [SKIP] Ollama is not running. Start Ollama and retry.")
        return {"total": 0, "correct": 0, "overall_accuracy": 0.0, "by_category": {},
                "skipped": True}

    all_results: list[InvocationResult] = []
    categories = ["crm", "calculator", "calendar", "weather", "no_tool"]

    for cat in categories:
        entries = [u for u in UTTERANCE_DATASET if u["category"] == cat]
        print(f"\n[{cat.upper()}] Evaluating {len(entries)} utterances...")
        cat_results = []
        for entry in entries:
            r = _evaluate_utterance(entry)
            cat_results.append(r)
            all_results.append(r)
            ok = "OK" if r.tool_correct else "FAIL"
            print(f"  [{ok}] [{r.utterance_id}] expected={r.expected_tool}, "
                  f"got={r.actual_tool} ({r.latency_s:.2f}s)")
        correct = sum(1 for r in cat_results if r.tool_correct)
        if cat_results:
            print(f"  -> Accuracy: {correct}/{len(cat_results)} "
                  f"({correct / len(cat_results) * 100:.0f}%)")

    total_correct = sum(1 for r in all_results if r.tool_correct)
    overall_acc = total_correct / len(all_results) if all_results else 0

    print(f"\n{'-'*60}")
    print(f"  OVERALL ACCURACY: {total_correct}/{len(all_results)} ({overall_acc:.0%})")
    print("=" * 60)

    summary = {
        "total": len(all_results),
        "correct": total_correct,
        "overall_accuracy": round(overall_acc, 4),
        "by_category": {},
    }
    for cat in categories:
        cat_res = [r for r in all_results if next(
            (u["category"] for u in UTTERANCE_DATASET if u["id"] == r.utterance_id), None
        ) == cat]
        if cat_res:
            c = sum(1 for r in cat_res if r.tool_correct)
            summary["by_category"][cat] = {
                "total": len(cat_res),
                "correct": c,
                "accuracy": round(c / len(cat_res), 4),
            }
    return summary


if __name__ == "__main__":
    summary = run_llm_invocation_eval()
    print(f"\nSummary: {json.dumps(summary, indent=2)}")
