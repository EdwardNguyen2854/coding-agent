from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.tool_guard import ToolGuard
from coding_agent.tool_result import ToolResult

SCHEMA = {
    "name": "git_commit",
    "description": (
        "Stage files and create a git commit. "
        "confirmed=true must be passed explicitly — this is a write operation with lasting effects. "
        "If paths is provided those files are staged automatically before committing."
    ),
    "properties": {
        "message": {"type": "string", "description": "Commit message. Required."},
        "paths": {
            "type": "array",
            "description": "Files to auto-stage before committing. If omitted, only already-staged changes are committed.",
        },
        "signoff": {
            "type": "boolean",
            "description": "Add a Signed-off-by trailer. Default: false.",
        },
        "confirmed": {
            "type": "boolean",
            "description": "Must be true to proceed. Prevents accidental commits.",
        },
    },
    "required": ["message"],  # confirmed defaults to False; checked explicitly in run()
}


def _run_git(args: List[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )


class GitCommitTool:
    name = "git_commit"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = str(Path(workspace_root).resolve())

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        confirmed: bool = bool(args.get("confirmed", False))
        if not confirmed:
            return ToolResult.failure(
                "CONFIRMATION_REQUIRED",
                "Set confirmed=true to proceed with the commit. This is a permanent operation.",
            )

        message: str = args["message"]
        paths: List[str] = args.get("paths") or []
        signoff: bool = bool(args.get("signoff", False))

        # Stage requested paths
        if paths:
            add_proc = _run_git(["add", "--"] + paths, self._workspace_root)
            if add_proc.returncode != 0:
                return ToolResult.failure(
                    "GIT_ADD_FAILED",
                    f"git add failed: {add_proc.stderr.strip()}",
                )

        # Verify something is staged
        status_proc = _run_git(["diff", "--cached", "--name-only"], self._workspace_root)
        staged_files = [f for f in status_proc.stdout.strip().splitlines() if f]

        if not staged_files:
            return ToolResult.failure(
                "NOTHING_TO_COMMIT",
                "Nothing is staged for commit. Provide paths or stage files manually.",
            )

        # Commit
        commit_cmd = ["commit", "-m", message]
        if signoff:
            commit_cmd.append("--signoff")

        commit_proc = _run_git(commit_cmd, self._workspace_root)
        if commit_proc.returncode != 0:
            return ToolResult.failure(
                "COMMIT_FAILED",
                f"git commit failed: {commit_proc.stderr.strip()}",
            )

        # Extract commit hash
        hash_proc = _run_git(["rev-parse", "--short", "HEAD"], self._workspace_root)
        commit_hash = hash_proc.stdout.strip() if hash_proc.returncode == 0 else "unknown"

        return ToolResult.success(
            data={
                "committed": True,
                "commit_hash": commit_hash,
                "files_committed": staged_files,
                "message": message,
            },
            message=f"Committed {len(staged_files)} file(s) as {commit_hash}: {message[:60]}",
        )
