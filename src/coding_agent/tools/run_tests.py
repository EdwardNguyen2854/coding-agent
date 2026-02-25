from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.tool_guard import ToolGuard
from coding_agent.tool_result import ToolResult

SCHEMA = {
    "name": "run_tests",
    "description": (
        "Run the test suite and return structured pass/fail results. "
        "Auto-detects pytest or npm test via workspace_info when command is omitted. "
        "Returns a failures array — no need to parse raw log output."
    ),
    "properties": {
        "command": {
            "type": "string",
            "description": "Test command to run. Auto-detected if omitted.",
        },
        "focus": {
            "type": "array",
            "description": "Specific test files or test names to run.",
        },
        "timeout_sec": {
            "type": "integer",
            "description": "Timeout in seconds. Default: 60.",
        },
    },
    "required": [],
}

# Pytest failure block pattern
_PYTEST_FAIL_RE = re.compile(
    r"^_{3,}\s+(?:FAILED\s+)?(.+?)\s+_{3,}$", re.MULTILINE
)
_PYTEST_FILE_TEST_RE = re.compile(r"^(.+?)::(.+)$")
_PYTEST_REASON_RE = re.compile(r"(E\s+.+?)(?=\n\S|\Z)", re.DOTALL)


def _parse_pytest_output(raw: str) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    # Find FAILED lines: "FAILED path/test_foo.py::test_bar - reason"
    for line in raw.splitlines():
        if line.startswith("FAILED "):
            rest = line[len("FAILED "):].strip()
            m = _PYTEST_FILE_TEST_RE.match(rest.split(" - ")[0])
            reason_part = rest.split(" - ", 1)[1] if " - " in rest else ""
            failures.append({
                "file": m.group(1) if m else rest,
                "test": m.group(2) if m else rest,
                "reason": reason_part,
                "snippet": "",
            })
    return failures


def _parse_jest_output(raw: str) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        if "✕" in line or "✗" in line or line.strip().startswith("●"):
            failures.append({
                "file": "",
                "test": line.strip().lstrip("●").strip(),
                "reason": "",
                "snippet": "",
            })
    return failures


class RunTestsTool:
    name = "run_tests"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = str(Path(workspace_root).resolve())

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        timeout: int = int(args.get("timeout_sec", 60))
        focus: List[str] = args.get("focus") or []
        command: Optional[str] = args.get("command")

        if not command:
            command = self._detect_command()
            if command is None:
                return ToolResult.failure(
                    "COMMAND_REQUIRED",
                    "Could not auto-detect test runner. Provide a command explicitly.",
                )

        if focus:
            command = f"{command} {' '.join(focus)}"

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self._workspace_root,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ToolResult.failure("TIMEOUT", f"Tests timed out after {timeout}s")
        except Exception as exc:
            return ToolResult.failure("EXEC_ERROR", str(exc))

        raw = proc.stdout + proc.stderr
        passed = proc.returncode == 0

        # Parse structured output
        failures: List[Dict[str, Any]] = []
        total = passed_count = failed_count = 0
        summary = ""

        if "pytest" in command:
            failures = _parse_pytest_output(raw)
            # Parse summary line: "5 passed, 2 failed in 1.23s"
            m = re.search(r"(\d+) passed", raw)
            if m:
                passed_count = int(m.group(1))
            m = re.search(r"(\d+) failed", raw)
            if m:
                failed_count = int(m.group(1))
            total = passed_count + failed_count
            m = re.search(r"=+ (.+?) =+\s*$", raw, re.MULTILINE)
            summary = m.group(1) if m else ("passed" if passed else "failed")
        elif "npm" in command or "jest" in command:
            failures = _parse_jest_output(raw)
            failed_count = len(failures)
            m = re.search(r"Tests:\s+.*?(\d+) passed", raw)
            if m:
                passed_count = int(m.group(1))
            total = passed_count + failed_count
            summary = "passed" if passed else f"{failed_count} failed"
        else:
            summary = "passed" if passed else f"exit code {proc.returncode}"

        return ToolResult.success(
            data={
                "passed": passed,
                "total": total,
                "passed_count": passed_count,
                "failed_count": failed_count,
                "summary": summary,
                "failures": failures,
                "raw_output": raw,
            },
            message=f"Tests {'passed' if passed else 'FAILED'}: {summary}",
            warnings=[] if passed else [f"{failed_count} test(s) failed"],
        )

    def _detect_command(self) -> Optional[str]:
        import shutil
        if shutil.which("pytest"):
            return "pytest"
        pkg_json = Path(self._workspace_root) / "package.json"
        if pkg_json.exists() and shutil.which("npm"):
            import json
            try:
                pkg = json.loads(pkg_json.read_text())
                if "test" in pkg.get("scripts", {}):
                    return "npm test"
            except Exception:
                pass
        return None
