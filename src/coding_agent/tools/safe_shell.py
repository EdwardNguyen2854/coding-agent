from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.tool_guard import ToolGuard
from coding_agent.tool_result import ToolResult

SCHEMA = {
    "name": "safe_shell",
    "description": (
        "Execute a shell command after checking it against a configurable allowlist and denylist. "
        "This is the PREFERRED shell tool — use raw shell only when you need a command not covered here. "
        "Blocked commands return a structured reason and a suggested safe alternative."
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

# ── Default patterns ────────────────────────────────────────────────────────

DEFAULT_DENYLIST: List[str] = [
    r"rm\s+-rf",
    r"rm\s+--no-preserve-root",
    r"del\s+/s",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bmkfs\b",
    r"format\s+[A-Za-z]:",
    r"curl\s+.*\|\s*(bash|sh|zsh)",
    r"wget\s+.*\|\s*(bash|sh|zsh)",
    r">\s*/etc/",
    r">\s*/bin/",
    r">\s*/usr/",
]

DEFAULT_ALLOWLIST: List[str] = [
    r"^ls(\s|$)",
    r"^cat\s",
    r"^echo\s",
    r"^pwd$",
    r"^env$",
    r"^python\s+-m\s+pytest",
    r"^pytest",
    r"^npm\s+test",
    r"^npm\s+run\s+\w+",
    r"^npm\s+install",
    r"^git\s+(status|log|diff|show|branch|remote|fetch|pull)",
    r"^ruff\s+check",
    r"^ruff\s+format",
    r"^mypy\s",
    r"^pyright\s",
    r"^tsc\b",
    r"^which\s",
    r"^find\s",
    r"^head\s",
    r"^tail\s",
    r"^wc\s",
    r"^sort\s",
    r"^uniq\s",
    r"^grep\s",
    r"^rg\s",
    r"^python\s",
    r"^python3\s",
    r"^pip\s+install",
    r"^pip3\s+install",
    r"^make\s",
    r"^cargo\s+(build|test|check|clippy)",
    r"^go\s+(build|test|vet|fmt)",
]

_DENY_SUGGESTIONS: Dict[str, str] = {
    r"rm\s+-rf": "Use file_delete with recursive=true for a safe, logged deletion.",
    r"shutdown|reboot": "This is a system-level command; it cannot be run from the agent.",
    r"mkfs|format": "Disk formatting is not permitted from the agent.",
    r"curl.*\|.*bash|wget.*\|.*bash": "Download the script first, inspect it, then run it explicitly.",
    r">\s*/etc/|>\s*/bin/|>\s*/usr/": "Writing to system directories is not permitted.",
}


def _load_config(config_path: Optional[str]) -> tuple[List[str], List[str]]:
    if config_path is None:
        return DEFAULT_ALLOWLIST, DEFAULT_DENYLIST
    try:
        cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
        allow = cfg.get("allowlist", DEFAULT_ALLOWLIST)
        deny = cfg.get("denylist", DEFAULT_DENYLIST)
        return allow, deny
    except Exception:
        return DEFAULT_ALLOWLIST, DEFAULT_DENYLIST


def _match(command: str, patterns: List[str]) -> Optional[str]:
    for pat in patterns:
        if re.search(pat, command, re.IGNORECASE):
            return pat
    return None


def _suggest(matched_pattern: str) -> str:
    for key, suggestion in _DENY_SUGGESTIONS.items():
        if re.search(key, matched_pattern, re.IGNORECASE):
            return suggestion
    return "Consider using a more specific, purpose-built tool (file_delete, git_commit, run_tests, etc.)."


class SafeShellTool:
    name = "safe_shell"

    def __init__(
        self,
        workspace_root: str,
        policy: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = Path(workspace_root).resolve()
        self._allowlist, self._denylist = _load_config(config_path)

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

        # ── Denylist (evaluated first) ──────────────────────────────────────
        deny_match = _match(command, self._denylist)
        if deny_match:
            return ToolResult.success(
                data={
                    "blocked": True,
                    "reason": "Command matched denylist pattern.",
                    "matched_pattern": deny_match,
                    "suggested_safe_alternative": _suggest(deny_match),
                },
                message=f"Blocked by denylist: {deny_match}",
                warnings=["Command was blocked by the denylist."],
            )

        # ── Allowlist ───────────────────────────────────────────────────────
        allow_match = _match(command, self._allowlist)
        if not allow_match:
            return ToolResult.success(
                data={
                    "blocked": True,
                    "reason": "Command not in allowlist.",
                    "matched_pattern": "",
                    "suggested_safe_alternative": (
                        "If this command is safe, add it to the allowlist in the safe_shell config, "
                        "or use the raw shell tool explicitly."
                    ),
                },
                message="Blocked: command not in allowlist",
                warnings=["Command was not in the allowlist."],
            )

        # ── Execute ─────────────────────────────────────────────────────────
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
            return ToolResult.failure("TIMEOUT", f"Command timed out after {timeout}s")
        except Exception as exc:
            return ToolResult.failure("EXEC_ERROR", str(exc))

        return ToolResult.success(
            data={
                "blocked": False,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "exit_code": proc.returncode,
            },
            message=f"Exit code {proc.returncode}",
            warnings=(
                [f"Command exited with non-zero code {proc.returncode}"]
                if proc.returncode != 0
                else []
            ),
        )
