"""Tool orchestrator with schema validation, async execution, and timeouts."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from tools import CalculatorTool, CRMTool, WeatherTool, CalendarTool
from tools.base import ToolError, ToolSpec, ToolTimeoutError, ToolValidationError


# ---------------------------------------------------------------------------
# Argument parsing and validation
# ---------------------------------------------------------------------------

def _parse_args(args: Any) -> Dict[str, Any]:
    if args is None:
        return {}
    if isinstance(args, dict):
        return dict(args)
    if isinstance(args, str):
        text = args.strip()
        if not text:
            return {}
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ToolValidationError("Tool arguments must decode to a JSON object.")
        return parsed
    raise ToolValidationError("Tool arguments must be a dictionary or a JSON string.")


def _coerce_value(value: Any, schema: Dict[str, Any]) -> Any:
    schema_type = schema.get("type")
    if value is None:
        return None

    if schema_type == "string":
        return str(value)

    if schema_type == "integer":
        if isinstance(value, bool):
            raise ToolValidationError("Boolean values are not valid integers.")
        return int(value)

    if schema_type == "number":
        if isinstance(value, bool):
            raise ToolValidationError("Boolean values are not valid numbers.")
        return float(value)

    if schema_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
        raise ToolValidationError("Boolean arguments must be true/false values.")

    if schema_type == "object":
        if not isinstance(value, dict):
            raise ToolValidationError("Object arguments must be dictionaries.")
        return value

    if schema_type == "array":
        if not isinstance(value, list):
            raise ToolValidationError("Array arguments must be lists.")
        return value

    return value


def _validate_args(args: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    missing = [
        field for field in required
        if field not in args or args[field] in (None, "")
    ]
    if missing:
        raise ToolValidationError(f"Missing required arguments: {', '.join(missing)}")

    if not schema.get("additionalProperties", True):
        unexpected = sorted(set(args.keys()) - set(properties.keys()))
        if unexpected:
            raise ToolValidationError(f"Unexpected arguments: {', '.join(unexpected)}")

    validated: Dict[str, Any] = {}
    for key, value in args.items():
        prop_schema = properties.get(key)
        if prop_schema is None:
            validated[key] = value
            continue

        coerced = _coerce_value(value, prop_schema)

        enum_values = prop_schema.get("enum")
        if enum_values is not None and coerced not in enum_values:
            raise ToolValidationError(
                f"Argument '{key}' must be one of: {', '.join(map(str, enum_values))}"
            )

        minimum = prop_schema.get("minimum")
        maximum = prop_schema.get("maximum")
        if isinstance(coerced, (int, float)):
            if minimum is not None and coerced < minimum:
                raise ToolValidationError(f"Argument '{key}' must be >= {minimum}.")
            if maximum is not None and coerced > maximum:
                raise ToolValidationError(f"Argument '{key}' must be <= {maximum}.")

        validated[key] = coerced

    return validated


# ---------------------------------------------------------------------------
# Response dataclass
# ---------------------------------------------------------------------------

@dataclass
class ToolResponse:
    ok: bool
    tool: str
    result: Any = None
    error: str | None = None
    error_type: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"ok": self.ok, "tool": self.tool}
        if self.ok:
            payload["result"] = self.result
        else:
            payload["error"] = self.error
            payload["error_type"] = self.error_type
        return payload


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class ToolOrchestrator:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register_tool(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def list_tools(self) -> list[Dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "schema": spec.schema,
                "timeout_seconds": spec.timeout_seconds,
            }
            for spec in self._tools.values()
        ]

    def get_schema(self, name: str) -> Dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            raise KeyError(f"Unknown tool: {name}")
        return spec.schema

    async def execute(self, name: str, args: Any) -> Dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResponse(
                False, name,
                error=f"Unknown tool: '{name}'. Available tools: {list(self._tools)}",
                error_type="KeyError",
            ).to_dict()

        try:
            parsed_args = _validate_args(_parse_args(args), spec.schema)
            handler = spec.handler

            if asyncio.iscoroutinefunction(handler):
                coro = handler(parsed_args)
            else:
                # Run sync handlers in a thread so we don't block the event loop.
                loop = asyncio.get_running_loop()
                coro = loop.run_in_executor(None, handler, parsed_args)

            result = await asyncio.wait_for(coro, timeout=spec.timeout_seconds)
            return ToolResponse(True, name, result=result).to_dict()

        except asyncio.TimeoutError:
            return ToolResponse(
                False, name,
                error=f"Tool '{name}' timed out after {spec.timeout_seconds:.1f}s.",
                error_type=ToolTimeoutError.__name__,
            ).to_dict()
        except ToolError as exc:
            return ToolResponse(False, name, error=str(exc), error_type=type(exc).__name__).to_dict()
        except Exception as exc:
            return ToolResponse(False, name, error=str(exc), error_type=type(exc).__name__).to_dict()


# ---------------------------------------------------------------------------
# Default orchestrator (singleton, built once at module import)
# ---------------------------------------------------------------------------

def build_default_orchestrator() -> ToolOrchestrator:
    crm_tool = CRMTool()
    calculator_tool = CalculatorTool()
    weather_tool = WeatherTool()
    calendar_tool = CalendarTool()

    orchestrator = ToolOrchestrator()
    orchestrator.register_tool(
        ToolSpec(
            name="crm",
            description="Store, retrieve, update, delete, and list customer CRM records.",
            schema=CRMTool.schema(),
            handler=crm_tool.run,
            timeout_seconds=5.0,
        )
    )
    orchestrator.register_tool(
        ToolSpec(
            name="calculator",
            description="Safely evaluate arithmetic expressions.",
            schema=CalculatorTool.schema(),
            handler=calculator_tool.run,
            timeout_seconds=5.0,
        )
    )
    orchestrator.register_tool(
        ToolSpec(
            name="weather",
            description=(
                "Check weather conditions and assess delivery impact "
                "based on weather patterns for a given location."
            ),
            schema=WeatherTool.schema(),
            handler=weather_tool.run,
            timeout_seconds=10.0,
        )
    )
    orchestrator.register_tool(
        ToolSpec(
            name="calendar",
            description=(
                "Estimate delivery dates for custom crochet orders "
                "based on order date and processing time in business days."
            ),
            schema=CalendarTool.schema(),
            handler=calendar_tool.run,
            timeout_seconds=5.0,
        )
    )
    return orchestrator


_DEFAULT_ORCHESTRATOR: ToolOrchestrator | None = None
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tool-worker")


def _get_orchestrator() -> ToolOrchestrator:
    """Return the singleton orchestrator, building it on first call."""
    global _DEFAULT_ORCHESTRATOR
    if _DEFAULT_ORCHESTRATOR is None:
        _DEFAULT_ORCHESTRATOR = build_default_orchestrator()
    return _DEFAULT_ORCHESTRATOR


# ---------------------------------------------------------------------------
# Public async entry point
# ---------------------------------------------------------------------------

async def execute_tool(name: str, args: Any) -> Dict[str, Any]:
    """Execute a registered tool asynchronously and return a structured response."""
    return await _get_orchestrator().execute(name, args)


# ---------------------------------------------------------------------------
# Sync wrapper — SAFE for use in async contexts
# ---------------------------------------------------------------------------

def execute_tool_sync(name: str, args: Any) -> Dict[str, Any]:
    """
    Synchronous wrapper for tool execution - SAFE for async contexts.
    Uses threading to avoid event loop conflicts.
    """
    def _run_in_thread():
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(execute_tool(name, args))
            finally:
                loop.close()
        except Exception as e:
            return {"ok": False, "error": str(e), "error_type": type(e).__name__}
    
    # Run in separate thread with its own event loop
    future = _EXECUTOR.submit(_run_in_thread)
    return future.result(timeout=15)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def get_tool_schema(name: str) -> Dict[str, Any]:
    return _get_orchestrator().get_schema(name)


def list_tools() -> list[Dict[str, Any]]:
    return _get_orchestrator().list_tools()