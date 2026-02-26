from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from coding_agent.core.tool_guard import ToolGuard
from coding_agent.core.tool_result import ToolResult

SCHEMA = {
    "name": "file_read",
    "description": (
        "Read the contents of a file from the workspace. "
        "Optionally control the line range returned via offset and limit."
    ),
    "properties": {
        "path": {"type": "string", "description": "Relative or absolute path to the file."},
        "offset": {"type": "integer", "description": "0-based line index to start reading from. Default: 0."},
        "limit": {"type": "integer", "description": "Maximum number of lines to return. Omit to read entire file."},
    },
    "required": ["path"],
}


class FileReadTool:
    name = "file_read"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = Path(workspace_root).resolve()

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        # --- Guard ---------------------------------------------------------
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        # --- Resolve path --------------------------------------------------
        raw_path = args["path"]
        path = Path(raw_path)
        if not path.is_absolute():
            path = (self._workspace_root / path).resolve()
        else:
            path = path.resolve()

        offset: int = int(args.get("offset", 0))
        limit: Optional[int] = args.get("limit")

        # --- Read ----------------------------------------------------------
        if not path.exists():
            return ToolResult.failure("FILE_NOT_FOUND", f"File not found: {path}")
        if not path.is_file():
            return ToolResult.failure("NOT_A_FILE", f"Path is not a file: {path}")

        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError as exc:
            return ToolResult.failure("READ_ERROR", f"Could not read file: {exc}")

        total_lines = len(lines)
        sliced = lines[offset:] if limit is None else lines[offset: offset + limit]
        content = "".join(sliced)

        return ToolResult.success(
            data={
                "path": str(path),
                "content": content,
                "total_lines": total_lines,
                "returned_lines": len(sliced),
                "offset": offset,
            },
            message=f"Read {len(sliced)} lines from {path.name}",
        )


# ── Legacy compatibility shim ──────────────────────────────────────────────
# The original API exposed a standalone execute() function returning an object
# with .is_error / .output / .error attributes. New code should use
# FileReadTool(workspace_root).run(args) instead.


@dataclass
class _LegacyResult:
    is_error: bool
    output: str = ""
    error: str = ""


def execute(args: dict[str, Any]) -> _LegacyResult:
    """Standalone execute function for backwards compatibility.

    Wraps FileReadTool using the file's own directory as workspace root,
    then converts ToolResult to the legacy result shape.
    """
    from coding_agent.tools.file_read import FileReadTool

    path_str: str | None = args.get("path")
    if not path_str:
        return _LegacyResult(is_error=True, error="path is required")

    path = Path(path_str)

    # Detect binary files before delegating
    if path.exists() and path.is_file():
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return _LegacyResult(is_error=True, error="binary file cannot be read as text")

    workspace = str(path.parent.resolve()) if path.is_absolute() else str(Path.cwd())
    tool = FileReadTool(workspace_root=workspace)
    result = tool.run(args)

    if not result.ok:
        msg = result.message.lower()
        if "not found" in msg:
            return _LegacyResult(is_error=True, error=f"file not found: {path_str}")
        return _LegacyResult(is_error=True, error=result.message)

    # Format output with line numbers to match old behaviour:
    # "     1  line1\n     2  line2\n..."
    content: str = result.data.get("content", "")
    if not content:
        return _LegacyResult(is_error=False, output="")

    offset: int = int(args.get("offset", 0))
    lines = content.splitlines()
    formatted = "\n".join(
        f"{(offset + i + 1):6}  {line}" for i, line in enumerate(lines)
    )
    return _LegacyResult(is_error=False, output=formatted)