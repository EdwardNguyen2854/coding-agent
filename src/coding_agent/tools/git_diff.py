from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.core.tool_guard import ToolGuard
from coding_agent.core.tool_result import ToolResult

SCHEMA = {
    "name": "git_diff",
    "description": (
        "Return a structured diff of changes in the repository. "
        "Can show staged changes, unstaged changes, or diff between two refs."
    ),
    "properties": {
        "staged": {
            "type": "boolean",
            "description": "Show staged (index) changes instead of unstaged working-tree changes. Default: false.",
        },
        "pathspec": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Limit diff to specific files or paths.",
        },
        "base_ref": {
            "type": "string",
            "description": "Base git ref for a ref-to-ref diff, e.g. 'main'.",
        },
        "target_ref": {
            "type": "string",
            "description": "Target git ref, e.g. 'HEAD'. Used together with base_ref.",
        },
    },
    "required": [],
}

_FILE_STAT_RE = re.compile(r"^(\S.*?)\s+\|\s+(\d+)\s+([+-]+)", re.MULTILINE)
_DIFF_FILE_RE = re.compile(r"^diff --git a/.+ b/(.+)$", re.MULTILINE)


def _parse_per_file_diffs(diff_text: str) -> List[Dict[str, Any]]:
    """Split a unified diff into per-file chunks with addition/deletion counts."""
    files: List[Dict[str, Any]] = []
    # Split on "diff --git" markers
    chunks = re.split(r"(?=^diff --git )", diff_text, flags=re.MULTILINE)
    for chunk in chunks:
        if not chunk.strip():
            continue
        m = _DIFF_FILE_RE.match(chunk)
        path = m.group(1) if m else "unknown"
        additions = chunk.count("\n+") - chunk.count("\n+++")
        deletions = chunk.count("\n-") - chunk.count("\n---")
        files.append({
            "path": path,
            "additions": max(additions, 0),
            "deletions": max(deletions, 0),
            "diff": chunk,
        })
    return files


class GitDiffTool:
    name = "git_diff"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = str(Path(workspace_root).resolve())

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        staged: bool = bool(args.get("staged", False))
        pathspec: List[str] = args.get("pathspec") or []
        base_ref: Optional[str] = args.get("base_ref")
        target_ref: Optional[str] = args.get("target_ref")

        cmd = ["git", "diff"]

        if base_ref and target_ref:
            cmd += [f"{base_ref}...{target_ref}"]
        elif base_ref:
            cmd += [base_ref]
        elif staged:
            cmd.append("--cached")

        if pathspec:
            cmd += ["--"] + pathspec

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self._workspace_root,
            timeout=30,
        )
        if proc.returncode not in (0, 1):  # git diff exits 1 when there are diffs
            return ToolResult.failure("GIT_ERROR", proc.stderr.strip())

        diff_text = proc.stdout
        files_changed = _parse_per_file_diffs(diff_text) if diff_text else []

        return ToolResult.success(
            data={
                "diff_text": diff_text,
                "files_changed": files_changed,
            },
            message=(
                f"{len(files_changed)} file(s) changed"
                if files_changed
                else "No changes"
            ),
        )
