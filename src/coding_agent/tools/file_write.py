from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from coding_agent.core.tool_guard import ToolGuard
from coding_agent.core.tool_result import ToolResult

SCHEMA = {
    "name": "file_write",
    "description": (
        "Create or overwrite a file in the workspace. "
        "Intermediate directories are created automatically."
    ),
    "properties": {
        "path": {"type": "string", "description": "Relative or absolute path to the destination file."},
        "content": {"type": "string", "description": "Text content to write."},
        "overwrite": {"type": "boolean", "description": "Allow overwriting an existing file. Default: true."},
    },
    "required": ["path", "content"],
}


class FileWriteTool:
    name = "file_write"

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
        content: str = args["content"]
        overwrite: bool = bool(args.get("overwrite", True))

        path = Path(raw_path)
        if not path.is_absolute():
            path = (self._workspace_root / path).resolve()
        else:
            path = path.resolve()

        existed = path.exists()

        if existed and not overwrite:
            return ToolResult.failure(
                "FILE_EXISTS",
                f"File already exists and overwrite=false: {path}",
            )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult.failure("WRITE_ERROR", f"Could not write file: {exc}")

        return ToolResult.success(
            data={
                "path": str(path),
                "bytes_written": len(content.encode("utf-8")),
                "created": not existed,
                "overwritten": existed,
            },
            message=f"{'Overwrote' if existed else 'Created'} {path.name} ({len(content.encode())} bytes)",
        )


# ── Legacy compatibility shim ──────────────────────────────────────────────


@dataclass
class _LegacyResult:
    is_error: bool
    output: str = ""
    error: str = ""


def execute(args: dict[str, Any]) -> _LegacyResult:
    """Standalone execute function for backwards compatibility."""
    from coding_agent.tools.file_write import FileWriteTool

    path_str: str | None = args.get("path")
    if not path_str:
        return _LegacyResult(is_error=True, error="Path is required")

    path = Path(path_str)

    # Reject if path points to an existing directory
    if path.exists() and path.is_dir():
        return _LegacyResult(is_error=True, error=f"path is a directory: {path_str}")

    workspace = str(path.parent.resolve()) if path.is_absolute() else str(Path.cwd())
    tool = FileWriteTool(workspace_root=workspace)
    result = tool.run(args)

    if not result.ok:
        return _LegacyResult(is_error=True, error=result.message)

    bytes_written = result.data.get("bytes_written", 0)
    return _LegacyResult(
        is_error=False,
        output=f"Successfully wrote {bytes_written} bytes to {path_str}",
    )