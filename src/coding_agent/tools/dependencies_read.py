from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.tool_guard import ToolGuard
from coding_agent.tool_result import ToolResult

SCHEMA = {
    "name": "dependencies_read",
    "description": (
        "Parse dependency files in the workspace and return structured dependency lists. "
        "Supports pyproject.toml, requirements.txt, and package.json. "
        "Returns separate lists for runtime and dev dependencies."
    ),
    "properties": {
        "path": {
            "type": "string",
            "description": "File to parse, or directory to search for dependency files. "
                           "Defaults to workspace root.",
        },
    },
    "required": [],
}

Dep = Dict[str, Any]


def _parse_requirements_txt(text: str) -> List[Dep]:
    deps: List[Dep] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "-r", "-c", "--")):
            continue
        # Strip inline comments
        line = re.split(r"\s+#", line)[0].strip()
        # Parse name + version specifier
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*([><=!~^][^\s;]*)?", line)
        if m:
            deps.append({
                "name": m.group(1),
                "version": m.group(2) or "",
                "dev": False,
            })
    return deps


def _parse_pyproject_toml(text: str) -> tuple[List[Dep], List[Dep], str]:
    """Returns (deps, dev_deps, format_label)."""
    try:
        import tomllib  # Python 3.11+
        data = tomllib.loads(text)
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
            data = tomllib.loads(text)
        except ImportError:
            # Minimal fallback: regex extraction
            return _parse_pyproject_toml_regex(text)

    deps: List[Dep] = []
    dev_deps: List[Dep] = []

    # PEP 517 / flit / setuptools style
    project = data.get("project", {})
    for spec in project.get("dependencies", []):
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*([><=!~^][^\s;]*)?", spec)
        if m:
            deps.append({"name": m.group(1), "version": m.group(2) or "", "dev": False})

    opt_deps = project.get("optional-dependencies", {})
    for group, specs in opt_deps.items():
        is_dev = group.lower() in ("dev", "test", "tests", "lint", "typing", "ci")
        for spec in specs:
            m = re.match(r"^([A-Za-z0-9_.\-]+)\s*([><=!~^][^\s;]*)?", spec)
            if m:
                entry = {"name": m.group(1), "version": m.group(2) or "", "dev": is_dev}
                (dev_deps if is_dev else deps).append(entry)

    # Poetry style
    tool_poetry = data.get("tool", {}).get("poetry", {})
    for spec_name, spec_val in tool_poetry.get("dependencies", {}).items():
        if spec_name == "python":
            continue
        version = spec_val if isinstance(spec_val, str) else spec_val.get("version", "")
        deps.append({"name": spec_name, "version": version, "dev": False})

    for spec_name, spec_val in tool_poetry.get("dev-dependencies", {}).items():
        version = spec_val if isinstance(spec_val, str) else spec_val.get("version", "")
        dev_deps.append({"name": spec_name, "version": version, "dev": True})

    # poetry group dependencies
    for group_name, group_data in tool_poetry.get("group", {}).items():
        is_dev = group_name.lower() in ("dev", "test", "tests", "lint")
        for spec_name, spec_val in group_data.get("dependencies", {}).items():
            version = spec_val if isinstance(spec_val, str) else spec_val.get("version", "")
            entry = {"name": spec_name, "version": version, "dev": is_dev}
            (dev_deps if is_dev else deps).append(entry)

    return deps, dev_deps, "pyproject.toml"


def _parse_pyproject_toml_regex(text: str) -> tuple[List[Dep], List[Dep], str]:
    """Minimal regex fallback when tomllib/tomli not available."""
    deps: List[Dep] = []
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "dependencies = [":
            in_deps = True
            continue
        if in_deps:
            if stripped == "]":
                in_deps = False
                continue
            spec = stripped.strip('",')
            m = re.match(r"^([A-Za-z0-9_.\-]+)\s*([><=!~^][^\s;]*)?", spec)
            if m:
                deps.append({"name": m.group(1), "version": m.group(2) or "", "dev": False})
    return deps, [], "pyproject.toml"


def _parse_package_json(text: str) -> tuple[List[Dep], List[Dep]]:
    try:
        data = json.loads(text)
    except Exception:
        return [], []
    deps: List[Dep] = []
    dev_deps: List[Dep] = []
    for name, version in data.get("dependencies", {}).items():
        deps.append({"name": name, "version": version, "dev": False})
    for name, version in data.get("devDependencies", {}).items():
        dev_deps.append({"name": name, "version": version, "dev": True})
    return deps, dev_deps


class DependenciesReadTool:
    name = "dependencies_read"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = Path(workspace_root).resolve()

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        raw_path = args.get("path")
        if raw_path:
            target = Path(raw_path)
            if not target.is_absolute():
                target = (self._workspace_root / target).resolve()
        else:
            target = self._workspace_root

        # If target is a file, parse it directly
        if target.is_file():
            return self._parse_file(target)

        # Search for dependency files in directory
        candidates = [
            target / "pyproject.toml",
            target / "requirements.txt",
            target / "package.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return self._parse_file(candidate)

        return ToolResult.failure(
            "NO_DEPENDENCY_FILE",
            f"No supported dependency file found in '{target}'. "
            "Expected: pyproject.toml, requirements.txt, or package.json.",
        )

    def _parse_file(self, path: Path) -> ToolResult:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult.failure("READ_ERROR", str(exc))

        name = path.name.lower()
        if name == "pyproject.toml":
            deps, dev_deps, fmt = _parse_pyproject_toml(text)
        elif name == "requirements.txt":
            deps = _parse_requirements_txt(text)
            dev_deps = []
            fmt = "requirements.txt"
        elif name == "package.json":
            deps, dev_deps = _parse_package_json(text)
            fmt = "package.json"
        else:
            return ToolResult.failure(
                "UNSUPPORTED_FORMAT",
                f"Unsupported dependency file: '{path.name}'. "
                "Supported: pyproject.toml, requirements.txt, package.json.",
            )

        return ToolResult.success(
            data={
                "format": fmt,
                "file": str(path),
                "dependencies": deps,
                "dev_dependencies": dev_deps,
                "total_count": len(deps) + len(dev_deps),
            },
            message=f"Parsed {len(deps)} runtime and {len(dev_deps)} dev dependencies from {path.name}",
        )
