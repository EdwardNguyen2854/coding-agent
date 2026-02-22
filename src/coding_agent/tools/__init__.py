"""Tool registry - will be populated as tools are implemented."""

from typing import Any

from coding_agent.tools.base import ToolDefinition, ToolResult


tool_registry: dict[str, ToolDefinition] = {}


def register_tool(definition: ToolDefinition) -> None:
    """Register a tool in the registry.

    Args:
        definition: The ToolDefinition to register
    """
    tool_registry[definition.name] = definition


def get_openai_tools() -> list[dict[str, Any]]:
    """Get all tools in OpenAI function calling format.

    Returns:
        List of tool definitions in OpenAI function calling format
    """
    tools = []
    for tool_def in tool_registry.values():
        tools.append({
            "type": "function",
            "function": {
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": tool_def.parameters,
            },
        })
    return tools


def execute_tool(name: str, params: dict) -> ToolResult:
    """Execute a tool by name with given parameters.

    Args:
        name: Tool name
        params: Tool parameters

    Returns:
        ToolResult from execution
    """
    if name not in tool_registry:
        return ToolResult(
            output="",
            error=f"Unknown tool: {name}",
            is_error=True,
        )

    tool_def = tool_registry[name]
    try:
        return tool_def.handler(params)
    except Exception as e:
        return ToolResult(
            output="",
            error=str(e),
            is_error=True,
        )


# Register stub tools for testing
from coding_agent.tools import file_read, file_write, file_edit, glob_tool, grep_tool, shell  # noqa: E402, F401

register_tool(file_read.definition)
register_tool(file_write.definition)
register_tool(file_edit.definition)
register_tool(glob_tool.definition)
register_tool(grep_tool.definition)
register_tool(shell.definition)
