from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from coding_agent.tool_guard import ToolGuard
from coding_agent.tool_result import ToolResult

SCHEMA = {
    "name": "shell",
    "description": (
        "Execute a shell command in the workspace. "
        "Prefer safe_shell for everyday tasks — this tool has no pattern-based guards. "
        "Avoid destructive commands; the agent may require user confirmation for risky operations."
    ),
    "properties": {
        "command": {"type": "string", "description": "Shell command to execute."},
        "cwd": {
            "type": "string",
            "description": "Working directory. Defaults to workspace root.",
        },
        "timeout_sec": {
            "type": "integer",
            "description": "Timeout in seconds. Default: 60.",
        },
    },
    "required": ["command"],
}


class ShellTool:
    name = "shell"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = Path(workspace_root).resolve()

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        command: str = args["command"]
        timeout: int = int(args.get("timeout_sec", 60))

        cwd_raw = args.get("cwd")
        if cwd_raw:
            cwd = Path(cwd_raw)
            if not cwd.is_absolute():
                cwd = (self._workspace_root / cwd).resolve()
            else:
                cwd = cwd.resolve()
        else:
            cwd = self._workspace_root

        if not cwd.exists():
            return ToolResult.failure("CWD_NOT_FOUND", f"Working directory does not exist: {cwd}")

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(cwd),
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ToolResult.failure(
                "TIMEOUT",
                f"Command timed out after {timeout} seconds: {command}",
            )
        except Exception as exc:
            return ToolResult.failure("EXEC_ERROR", f"Execution failed: {exc}")

        success = proc.returncode == 0
        return ToolResult.success(
            data={
                "command": command,
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "success": success,
            },
            message=f"Command exited with code {proc.returncode}",
            warnings=(
                [] if success
                else [f"Command exited with non-zero code {proc.returncode}"]
            ),
        )
