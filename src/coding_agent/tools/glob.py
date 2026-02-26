from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.core.tool_guard import ToolGuard
from coding_agent.core.tool_result import ToolResult

SCHEMA = {
    "name": "glob",
    "description": (
        "Search for files in the workspace using a glob pattern. "
        "Returns matching file paths sorted alphabetically."
    ),
    "properties": {
        "pattern": {
            "type": "string",
            "description": "Glob pattern, e.g. '**/*.py', 'src/**/*.ts', '*.json'.",
        },
        "base_path": {
            "type": "string",
            "description": "Directory to search from. Defaults to workspace root.",
        },
        "include_hidden": {
            "type": "boolean",
            "description": "Include files/dirs starting with '.'. Default: false.",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return. Default: 500.",
        },
    },
    "required": ["pattern"],
}


class GlobTool:
    name = "glob"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = Path(workspace_root).resolve()

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        pattern: str = args["pattern"]
        include_hidden: bool = bool(args.get("include_hidden", False))
        max_results: int = int(args.get("max_results", 500))

        base_raw = args.get("base_path")
        if base_raw:
            base = Path(base_raw)
            if not base.is_absolute():
                base = (self._workspace_root / base).resolve()
            else:
                base = base.resolve()
        else:
            base = self._workspace_root

        if not base.exists():
            return ToolResult.failure("DIR_NOT_FOUND", f"Base path does not exist: {base}")

        try:
            all_matches: List[str] = []
            truncated = False

            for p in sorted(base.glob(pattern)):
                # Skip hidden files/dirs unless requested
                if not include_hidden:
                    parts = p.relative_to(base).parts
                    if any(part.startswith(".") for part in parts):
                        continue

                rel = str(p.relative_to(self._workspace_root))
                all_matches.append(rel)

                if len(all_matches) >= max_results:
                    truncated = True
                    break

        except Exception as exc:
            return ToolResult.failure("GLOB_ERROR", f"Glob failed: {exc}")

        warnings = []
        if truncated:
            warnings.append(
                f"Results truncated at {max_results}. Use a more specific pattern or increase max_results."
            )

        return ToolResult.success(
            data={
                "pattern": pattern,
                "base_path": str(base),
                "matches": all_matches,
                "count": len(all_matches),
                "truncated": truncated,
            },
            message=f"Found {len(all_matches)} match(es) for '{pattern}'",
            warnings=warnings,
        )
