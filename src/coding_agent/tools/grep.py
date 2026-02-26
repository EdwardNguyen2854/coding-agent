from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.core.tool_guard import ToolGuard
from coding_agent.core.tool_result import ToolResult

SCHEMA = {
    "name": "grep",
    "description": (
        "Search inside files using regular expressions. "
        "Uses ripgrep (rg) when available, falls back to Python regex. "
        "Returns matching file paths, line numbers, and matching lines."
    ),
    "properties": {
        "pattern": {"type": "string", "description": "Regular expression to search for."},
        "path": {
            "type": "string",
            "description": "File or directory to search. Defaults to workspace root.",
        },
        "glob": {
            "type": "string",
            "description": "Limit search to files matching this glob pattern, e.g. '*.py'.",
        },
        "case_sensitive": {
            "type": "boolean",
            "description": "Case-sensitive search. Default: true.",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of matching lines to return. Default: 200.",
        },
        "context_lines": {
            "type": "integer",
            "description": "Number of context lines before/after each match. Default: 0.",
        },
    },
    "required": ["pattern"],
}


class GrepTool:
    name = "grep"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = Path(workspace_root).resolve()
        self._rg_available = self._check_rg()

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    @staticmethod
    def _check_rg() -> bool:
        try:
            subprocess.run(["rg", "--version"], capture_output=True, check=True, timeout=5)
            return True
        except Exception:
            return False

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        pattern: str = args["pattern"]
        case_sensitive: bool = bool(args.get("case_sensitive", True))
        max_results: int = int(args.get("max_results", 200))
        context_lines: int = int(args.get("context_lines", 0))
        glob_pattern: Optional[str] = args.get("glob")

        raw_path = args.get("path")
        if raw_path:
            search_path = Path(raw_path)
            if not search_path.is_absolute():
                search_path = (self._workspace_root / search_path).resolve()
            else:
                search_path = search_path.resolve()
        else:
            search_path = self._workspace_root

        if not search_path.exists():
            return ToolResult.failure("PATH_NOT_FOUND", f"Search path does not exist: {search_path}")

        if self._rg_available:
            return self._run_rg(pattern, search_path, case_sensitive, max_results, context_lines, glob_pattern)
        return self._run_python(pattern, search_path, case_sensitive, max_results, context_lines, glob_pattern)

    # ------------------------------------------------------------------ rg

    def _run_rg(
        self,
        pattern: str,
        search_path: Path,
        case_sensitive: bool,
        max_results: int,
        context_lines: int,
        glob_pattern: Optional[str],
    ) -> ToolResult:
        cmd = [
            "rg",
            "--json",
            f"--max-count={max_results}",
            f"--context={context_lines}",
        ]
        if not case_sensitive:
            cmd.append("--ignore-case")
        if glob_pattern:
            cmd += ["--glob", glob_pattern]
        cmd += [pattern, str(search_path)]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return ToolResult.failure("TIMEOUT", "grep timed out after 30 seconds")
        except Exception as exc:
            return ToolResult.failure("RG_ERROR", str(exc))

        matches: List[Dict[str, Any]] = []
        files_matched: set = set()

        import json as _json
        for line in proc.stdout.splitlines():
            try:
                obj = _json.loads(line)
            except Exception:
                continue
            if obj.get("type") == "match":
                data = obj["data"]
                p = Path(data["path"]["text"])
                if not p.is_absolute():
                    p = (search_path / p).resolve()
                rel = str(p.relative_to(self._workspace_root)).replace("\\", "/")
                match_entry = {
                    "file": rel,
                    "line_number": data["line_number"],
                    "line": data["lines"]["text"].rstrip("\n"),
                    "submatches": [
                        {"start": sm["start"], "end": sm["end"], "match": sm["match"]["text"]}
                        for sm in data.get("submatches", [])
                    ],
                }
                matches.append(match_entry)
                files_matched.add(rel)

        return ToolResult.success(
            data={
                "pattern": pattern,
                "matches": matches,
                "match_count": len(matches),
                "files_matched": sorted(files_matched),
                "parser_used": "ripgrep",
            },
            message=f"Found {len(matches)} match(es) across {len(files_matched)} file(s)",
        )

    # ---------------------------------------------------------- python fallback

    def _run_python(
        self,
        pattern: str,
        search_path: Path,
        case_sensitive: bool,
        max_results: int,
        context_lines: int,
        glob_pattern: Optional[str],
    ) -> ToolResult:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as exc:
            return ToolResult.failure("INVALID_REGEX", f"Invalid regex pattern: {exc}")

        # Collect files to search
        if search_path.is_file():
            files = [search_path]
        else:
            if glob_pattern:
                files = list(search_path.rglob(glob_pattern))
            else:
                files = [p for p in search_path.rglob("*") if p.is_file()]

        matches: List[Dict[str, Any]] = []
        files_matched: set = set()
        truncated = False

        for file_path in sorted(files):
            if truncated:
                break
            try:
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines):
                if regex.search(line):
                    rel = str(file_path.relative_to(self._workspace_root))
                    # Context
                    ctx_start = max(0, i - context_lines)
                    ctx_end = min(len(lines), i + context_lines + 1)
                    context = lines[ctx_start:ctx_end]
                    matches.append({
                        "file": rel,
                        "line_number": i + 1,
                        "line": line,
                        "context": context if context_lines > 0 else None,
                    })
                    files_matched.add(rel)
                    if len(matches) >= max_results:
                        truncated = True
                        break

        warnings = []
        if truncated:
            warnings.append(f"Results truncated at {max_results}.")

        return ToolResult.success(
            data={
                "pattern": pattern,
                "matches": matches,
                "match_count": len(matches),
                "files_matched": sorted(files_matched),
                "truncated": truncated,
                "parser_used": "python_re",
            },
            message=f"Found {len(matches)} match(es) across {len(files_matched)} file(s)",
            warnings=warnings,
        )
