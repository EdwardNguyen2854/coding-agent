"""File read tool - reads files with line numbers."""

from pathlib import Path

from coding_agent.tools.base import ToolDefinition, ToolResult


def execute(params: dict) -> ToolResult:
    """Read a file with line numbers.

    Args:
        params: Dict with 'path' (required), 'offset' (optional), 'limit' (optional)

    Returns:
        ToolResult with file contents or error
    """
    path = params.get("path", "")
    offset = params.get("offset", 0)
    limit = params.get("limit")

    if not path:
        return ToolResult(output="", error="Path is required", is_error=True)

    p = Path(path)

    if not p.exists():
        return ToolResult(output="", error=f"File not found: {path}", is_error=True)

    if not p.is_file():
        return ToolResult(output="", error=f"Not a file: {path}", is_error=True)

    try:
        with open(p, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return ToolResult(output="", error="Cannot read binary file", is_error=True)
    except Exception as e:
        return ToolResult(output="", error=f"Cannot read file: {str(e)}", is_error=True)

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return ToolResult(output="", error=f"Cannot read file: {str(e)}", is_error=True)

    lines = content.splitlines()

    if offset > 0:
        lines = lines[offset:]
    if limit is not None:
        lines = lines[:limit]

    numbered = [f"{i + 1:6d}  {line}" for i, line in enumerate(lines)]

    return ToolResult(output="\n".join(numbered), error=None, is_error=False)


definition = ToolDefinition(
    name="file_read",
    description="Read contents of a file with line numbers",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"},
            "offset": {
                "type": "integer",
                "description": "Line number to start from (0-indexed)",
                "default": 0,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read",
                "default": None,
            },
        },
        "required": ["path"],
    },
    handler=execute,
)
