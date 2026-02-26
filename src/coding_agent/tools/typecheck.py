from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.core.tool_guard import ToolGuard
from coding_agent.core.tool_result import ToolResult

SCHEMA = {
    "name": "typecheck",
    "description": (
        "Run the type checker and return structured issues. "
        "Auto-detects mypy, pyright, or tsc. Returns structured issues array."
    ),
    "properties": {
        "command": {
            "type": "string",
            "description": "Typecheck command. Auto-detected if omitted.",
        },
        "paths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Limit type-checking to specific files or directories.",
        },
    },
    "required": [],
}

Issue = Dict[str, Any]

_MYPY_RE = re.compile(r"^(.+?):(\d+):\s*(error|warning|note):\s*(.+?)(?:\s+\[([^\]]+)\])?$", re.MULTILINE)
_TSC_RE = re.compile(r"^(.+?)\((\d+),(\d+)\):\s*(error|warning)\s+(TS\d+):\s*(.+)$", re.MULTILINE)
_PYRIGHT_RE = re.compile(r"^\s+(.+?):(\d+):(\d+):\s*(error|warning|information):\s*(.+?)(?:\s+\((.+?)\))?$", re.MULTILINE)


def _parse_mypy(raw: str) -> List[Issue]:
    issues: List[Issue] = []
    for m in _MYPY_RE.finditer(raw):
        severity = m.group(3)
        if severity == "note":
            continue
        issues.append({
            "file": m.group(1),
            "line": int(m.group(2)),
            "col": 0,
            "rule": m.group(5) or "",
            "message": m.group(4),
            "severity": severity,
        })
    return issues


def _parse_pyright(raw: str) -> List[Issue]:
    issues: List[Issue] = []
    for m in _PYRIGHT_RE.finditer(raw):
        issues.append({
            "file": m.group(1),
            "line": int(m.group(2)),
            "col": int(m.group(3)),
            "rule": m.group(6) or "",
            "message": m.group(5),
            "severity": "error" if m.group(4) == "error" else "warning",
        })
    return issues


def _parse_tsc(raw: str) -> List[Issue]:
    issues: List[Issue] = []
    for m in _TSC_RE.finditer(raw):
        issues.append({
            "file": m.group(1),
            "line": int(m.group(2)),
            "col": int(m.group(3)),
            "rule": m.group(5),
            "message": m.group(6),
            "severity": m.group(4),
        })
    return issues


def _fallback_parse(raw: str) -> List[Issue]:
    issues: List[Issue] = []
    pattern = re.compile(r"^(.+?):(\d+):(\d+):\s*(error|warning):\s*(.+)$", re.MULTILINE)
    for m in pattern.finditer(raw):
        issues.append({
            "file": m.group(1),
            "line": int(m.group(2)),
            "col": int(m.group(3)),
            "rule": "",
            "message": m.group(5),
            "severity": m.group(4),
        })
    return issues


class TypecheckTool:
    name = "typecheck"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = str(Path(workspace_root).resolve())

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        paths: List[str] = args.get("paths") or []
        command: Optional[str] = args.get("command")
        parser_used = "fallback"

        if not command:
            command, parser_used = self._detect_command()
            if command is None:
                return ToolResult.failure(
                    "COMMAND_REQUIRED",
                    "No type checker detected. Install mypy, pyright, or tsc, or provide a command.",
                )
        else:
            # Infer parser from provided command string
            if "mypy" in command:
                parser_used = "mypy"
            elif "pyright" in command:
                parser_used = "pyright"
            elif "tsc" in command:
                parser_used = "tsc"

        full_cmd = command
        if paths:
            full_cmd = f"{command} {' '.join(paths)}"

        try:
            proc = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self._workspace_root,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return ToolResult.failure("TIMEOUT", "Type checker timed out after 120s")
        except Exception as exc:
            return ToolResult.failure("EXEC_ERROR", str(exc))

        raw = proc.stdout + proc.stderr

        if parser_used == "mypy":
            issues = _parse_mypy(raw)
        elif parser_used == "pyright":
            issues = _parse_pyright(raw)
        elif parser_used == "tsc":
            issues = _parse_tsc(raw)
        else:
            issues = _fallback_parse(raw)

        if not issues and raw:
            fallback = _fallback_parse(raw)
            if fallback:
                issues = fallback
                parser_used = "fallback"

        clean = len(issues) == 0 and proc.returncode == 0

        return ToolResult.success(
            data={
                "clean": clean,
                "issue_count": len(issues),
                "issues": issues,
                "raw_output": raw,
                "parser_used": parser_used,
            },
            message="No type errors" if clean else f"{len(issues)} type error(s) found",
            warnings=[] if clean else [f"{len(issues)} type error(s) need attention"],
        )

    def _detect_command(self) -> tuple[Optional[str], str]:
        if shutil.which("mypy"):
            return "mypy", "mypy"
        if shutil.which("pyright"):
            return "pyright", "pyright"
        if shutil.which("tsc"):
            return "tsc --noEmit", "tsc"
        return None, "fallback"
