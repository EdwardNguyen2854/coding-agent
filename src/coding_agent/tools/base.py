"""Base types for tool system."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolResult:
    """Result from tool execution."""

    output: str
    error: str | None = None
    is_error: bool = False


@dataclass
class ToolDefinition:
    """Definition of a tool available to the agent."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict], ToolResult]
