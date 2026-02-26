from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.core.tool_guard import ToolGuard
from coding_agent.core.tool_result import ToolResult

SCHEMA = {
    "name": "file_move",
    "description": "Move or rename a file or directory within the workspace.",
    "properties": {
        "src": {"type": "string", "description": "Source path (file or directory)."},
        "dst": {"type": "string", "description": "Destination path. Intermediate dirs are created."},
        "overwrite": {
            "type": "boolean",
            "description": "Allow overwriting an existing destination. Default: false.",
        },
    },
    "required": ["src", "dst"],
}


class FileMoveTool:
    name = "file_move"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = Path(workspace_root).resolve()

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        overwrite: bool = bool(args.get("overwrite", False))

        src = Path(args["src"])
        dst = Path(args["dst"])

        if not src.is_absolute():
            src = (self._workspace_root / src).resolve()
        else:
            src = src.resolve()

        if not dst.is_absolute():
            dst = (self._workspace_root / dst).resolve()
        else:
            dst = dst.resolve()

        # Extra workspace boundary check for dst (guard checks args named *path*, not *src/dst*)
        def outside(p: Path) -> bool:
            return self._workspace_root not in p.parents and p != self._workspace_root

        if outside(src):
            return ToolResult.failure("PATH_OUTSIDE_WORKSPACE", f"src '{src}' is outside workspace.")
        if outside(dst):
            return ToolResult.failure("PATH_OUTSIDE_WORKSPACE", f"dst '{dst}' is outside workspace.")

        if not src.exists():
            return ToolResult.failure("SRC_NOT_FOUND", f"Source does not exist: {src}")

        if dst.exists() and not overwrite:
            return ToolResult.failure(
                "DST_EXISTS",
                f"Destination already exists and overwrite=false: {dst}",
            )

        dirs_created: List[str] = []
        if not dst.parent.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dirs_created.append(str(dst.parent.relative_to(self._workspace_root)))

        shutil.move(str(src), str(dst))

        return ToolResult.success(
            data={
                "moved_from": str(src.relative_to(self._workspace_root)),
                "moved_to": str(dst.relative_to(self._workspace_root)),
                "dirs_created": dirs_created,
            },
            message=f"Moved '{src.name}' → '{dst}'",
        )
