from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Any, Dict, Optional

from coding_agent.tool_guard import ToolGuard
from coding_agent.tool_result import ToolResult

SCHEMA = {
    "name": "workspace_info",
    "description": (
        "Return a structured snapshot of the workspace environment: OS, installed runtimes "
        "(python, node, java, go), and available CLI tools (git, pytest, npm, ruff, mypy, etc.). "
        "Result is cached after the first call. Pass refresh=true to force re-detection."
    ),
    "properties": {
        "refresh": {
            "type": "boolean",
            "description": "Force re-probe even if a cached result exists. Default: false.",
        },
    },
    "required": [],
}

_RUNTIMES = {
    "python": (["python3", "--version"], ["python", "--version"]),
    "node": (["node", "--version"],),
    "java": (["java", "-version"],),
    "go": (["go", "version"],),
}

_TOOLS = [
    "git", "pytest", "npm", "ruff", "eslint", "mypy", "pyright",
    "tsc", "cargo", "make", "docker",
]


def _run(cmd: list[str]) -> Optional[str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        output = (proc.stdout or proc.stderr or "").strip()
        return output or None
    except Exception:
        return None


def _version_from_output(output: str) -> str:
    # Extract the first version-like token: e.g. "Python 3.11.4" → "3.11.4"
    import re
    m = re.search(r"(\d+\.\d+[\.\d]*)", output)
    return m.group(1) if m else output.split()[-1] if output else "unknown"


def _probe_runtimes() -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for name, cmd_variants in _RUNTIMES.items():
        found = False
        for cmd in cmd_variants:
            output = _run(list(cmd))
            if output:
                path = shutil.which(cmd[0])
                result[name] = {
                    "available": True,
                    "version": _version_from_output(output),
                    "path": path or cmd[0],
                }
                found = True
                break
        if not found:
            result[name] = {"available": False}
    return result


def _probe_tools() -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for tool in _TOOLS:
        path = shutil.which(tool)
        result[tool] = {"available": path is not None}
        if path:
            result[tool]["path"] = path
    return result


def _probe_git(workspace_root: str) -> tuple[bool, Optional[str]]:
    if not shutil.which("git"):
        return False, None
    output = _run(["git", "-C", workspace_root, "rev-parse", "--show-toplevel"])
    if output and not output.startswith("fatal"):
        return True, output.strip()
    return True, None  # git exists but not a repo


def _probe_os() -> tuple[str, str]:
    system = platform.system().lower()
    if system == "darwin":
        return "macos", platform.platform()
    if system == "windows":
        return "windows", platform.platform()
    return "linux", platform.platform()


class WorkspaceInfoTool:
    name = "workspace_info"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = workspace_root
        self._cache: Optional[Dict[str, Any]] = None

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        refresh: bool = bool(args.get("refresh", False))

        if self._cache is not None and not refresh:
            return ToolResult.success(
                data=self._cache,
                message="Workspace info (cached)",
            )

        os_name, platform_str = _probe_os()
        runtimes = _probe_runtimes()
        tools = _probe_tools()
        git_present, git_repo_root = _probe_git(self._workspace_root)

        data: Dict[str, Any] = {
            "workspace_root": self._workspace_root,
            "os": os_name,
            "platform": platform_str,
            "runtimes": runtimes,
            "git_present": git_present,
            "git_repo_root": git_repo_root,
            "tools": tools,
        }
        self._cache = data

        return ToolResult.success(data=data, message="Workspace info probed successfully")
