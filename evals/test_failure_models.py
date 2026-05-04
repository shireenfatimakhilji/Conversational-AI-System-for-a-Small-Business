"""
test_failure_modes.py
=====================
Negative / failure-mode tests for Crochetzies tools.

Covers:
  1. Tool timeout simulation (orchestrator-level)
  2. Empty database scenarios (CRM)
  3. Malformed tool-call JSON from the LLM
  4. Missing required arguments
  5. Wrong argument types / out-of-range values
  6. Unknown tool name
  7. Network failure simulation (Weather API)
  8. ConcurrentDelete race condition
  9. Orchestrator arg validation pipeline

Run:
    cd nlp_3
    python -m pytest evals/test_failure_modes.py -v
  OR standalone:
    python evals/test_failure_modes.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.crm import CRMTool
from tools.calculator import CalculatorTool
from tools.calendar import CalendarTool
from tools.weather import WeatherTool
from tools.base import ToolSpec
from orchestrator import (
    ToolOrchestrator,
    _parse_args,
    _validate_args,
    _coerce_value,
    build_default_orchestrator,
)


def run(coro):
    """Run a coroutine, always using a fresh event loop (Python 3.10 compatible)."""
    return asyncio.run(coro)


# ── Shared temp CRM helper ─────────────────────────────────────────────────────

class TempCRM:
    def __enter__(self):
        self._dir = tempfile.mkdtemp()
        db = os.path.join(self._dir, "fail_test.sqlite3")
        self.crm = CRMTool(db_path=db)
        return self.crm

    def __exit__(self, *_):
        import shutil
        shutil.rmtree(self._dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Tool Timeout Simulation
# ══════════════════════════════════════════════════════════════════════════════

class TestToolTimeout(unittest.TestCase):
    """The orchestrator must respect timeout_seconds and return an error response."""

    def test_slow_tool_times_out(self):
        """A tool that sleeps beyond its timeout must return ok=False with timeout error."""
        async def _run():
            orchestrator = ToolOrchestrator()

            async def slow_handler(args):
                await asyncio.sleep(10)
                return {"done": True}

            orchestrator.register_tool(ToolSpec(
                name="slow_tool",
                description="Always times out",
                schema={"type": "object", "properties": {}, "required": []},
                handler=slow_handler,
                timeout_seconds=0.1,   # 100 ms — very short
            ))
            return await orchestrator.execute("slow_tool", {})

        result = asyncio.run(_run())
        self.assertFalse(result["ok"])
        self.assertIn("timed out", result["error"].lower())
        self.assertEqual(result["error_type"], "ToolTimeoutError")

    def test_fast_tool_does_not_time_out(self):
        """A fast tool completes within timeout → ok=True."""
        async def _run():
            orchestrator = ToolOrchestrator()

            async def fast_handler(args):
                return {"value": 42}

            orchestrator.register_tool(ToolSpec(
                name="fast_tool",
                description="Fast",
                schema={"type": "object", "properties": {}, "required": []},
                handler=fast_handler,
                timeout_seconds=5.0,
            ))
            return await orchestrator.execute("fast_tool", {})

        result = asyncio.run(_run())
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["value"], 42)

    def test_timeout_result_structure(self):
        """Timeout response must contain: ok, tool, error, error_type."""
        async def _run():
            orchestrator = ToolOrchestrator()

            async def timeout_handler(args):
                await asyncio.sleep(5)

            orchestrator.register_tool(ToolSpec(
                name="t2",
                description="x",
                schema={"type": "object", "properties": {}, "required": []},
                handler=timeout_handler,
                timeout_seconds=0.05,
            ))
            return await orchestrator.execute("t2", {})

        result = asyncio.run(_run())
        for field in ("ok", "tool", "error", "error_type"):
            self.assertIn(field, result, f"Missing field '{field}' in timeout response")


# ══════════════════════════════════════════════════════════════════════════════
# 2. Empty Database Scenarios (CRM)
# ══════════════════════════════════════════════════════════════════════════════

class TestCRMEmptyDatabase(unittest.TestCase):
    """Test CRM behaviour when the database is completely empty."""

    def test_list_empty_db_returns_empty_list(self):
        with TempCRM() as crm:
            result = run(crm.run({"action": "list"}))
            self.assertEqual(result["users"], [])
            self.assertIsInstance(result["users"], list)

    def test_get_from_empty_db_returns_none(self):
        with TempCRM() as crm:
            result = run(crm.run({"action": "get", "user_id": "nonexistent"}))
            self.assertIsNone(result["user"])

    def test_delete_from_empty_db_returns_false(self):
        with TempCRM() as crm:
            result = run(crm.run({"action": "delete", "user_id": "nobody"}))
            self.assertFalse(result["deleted"])

    def test_update_empty_db_raises(self):
        """Updating a user that does not exist must raise ValueError."""
        with TempCRM() as crm:
            with self.assertRaises(ValueError):
                run(crm.run({"action": "update", "user_id": "ghost", "name": "Ghost"}))

    def test_list_after_all_deleted_is_empty(self):
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "tmp", "name": "Temp"}))
            run(crm.run({"action": "delete", "user_id": "tmp"}))
            result = run(crm.run({"action": "list"}))
            self.assertEqual(result["users"], [])


# ══════════════════════════════════════════════════════════════════════════════
# 3. Malformed Tool-Call JSON
# ══════════════════════════════════════════════════════════════════════════════

TOOL_CALL_RE = re.compile(
    r'\{\s*"tool"\s*:\s*"(?P<tool>[^"]+)"\s*,\s*"args"\s*:\s*(?P<args>\{[^{}]*\})\s*\}',
    re.DOTALL,
)


class TestMalformedToolCall(unittest.TestCase):
    """
    Simulate what happens when the LLM produces malformed tool-call JSON.
    The convo_manager.py gracefully skips malformed calls.
    """

    def _extract(self, text: str):
        match = TOOL_CALL_RE.search(text)
        if not match:
            return None, None
        tool = match.group("tool")
        try:
            args = json.loads(match.group("args"))
        except json.JSONDecodeError:
            args = None
        return tool, args

    def test_no_tool_call_returns_none(self):
        tool, _ = self._extract("Hello! I'm here to help you with crochet orders.")
        self.assertIsNone(tool)

    def test_truncated_json_not_parsed(self):
        """Incomplete JSON → regex won't match → graceful no-op."""
        output = '{"tool": "crm", "args": {"action": "ups'
        tool, _ = self._extract(output)
        self.assertIsNone(tool)

    def test_invalid_args_json_returns_none_args(self):
        """Syntactically broken args → args should fail to parse."""
        output = '{"tool": "crm", "args": {action: upsert}}'
        tool, args = self._extract(output)
        # The regex may not even match invalid JSON keys
        if tool is not None:
            self.assertIsNone(args)

    def test_extra_text_around_json_parsed(self):
        """Tool call embedded in prose → regex must still find it."""
        output = 'Sure! Let me store that. {"tool": "crm", "args": {"action": "upsert", "user_id": "u1", "name": "Alice"}} Done!'
        tool, args = self._extract(output)
        self.assertEqual(tool, "crm")
        self.assertEqual(args["action"], "upsert")

    def test_wrong_field_name_not_matched(self):
        """'function_call' instead of 'tool' → not matched by regex."""
        output = '{"function_call": "crm", "args": {"action": "upsert"}}'
        tool, _ = self._extract(output)
        self.assertIsNone(tool)

    def test_double_tool_call_first_matched(self):
        """If the LLM emits two tool calls, only the first is captured."""
        output = (
            '{"tool": "crm", "args": {"action": "upsert", "user_id": "u1", "name": "A"}} '
            '{"tool": "calculator", "args": {"expression": "1+1"}}'
        )
        tool, _ = self._extract(output)
        self.assertEqual(tool, "crm")

    def test_orchestrator_handles_invalid_json_string(self):
        """Passing invalid JSON string to orchestrator execute → ok=False."""
        orchestrator = build_default_orchestrator()
        result = run(orchestrator.execute("calculator", "not-json"))
        self.assertFalse(result["ok"])


# ══════════════════════════════════════════════════════════════════════════════
# 4. Missing Required Arguments
# ══════════════════════════════════════════════════════════════════════════════

class TestMissingRequiredArgs(unittest.TestCase):
    """Orchestrator must return ok=False when required args are absent."""

    def _exec(self, tool_name: str, args: dict) -> dict:
        orchestrator = build_default_orchestrator()
        return run(orchestrator.execute(tool_name, args))

    def test_calculator_missing_expression(self):
        result = self._exec("calculator", {"precision": 2})
        self.assertFalse(result["ok"])
        self.assertIn("expression", result["error"].lower())

    def test_calendar_missing_order_date(self):
        result = self._exec("calendar", {"processing_days": 7})
        self.assertFalse(result["ok"])
        self.assertIn("order_date", result["error"].lower())

    def test_calendar_missing_processing_days(self):
        result = self._exec("calendar", {"order_date": "2026-04-20"})
        self.assertFalse(result["ok"])
        self.assertIn("processing_days", result["error"].lower())

    def test_crm_missing_action(self):
        result = self._exec("crm", {"user_id": "u1", "name": "Alice"})
        self.assertFalse(result["ok"])

    def test_weather_missing_location(self):
        result = self._exec("weather", {"action": "check_weather"})
        self.assertFalse(result["ok"])

    def test_crm_get_missing_user_id(self):
        result = self._exec("crm", {"action": "get"})
        self.assertFalse(result["ok"])

    def test_crm_delete_missing_user_id(self):
        result = self._exec("crm", {"action": "delete"})
        self.assertFalse(result["ok"])


# ══════════════════════════════════════════════════════════════════════════════
# 5. Wrong Argument Types / Out-of-Range Values
# ══════════════════════════════════════════════════════════════════════════════

class TestWrongArgTypes(unittest.TestCase):
    """Orchestrator validation should reject wrong types and out-of-range values."""

    def _exec(self, tool_name: str, args) -> dict:
        orchestrator = build_default_orchestrator()
        return run(orchestrator.execute(tool_name, args))

    def test_calculator_precision_too_high(self):
        result = self._exec("calculator", {"expression": "1+1", "precision": 99})
        self.assertFalse(result["ok"])

    def test_calculator_precision_negative(self):
        result = self._exec("calculator", {"expression": "1+1", "precision": -1})
        self.assertFalse(result["ok"])

    def test_calendar_zero_processing_days(self):
        result = self._exec("calendar", {"order_date": "2026-04-20", "processing_days": 0})
        self.assertFalse(result["ok"])

    def test_calendar_bad_date_format(self):
        result = self._exec("calendar", {"order_date": "not-a-date", "processing_days": 7})
        self.assertFalse(result["ok"])

    def test_calculator_extra_arg_rejected(self):
        """additionalProperties=False means unknown keys should be rejected."""
        result = self._exec("calculator", {"expression": "1+1", "unknown_field": "oops"})
        # Should fail validation because calculator schema has additionalProperties=False
        self.assertFalse(result["ok"])

    def test_weather_unknown_action(self):
        result = self._exec("weather", {"action": "fly_to_moon", "location": "Karachi"})
        self.assertFalse(result["ok"])

    def test_boolean_as_integer_rejected(self):
        """Boolean is not a valid integer for precision."""
        result = self._exec("calculator", {"expression": "1+1", "precision": True})
        self.assertFalse(result["ok"])


# ══════════════════════════════════════════════════════════════════════════════
# 6. Unknown Tool Name
# ══════════════════════════════════════════════════════════════════════════════

class TestUnknownTool(unittest.TestCase):
    """Calling an unregistered tool must return ok=False with a helpful error."""

    def test_unknown_tool_returns_error(self):
        orchestrator = build_default_orchestrator()
        result = run(orchestrator.execute("nonexistent_tool", {}))
        self.assertFalse(result["ok"])
        self.assertIn("nonexistent_tool", result["error"])

    def test_unknown_tool_error_type(self):
        orchestrator = build_default_orchestrator()
        result = run(orchestrator.execute("fake", {}))
        self.assertEqual(result["error_type"], "KeyError")

    def test_unknown_tool_suggests_available(self):
        orchestrator = build_default_orchestrator()
        result = run(orchestrator.execute("typoed_tool", {}))
        # The error message should list available tools
        self.assertIn("Available tools", result["error"])


# ══════════════════════════════════════════════════════════════════════════════
# 7. Network / API Failure (Weather)
# ══════════════════════════════════════════════════════════════════════════════

class TestWeatherNetworkFailure(unittest.TestCase):
    """Simulate network failures for the weather tool (real API mode)."""

    def test_aiohttp_connection_error_handled(self):
        """If the HTTP connection fails, WeatherTool must raise an exception."""
        import aiohttp
        tool = WeatherTool(api_key="real_key_triggers_real_path")

        async def raise_conn_error(*args, **kwargs):
            raise aiohttp.ClientConnectionError("Network unreachable")

        with patch.object(aiohttp.ClientSession, "get", side_effect=raise_conn_error):
            with self.assertRaises(Exception):
                run(tool.run({"action": "check_weather", "location": "London"}))

    def test_api_non_200_status_raises(self):
        """A non-200 API response should raise ValueError."""
        import aiohttp
        tool = WeatherTool(api_key="real_key")

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with self.assertRaises((ValueError, Exception)):
                run(tool.run({"action": "check_weather", "location": "London"}))

    def test_demo_mode_never_fails_network(self):
        """Demo mode must never make network requests; it always returns data."""
        demo = WeatherTool(api_key="demo")
        result = run(demo.run({"action": "check_weather", "location": "Karachi"}))
        self.assertTrue(result is not None)
        self.assertIn("weather", result)


# ══════════════════════════════════════════════════════════════════════════════
# 8. Orchestrator Argument Parsing
# ══════════════════════════════════════════════════════════════════════════════

class TestOrchestratorArgParsing(unittest.TestCase):
    """Unit-test the orchestrator's internal _parse_args and _validate_args."""

    def test_parse_dict_passthrough(self):
        args = {"action": "upsert", "user_id": "u1"}
        self.assertEqual(_parse_args(args), args)

    def test_parse_json_string(self):
        args_str = '{"action": "get", "user_id": "u2"}'
        parsed = _parse_args(args_str)
        self.assertEqual(parsed["action"], "get")
        self.assertEqual(parsed["user_id"], "u2")

    def test_parse_none_returns_empty(self):
        self.assertEqual(_parse_args(None), {})

    def test_parse_empty_string_returns_empty(self):
        self.assertEqual(_parse_args(""), {})

    def test_parse_invalid_json_raises(self):
        from tools.base import ToolValidationError
        with self.assertRaises((ToolValidationError, json.JSONDecodeError, Exception)):
            _parse_args("{not valid json}")

    def test_parse_json_array_raises(self):
        from tools.base import ToolValidationError
        with self.assertRaises((ToolValidationError, Exception)):
            _parse_args("[1, 2, 3]")

    def test_validate_missing_required_raises(self):
        from tools.base import ToolValidationError
        schema = {"properties": {"name": {"type": "string"}}, "required": ["name"]}
        with self.assertRaises(ToolValidationError):
            _validate_args({}, schema)

    def test_validate_enum_violation_raises(self):
        from tools.base import ToolValidationError
        schema = {
            "properties": {"action": {"type": "string", "enum": ["get", "set"]}},
            "required": ["action"],
        }
        with self.assertRaises(ToolValidationError):
            _validate_args({"action": "delete"}, schema)

    def test_validate_min_violation_raises(self):
        from tools.base import ToolValidationError
        schema = {
            "properties": {"count": {"type": "integer", "minimum": 1}},
            "required": ["count"],
        }
        with self.assertRaises(ToolValidationError):
            _validate_args({"count": 0}, schema)

    def test_validate_additional_properties_rejected(self):
        from tools.base import ToolValidationError
        schema = {
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
            "additionalProperties": False,
        }
        with self.assertRaises(ToolValidationError):
            _validate_args({"expression": "1+1", "sneaky": True}, schema)

    def test_coerce_string(self):
        self.assertEqual(_coerce_value(123, {"type": "string"}), "123")

    def test_coerce_integer(self):
        self.assertEqual(_coerce_value("7", {"type": "integer"}), 7)

    def test_coerce_boolean_string_true(self):
        self.assertTrue(_coerce_value("yes", {"type": "boolean"}))

    def test_coerce_boolean_string_false(self):
        self.assertFalse(_coerce_value("false", {"type": "boolean"}))

    def test_coerce_bool_as_int_raises(self):
        from tools.base import ToolValidationError
        with self.assertRaises(ToolValidationError):
            _coerce_value(True, {"type": "integer"})


# ══════════════════════════════════════════════════════════════════════════════
# 9. Race condition: concurrent delete + get
# ══════════════════════════════════════════════════════════════════════════════

class TestCRMConcurrentDeleteGet(unittest.TestCase):
    """
    Race condition: one thread deletes a user while another gets it.
    The outcome is non-deterministic, but neither operation should crash.
    """

    def test_concurrent_delete_and_get_no_exception(self):
        import threading
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "race_user", "name": "Racer"}))
            errors = []

            def _get():
                try:
                    asyncio.run(crm.run({"action": "get", "user_id": "race_user"}))
                except Exception as e:
                    errors.append(f"GET: {e}")

            def _delete():
                try:
                    asyncio.run(crm.run({"action": "delete", "user_id": "race_user"}))
                except Exception as e:
                    errors.append(f"DELETE: {e}")

            threads = [threading.Thread(target=_get if i % 2 == 0 else _delete)
                       for i in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [], f"Race condition errors: {errors}")


# ══════════════════════════════════════════════════════════════════════════════
# Standalone runner
# ══════════════════════════════════════════════════════════════════════════════

def run_failure_mode_tests() -> dict:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestToolTimeout,
        TestCRMEmptyDatabase,
        TestMalformedToolCall,
        TestMissingRequiredArgs,
        TestWrongArgTypes,
        TestUnknownTool,
        TestWeatherNetworkFailure,
        TestOrchestratorArgParsing,
        TestCRMConcurrentDeleteGet,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return {
        "total": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "passed": result.wasSuccessful(),
    }


if __name__ == "__main__":
    summary = run_failure_mode_tests()
    print(f"\n{'='*60}")
    print(f"FAILURE MODE TEST SUMMARY")
    print(f"  Total  : {summary['total']}")
    print(f"  Passed : {summary['total'] - summary['failures'] - summary['errors']}")
    print(f"  Failed : {summary['failures']}")
    print(f"  Errors : {summary['errors']}")
    print(f"  Result : {'✅ ALL PASSED' if summary['passed'] else '❌ SOME FAILED'}")
    print(f"{'='*60}")
