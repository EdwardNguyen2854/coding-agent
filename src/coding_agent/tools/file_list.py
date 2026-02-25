from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.tool_guard import ToolGuard
from coding_agent.tool_result import ToolResult

SCHEMA = {
    "name": "file_list",
    "description": (
        "List files and directories in the workspace as a structured tree. "
        "More readable than glob for exploring project structure."
    ),
    "properties": {
        "path": {"type": "string", "description": "Root directory to list. Defaults to workspace root."},
        "depth": {"type": "integer", "description": "Maximum recursion depth. Default: 2."},
        "include_hidden": {"type": "boolean", "description": "Include hidden entries (starting with '.'). Default: false."},
        "include_files": {"type": "boolean", "description": "Include files in the tree. Default: true."},
        "include_dirs": {"type": "boolean", "description": "Include directories in the tree. Default: true."},
    },
    "required": [],
}


def _build_tree(
    path: Path,
    workspace_root: Path,
    current_depth: int,
    max_depth: int,
    include_hidden: bool,
    include_files: bool,
    include_dirs: bool,
) -> Dict[str, Any]:
    node: Dict[str, Any] = {
        "name": path.name or str(path),
        "type": "dir",
        "path": str(path.relative_to(workspace_root)),
    }

    if current_depth >= max_depth:
        return node

    children: List[Dict[str, Any]] = []
    try:
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return node

    for entry in entries:
        if not include_hidden and entry.name.startswith("."):
            continue
        if entry.is_dir():
            if include_dirs:
                child = _build_tree(
                    entry, workspace_root, current_depth + 1, max_depth,
                    include_hidden, include_files, include_dirs
                )
                children.append(child)
            elif include_files:
                # Still recurse to get files even if dirs themselves are hidden
                sub = _build_tree(
                    entry, workspace_root, current_depth + 1, max_depth,
                    include_hidden, include_files, include_dirs
                )
                children.extend(sub.get("children", []))
        elif entry.is_file() and include_files:
            children.append({
                "name": entry.name,
                "type": "file",
                "path": str(entry.relative_to(workspace_root)),
                "size": entry.stat().st_size,
            })

    node["children"] = children
    return node


class FileListTool:
    name = "file_list"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = Path(workspace_root).resolve()

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        depth: int = int(args.get("depth", 2))
        include_hidden: bool = bool(args.get("include_hidden", False))
        include_files: bool = bool(args.get("include_files", True))
        include_dirs: bool = bool(args.get("include_dirs", True))

        raw_path = args.get("path")
        if raw_path:
            root = Path(raw_path)
            if not root.is_absolute():
                root = (self._workspace_root / root).resolve()
            else:
                root = root.resolve()
        else:
            root = self._workspace_root

        if not root.exists():
            return ToolResult.failure("DIR_NOT_FOUND", f"Directory not found: {root}")
        if not root.is_dir():
            return ToolResult.failure("NOT_A_DIR", f"Path is not a directory: {root}")

        tree = _build_tree(root, self._workspace_root, 0, depth, include_hidden, include_files, include_dirs)

        return ToolResult.success(
            data={"tree": tree},
            message=f"Listed '{root.name}' up to depth {depth}",
        )
