"""Glob tool - search for files by glob pattern."""

from pathlib import Path

from coding_agent.tools.base import ToolDefinition, ToolResult


def execute(params: dict) -> ToolResult:
    """Search for files by glob pattern.

    Args:
        params: Dict with 'pattern' (required)

    Returns:
        ToolResult with matching file paths
    """
    pattern = params.get("pattern", "")

    if not pattern:
        return ToolResult(output="", error="Pattern is required", is_error=True)

    try:
        base = Path(".")
        matches = list(base.glob(pattern))
        matches = sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)
        matches = matches[:200]

        result = "\n".join(str(m) for m in matches)
        return ToolResult(output=result, error=None, is_error=False)
    except Exception as e:
        return ToolResult(output="", error=f"Glob failed: {str(e)}", is_error=True)


definition = ToolDefinition(
    name="glob",
    description="Search for files by glob pattern",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern (e.g., **/*.py)"},
        },
        "required": ["pattern"],
    },
    handler=execute,
)
