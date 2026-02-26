from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.core.tool_guard import ToolGuard
from coding_agent.core.tool_result import ToolResult

SCHEMA = {
    "name": "symbols_index",
    "description": (
        "Search for symbols (functions, classes, variables) by name across the workspace. "
        "Uses ripgrep for fast full-repo search combined with AST analysis for Python. "
        "Returns results with file path, line number, symbol kind, and confidence score. "
        "Results are returned within 2 seconds on repos up to 100k lines."
    ),
    "properties": {
        "query": {
            "type": "string",
            "description": "Symbol name to search for (exact or partial match).",
        },
        "lang": {
            "type": "string",
            "description": "Filter by language: 'python' or 'typescript'. Searches all languages if omitted.",
        },
        "exact": {
            "type": "boolean",
            "description": "Require exact name match. Default: false (substring match).",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return. Default: 50.",
        },
    },
    "required": ["query"],
}

Result = Dict[str, Any]

# Python: match def/class/async def at any indent level
_PY_DEF_RE = re.compile(
    r"^(?P<indent>\s*)(?P<kind>async\s+def|def|class)\s+(?P<name>\w+)",
    re.MULTILINE,
)
# TypeScript/JS: function, class, const/let/var declarations
_TS_SYM_RE = re.compile(
    r"^(?P<indent>\s*)(?:export\s+)?(?:async\s+)?(?P<kind>function|class|const|let|var)\s+(?P<name>\w+)",
    re.MULTILINE,
)


def _kind_from_py_match(kind_str: str) -> str:
    if "def" in kind_str:
        return "function"
    return "class"


def _confidence(name: str, query: str, exact: bool) -> float:
    if exact:
        return 1.0 if name == query else 0.0
    if name == query:
        return 1.0
    if name.lower() == query.lower():
        return 0.95
    if query.lower() in name.lower():
        return 0.7
    return 0.0


def _parse_python_file(path: Path, query: str, exact: bool) -> List[Result]:
    """Use AST for accurate Python symbol extraction."""
    results: List[Result] = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except Exception:
        # Fall back to regex on parse failure
        return _parse_with_regex(path, query, exact, _PY_DEF_RE, _kind_from_py_match)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "function"
            name = node.name
        elif isinstance(node, ast.ClassDef):
            kind = "class"
            name = node.name
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    conf = _confidence(target.id, query, exact)
                    if conf > 0:
                        results.append({
                            "symbol": target.id,
                            "file": str(path),
                            "line": node.lineno,
                            "kind": "variable",
                            "confidence": conf,
                        })
            continue
        else:
            continue

        conf = _confidence(name, query, exact)
        if conf > 0:
            results.append({
                "symbol": name,
                "file": str(path),
                "line": node.lineno,
                "kind": kind,
                "confidence": conf,
            })
    return results


def _parse_with_regex(
    path: Path, query: str, exact: bool, pattern: re.Pattern, kind_fn: Any
) -> List[Result]:
    results: List[Result] = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return results
    for lineno, line in enumerate(source.splitlines(), start=1):
        m = pattern.match(line)
        if not m:
            continue
        name = m.group("name")
        conf = _confidence(name, query, exact)
        if conf > 0:
            results.append({
                "symbol": name,
                "file": str(path),
                "line": lineno,
                "kind": kind_fn(m.group("kind")),
                "confidence": conf,
            })
    return results


def _check_rg() -> bool:
    try:
        subprocess.run(["rg", "--version"], capture_output=True, check=True, timeout=5)
        return True
    except Exception:
        return False


def _rg_candidate_files(
    workspace: Path, query: str, lang: Optional[str], exact: bool
) -> List[Path]:
    """Use ripgrep to quickly locate files likely to contain the symbol."""
    pattern = rf"\b{re.escape(query)}\b" if exact else re.escape(query)
    cmd = ["rg", "--files-with-matches", "--max-count=1", pattern, str(workspace)]

    ext_map: Dict[str, List[str]] = {
        "python": ["py"],
        "typescript": ["ts", "tsx", "js", "jsx"],
    }
    if lang and lang in ext_map:
        for ext in ext_map[lang]:
            cmd += ["-g", f"*.{ext}"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        files = [Path(line.strip()) for line in proc.stdout.splitlines() if line.strip()]
        return files
    except Exception:
        return []


class SymbolsIndexTool:
    name = "symbols_index"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = Path(workspace_root).resolve()
        self._rg_available = _check_rg()

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        query: str = args["query"]
        lang: Optional[str] = args.get("lang")
        exact: bool = bool(args.get("exact", False))
        max_results: int = int(args.get("max_results", 50))

        if not query:
            return ToolResult.failure("EMPTY_QUERY", "query must not be empty.")

        # Get candidate files (rg fast path or walk)
        if self._rg_available:
            candidate_files = _rg_candidate_files(self._workspace_root, query, lang, exact)
        else:
            candidate_files = self._walk_files(lang)

        results: List[Result] = []
        py_exts = {".py"}
        ts_exts = {".ts", ".tsx", ".js", ".jsx"}

        for file_path in candidate_files:
            if len(results) >= max_results:
                break
            suffix = file_path.suffix.lower()
            if suffix in py_exts and lang != "typescript":
                file_results = _parse_python_file(file_path, query, exact)
            elif suffix in ts_exts and lang != "python":
                file_results = _parse_with_regex(
                    file_path, query, exact, _TS_SYM_RE,
                    lambda k: "function" if "function" in k else ("class" if k == "class" else "variable"),
                )
            else:
                continue
            results.extend(file_results)

        # Normalize file paths to be relative to workspace
        for r in results:
            p = Path(r["file"])
            try:
                r["file"] = str(p.relative_to(self._workspace_root)).replace("\\", "/")
            except ValueError:
                pass

        # Sort by confidence desc, then file, then line
        results.sort(key=lambda r: (-r["confidence"], r["file"], r["line"]))
        results = results[:max_results]

        return ToolResult.success(
            data={
                "query": query,
                "results": results,
                "result_count": len(results),
            },
            message=f"Found {len(results)} symbol(s) matching '{query}'",
        )

    def _walk_files(self, lang: Optional[str]) -> List[Path]:
        ext_filter: Optional[set] = None
        if lang == "python":
            ext_filter = {".py"}
        elif lang == "typescript":
            ext_filter = {".ts", ".tsx", ".js", ".jsx"}
        files = []
        for p in self._workspace_root.rglob("*"):
            if p.is_file():
                if ext_filter is None or p.suffix.lower() in ext_filter:
                    files.append(p)
        return files
