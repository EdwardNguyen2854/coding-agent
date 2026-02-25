from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from coding_agent.tool_guard import ToolGuard
from coding_agent.tool_result import ToolResult

SCHEMA = {
    "name": "file_edit",
    "description": (
        "Edit an existing file by replacing an exact string with new content. "
        "The old_str must match exactly once in the file; use file_read first if unsure."
    ),
    "properties": {
        "path": {"type": "string", "description": "Path to the file to edit."},
        "old_str": {"type": "string", "description": "Exact substring to find and replace. Must occur exactly once."},
        "new_str": {"type": "string", "description": "Replacement text."},
    },
    "required": ["path", "old_str", "new_str"],
}


class FileEditTool:
    name = "file_edit"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = Path(workspace_root).resolve()

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        raw_path = args["path"]
        old_str: str = args["old_str"]
        new_str: str = args["new_str"]

        path = Path(raw_path)
        if not path.is_absolute():
            path = (self._workspace_root / path).resolve()
        else:
            path = path.resolve()

        if not path.exists():
            return ToolResult.failure("FILE_NOT_FOUND", f"File not found: {path}")
        if not path.is_file():
            return ToolResult.failure("NOT_A_FILE", f"Path is not a file: {path}")

        try:
            original = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult.failure("READ_ERROR", f"Could not read file: {exc}")

        count = original.count(old_str)
        if count == 0:
            return ToolResult.failure(
                "MATCH_NOT_FOUND",
                "old_str was not found in the file. Use file_read to inspect current content.",
            )
        if count > 1:
            return ToolResult.failure(
                "AMBIGUOUS_MATCH",
                f"old_str matched {count} times. Make old_str more specific so it matches exactly once.",
            )

        updated = original.replace(old_str, new_str, 1)

        try:
            path.write_text(updated, encoding="utf-8")
        except OSError as exc:
            return ToolResult.failure("WRITE_ERROR", f"Could not write file: {exc}")

        # Compute a simple line-change summary
        old_lines = old_str.count("\n") + 1
        new_lines = new_str.count("\n") + 1

        return ToolResult.success(
            data={
                "path": str(path),
                "old_lines": old_lines,
                "new_lines": new_lines,
                "net_line_change": new_lines - old_lines,
            },
            message=f"Edited {path.name}: replaced {old_lines}-line block with {new_lines}-line block",
        )


# ── Legacy compatibility shim ──────────────────────────────────────────────


@dataclass
class _LegacyResult:
    is_error: bool
    output: str = ""
    error: str = ""


def execute(args: dict[str, Any]) -> _LegacyResult:
    """Standalone execute function for backwards compatibility.

    Old API used old_string / new_string keys; new API uses old_str / new_str.
    This shim translates between the two.
    """
    from coding_agent.tools.file_edit import FileEditTool

    path_str: str | None = args.get("path")
    if not path_str:
        return _LegacyResult(is_error=True, error="path is required")

    # Translate old key names → new key names
    translated = dict(args)
    if "old_string" in translated and "old_str" not in translated:
        translated["old_str"] = translated.pop("old_string")
    if "new_string" in translated and "new_str" not in translated:
        translated["new_str"] = translated.pop("new_string")

    # Reject empty old_str early
    if not translated.get("old_str"):
        return _LegacyResult(is_error=True, error="old_string must not be empty")

    path = Path(path_str)
    workspace = str(path.parent.resolve()) if path.is_absolute() else str(Path.cwd())
    tool = FileEditTool(workspace_root=workspace)
    result = tool.run(translated)

    if not result.ok:
        code = result.error_code or ""
        msg = result.message

        if code == "FILE_NOT_FOUND":
            return _LegacyResult(is_error=True, error=f"file not found: {path_str}")
        if code == "MATCH_NOT_FOUND":
            return _LegacyResult(is_error=True, error=f"old_string not found in file")
        if code == "AMBIGUOUS_MATCH":
            # Extract count from message, e.g. "old_str matched 2 times"
            m = re.search(r"(\d+)", msg)
            count = m.group(1) if m else "?"
            return _LegacyResult(is_error=True, error=f"old_string found {count} times — must match exactly once")
        return _LegacyResult(is_error=True, error=msg)

    return _LegacyResult(is_error=False, output=f"Successfully edited {path_str}")