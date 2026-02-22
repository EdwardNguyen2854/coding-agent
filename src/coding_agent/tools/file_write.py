"""File write tool - creates/writes files."""

from pathlib import Path

from coding_agent.tools.base import ToolDefinition, ToolResult


def execute(params: dict) -> ToolResult:
    """Write content to a file.

    Args:
        params: Dict with 'path' (required) and 'content' (required)

    Returns:
        ToolResult with success message or error
    """
    path = params.get("path", "")
    content = params.get("content", "")

    if not path:
        return ToolResult(output="", error="Path is required", is_error=True)

    p = Path(path)

    if p.is_dir():
        return ToolResult(output="", error=f"Path is a directory: {path}", is_error=True)

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except Exception as e:
        return ToolResult(output="", error=f"Failed to write file: {str(e)}", is_error=True)

    return ToolResult(output=f"Successfully wrote to {path}", error=None, is_error=False)


definition = ToolDefinition(
    name="file_write",
    description="Write content to a file, creating parent directories if needed",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to write"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    },
    handler=execute,
)
