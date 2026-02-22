"""File edit tool - edits files by replacing exact string matches."""

from pathlib import Path

from coding_agent.tools.base import ToolDefinition, ToolResult


def execute(params: dict) -> ToolResult:
    """Edit a file by replacing exact string match.

    Args:
        params: Dict with 'path' (required), 'old_string' (required), 'new_string' (required)

    Returns:
        ToolResult with success message or error
    """
    path = params.get("path", "")
    old_string = params.get("old_string", "")
    new_string = params.get("new_string", "")

    if not path:
        return ToolResult(output="", error="Path is required", is_error=True)

    if not old_string:
        return ToolResult(output="", error="old_string is required", is_error=True)

    p = Path(path)

    if not p.exists():
        return ToolResult(output="", error=f"File not found: {path}", is_error=True)

    if not p.is_file():
        return ToolResult(output="", error=f"Not a file: {path}", is_error=True)

    try:
        content = p.read_text(encoding="utf-8")
    except Exception as e:
        return ToolResult(output="", error=f"Cannot read file: {str(e)}", is_error=True)

    count = content.count(old_string)

    if count == 0:
        return ToolResult(output="", error=f"String not found in file: {old_string}", is_error=True)

    if count > 1:
        return ToolResult(
            output="",
            error=f"String appears {count} times. Be more specific.",
            is_error=True,
        )

    new_content = content.replace(old_string, new_string, 1)

    try:
        p.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return ToolResult(output="", error=f"Cannot write file: {str(e)}", is_error=True)

    return ToolResult(output=f"Successfully edited {path}", error=None, is_error=False)


definition = ToolDefinition(
    name="file_edit",
    description="Edit a file by replacing exact string match (only works when string appears exactly once)",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to edit"},
            "old_string": {"type": "string", "description": "String to replace"},
            "new_string": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_string", "new_string"],
    },
    handler=execute,
)
