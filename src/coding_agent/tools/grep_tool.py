"""Grep tool - search file contents by regex pattern."""

import subprocess

from coding_agent.tools.base import ToolDefinition, ToolResult


def execute(params: dict) -> ToolResult:
    """Search file contents by regex pattern using ripgrep.

    Args:
        params: Dict with 'pattern' (required), 'path' (optional), 'mode' (optional)

    Returns:
        ToolResult with search results
    """
    pattern = params.get("pattern", "")
    path = params.get("path", ".")
    mode = params.get("mode", "lines")

    if not pattern:
        return ToolResult(output="", error="Pattern is required", is_error=True)

    cmd = ["rg", "--smart-case"]
    if mode == "files":
        cmd.append("--files")
    elif mode == "count":
        cmd.append("--count")
    else:
        cmd.extend(["--line-number", "--no-heading"])

    cmd.extend([pattern, path])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout
        if len(output) > 30000:
            output = output[:30000] + "\n[Output truncated]"
        return ToolResult(output=output, error=None, is_error=False)
    except subprocess.TimeoutExpired:
        return ToolResult(output="", error="Search timed out", is_error=True)
    except FileNotFoundError:
        return ToolResult(output="", error="ripgrep (rg) not found", is_error=True)
    except Exception as e:
        return ToolResult(output="", error=f"Grep failed: {str(e)}", is_error=True)


definition = ToolDefinition(
    name="grep",
    description="Search file contents by regex pattern using ripgrep",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search"},
            "path": {"type": "string", "description": "Directory path to search", "default": "."},
            "mode": {
                "type": "string",
                "description": "Output mode: lines, files, or count",
                "default": "lines",
            },
        },
        "required": ["pattern"],
    },
    handler=execute,
)
