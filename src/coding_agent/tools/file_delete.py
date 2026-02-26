from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from coding_agent.core.tool_guard import ToolGuard
from coding_agent.core.tool_result import ToolResult

SCHEMA = {
    "name": "file_delete",
    "description": (
        "Delete a file or directory from the workspace. "
        "Directories require recursive=true to prevent accidental data loss."
    ),
    "properties": {
        "path": {"type": "string", "description": "Path to delete."},
        "recursive": {
            "type": "boolean",
            "description": "Required to be true when deleting a directory. Default: false.",
        },
    },
    "required": ["path"],
}


class FileDeleteTool:
    name = "file_delete"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = Path(workspace_root).resolve()

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        recursive: bool = bool(args.get("recursive", False))

        path = Path(args["path"])
        if not path.is_absolute():
            path = (self._workspace_root / path).resolve()
        else:
            path = path.resolve()

        if not path.exists():
            return ToolResult.failure("NOT_FOUND", f"Path does not exist: {path}")

        is_dir = path.is_dir()

        if is_dir and not recursive:
            return ToolResult.failure(
                "RECURSIVE_REQUIRED",
                f"'{path}' is a directory. Set recursive=true to delete it and its contents.",
            )

        try:
            if is_dir:
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            return ToolResult.failure("DELETE_ERROR", f"Could not delete: {exc}")

        return ToolResult.success(
            data={
                "deleted": str(path.relative_to(self._workspace_root)),
                "was_directory": is_dir,
            },
            message=f"Deleted {'directory' if is_dir else 'file'}: {path.name}",
        )
