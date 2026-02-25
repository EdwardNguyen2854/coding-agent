"""Base types for tool system."""

from dataclasses import dataclass, field
from typing import Any, Callable

from coding_agent.tool_result import ToolResult


@dataclass
class ToolDefinition:
    """Definition of a tool available to the agent."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict], ToolResult]
    schema: dict[str, Any] = field(default_factory=dict)
