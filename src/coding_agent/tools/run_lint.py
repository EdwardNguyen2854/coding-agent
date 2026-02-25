from __future__ import annotations

import json
import re
import subprocess
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.tool_guard import ToolGuard
from coding_agent.tool_result import ToolResult

SCHEMA = {
    "name": "run_lint",
    "description": (
        "Run the linter and return structured issues. "
        "Auto-detects ruff or eslint. Returns a structured issues array instead of raw text."
    ),
    "properties": {
        "command": {
            "type": "string",
            "description": "Lint command. Auto-detected if omitted.",
        },
        "paths": {
            "type": "array",
            "description": "Limit linting to specific files or directories.",
        },
    },
    "required": [],
}

Issue = Dict[str, Any]


def _parse_ruff_json(raw: str) -> List[Issue]:
    try:
        items = json.loads(raw)
    except Exception:
        return []
    issues: List[Issue] = []
    for item in items:
        loc = item.get("location", {})
        issues.append({
            "file": item.get("filename", ""),
            "line": loc.get("row", 0),
            "col": loc.get("column", 0),
            "rule": item.get("code", ""),
            "message": item.get("message", ""),
            "severity": "error" if item.get("fix") is None else "warning",
        })
    return issues


def _parse_eslint_json(raw: str) -> List[Issue]:
    try:
        items = json.loads(raw)
    except Exception:
        return []
    issues: List[Issue] = []
    for file_result in items:
        filepath = file_result.get("filePath", "")
        for msg in file_result.get("messages", []):
            issues.append({
                "file": filepath,
                "line": msg.get("line", 0),
                "col": msg.get("column", 0),
                "rule": msg.get("ruleId") or "",
                "message": msg.get("message", ""),
                "severity": "error" if msg.get("severity") == 2 else "warning",
            })
    return issues


def _fallback_parse(raw: str) -> List[Issue]:
    """Best-effort extraction from plain text lint output."""
    issues: List[Issue] = []
    # Pattern: file.py:10:5: E123 message
    pattern = re.compile(r"^(.+?):(\d+):(\d+):\s*(\S+)\s+(.+)$", re.MULTILINE)
    for m in pattern.finditer(raw):
        issues.append({
            "file": m.group(1),
            "line": int(m.group(2)),
            "col": int(m.group(3)),
            "rule": m.group(4),
            "message": m.group(5),
            "severity": "error",
        })
    return issues


class RunLintTool:
    name = "run_lint"

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
                    "No linter detected. Install ruff or eslint, or provide a command.",
                )
        else:
            # Infer parser from provided command string
            if "ruff" in command:
                parser_used = "ruff"
            elif "eslint" in command:
                parser_used = "eslint"

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
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return ToolResult.failure("TIMEOUT", "Linter timed out after 60s")
        except Exception as exc:
            return ToolResult.failure("EXEC_ERROR", str(exc))

        raw = proc.stdout + proc.stderr
        issues: List[Issue] = []

        if parser_used == "ruff":
            issues = _parse_ruff_json(proc.stdout) or _fallback_parse(raw)
            if not _parse_ruff_json(proc.stdout) and raw:
                parser_used = "fallback"
        elif parser_used == "eslint":
            issues = _parse_eslint_json(proc.stdout) or _fallback_parse(raw)
            if not _parse_eslint_json(proc.stdout) and raw:
                parser_used = "fallback"
        else:
            issues = _fallback_parse(raw)

        clean = len(issues) == 0 and proc.returncode == 0

        return ToolResult.success(
            data={
                "clean": clean,
                "issue_count": len(issues),
                "issues": issues,
                "raw_output": raw,
                "parser_used": parser_used,
            },
            message="No issues found" if clean else f"{len(issues)} issue(s) found",
            warnings=[] if clean else [f"{len(issues)} lint issue(s) need attention"],
        )

    def _detect_command(self) -> tuple[Optional[str], str]:
        if shutil.which("ruff"):
            return "ruff check --output-format json", "ruff"
        if shutil.which("eslint"):
            return "eslint --format json", "eslint"
        if shutil.which("flake8"):
            return "flake8", "fallback"
        return None, "fallback"
