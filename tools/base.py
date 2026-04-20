"""Shared types for tool implementations and registration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict


ToolHandler = Callable[[Dict[str, Any]], Any | Awaitable[Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: Dict[str, Any]
    handler: ToolHandler
    timeout_seconds: float = 10.0


class ToolError(Exception):
    """Base exception for tool failures."""


class ToolValidationError(ToolError):
    """Raised when tool arguments do not match the tool schema."""


class ToolTimeoutError(ToolError):
    """Raised when a tool takes too long to finish."""