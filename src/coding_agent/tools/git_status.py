from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.tool_guard import ToolGuard
from coding_agent.tool_result import ToolResult

SCHEMA = {
    "name": "git_status",
    "description": (
        "Return a structured snapshot of the current git repository status: "
        "branch, upstream tracking, ahead/behind counts, and staged/unstaged/untracked files."
    ),
    "properties": {},
    "required": [],
}


def _run_git(args: List[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=15,
    )


class GitStatusTool:
    name = "git_status"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = str(Path(workspace_root).resolve())

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        # --- Branch + upstream ---
        branch_proc = _run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], self._workspace_root
        )
        if branch_proc.returncode != 0:
            return ToolResult.failure(
                "NOT_A_REPO",
                f"Not a git repository or git not available: {branch_proc.stderr.strip()}",
            )
        branch = branch_proc.stdout.strip()

        upstream_proc = _run_git(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            self._workspace_root,
        )
        upstream = upstream_proc.stdout.strip() if upstream_proc.returncode == 0 else None

        ahead = behind = 0
        if upstream:
            ab_proc = _run_git(
                ["rev-list", "--left-right", "--count", f"{upstream}...HEAD"],
                self._workspace_root,
            )
            if ab_proc.returncode == 0:
                parts = ab_proc.stdout.strip().split()
                if len(parts) == 2:
                    behind, ahead = int(parts[0]), int(parts[1])

        # --- File status (porcelain v2) ---
        status_proc = _run_git(
            ["status", "--porcelain=v2", "--branch"],
            self._workspace_root,
        )
        if status_proc.returncode != 0:
            return ToolResult.failure("GIT_ERROR", status_proc.stderr.strip())

        staged: List[str] = []
        unstaged: List[str] = []
        untracked: List[str] = []

        for line in status_proc.stdout.splitlines():
            if line.startswith("# "):
                continue
            if line.startswith("? "):
                untracked.append(line[2:])
            elif line.startswith("1 ") or line.startswith("2 "):
                # Format: "1 XY sub mH mI mW hH hI path"
                parts = line.split(" ", 9)
                xy = parts[1] if len(parts) > 1 else "  "
                path = parts[-1].split("\t")[0]
                if xy[0] != "." and xy[0] != " ":
                    staged.append(path)
                if xy[1] != "." and xy[1] != " ":
                    unstaged.append(path)

        # repo root
        root_proc = _run_git(
            ["rev-parse", "--show-toplevel"], self._workspace_root
        )
        repo_root = root_proc.stdout.strip() if root_proc.returncode == 0 else self._workspace_root

        return ToolResult.success(
            data={
                "branch": branch,
                "upstream": upstream,
                "ahead": ahead,
                "behind": behind,
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked,
                "repo_root": repo_root,
            },
            message=f"On branch '{branch}' — {len(staged)} staged, {len(unstaged)} unstaged, {len(untracked)} untracked",
        )
