import datetime
import json
from pathlib import Path
from typing import Any, Dict, Optional

from coding_agent.tool_result import ToolResult


class ToolGuard:
    def __init__(
        self,
        workspace_root: str,
        policy: Dict[str, Any],
        log_path: Optional[str] = None,
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.policy = policy
        self._log_path = log_path

    def check(
        self,
        tool_name: str,
        args: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
    ) -> Optional[ToolResult]:
        # 1. Check deny_tools list
        deny_tools = self.policy.get("deny_tools", [])
        if tool_name in deny_tools:
            result = ToolResult.failure(
                "DENIED_BY_POLICY", f"Tool '{tool_name}' is denied by policy."
            )
            self._log(tool_name, result)
            return result

        # 2. Check deny_actions
        deny_actions = self.policy.get("deny_actions", {})
        if deny_actions.get(tool_name):
            result = ToolResult.failure(
                "DENIED_BY_POLICY", f"Action '{tool_name}' is denied by policy."
            )
            self._log(tool_name, result)
            return result

        # 3. Validate args against schema
        if schema is not None:
            error = self._validate(args, schema)
            if error:
                result = ToolResult.failure("INVALID_ARGS", error)
                self._log(tool_name, result)
                return result

        # 4. Check path traversal for any 'path' argument (skip multiline values)
        if "path" in args:
            path_arg = args["path"]
            if isinstance(path_arg, str) and "\n" not in path_arg:
                try:
                    resolved = (self.workspace_root / path_arg).resolve()
                    resolved.relative_to(self.workspace_root)
                except ValueError:
                    result = ToolResult.failure(
                        "PATH_OUTSIDE_WORKSPACE",
                        f"Path '{path_arg}' resolves outside the workspace.",
                    )
                    self._log(tool_name, result)
                    return result

        self._log(tool_name, None)
        return None  # All checks passed

    def _log(self, tool_name: str, result: Optional[ToolResult]) -> None:
        if self._log_path is None:
            return
        entry = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "tool_name": tool_name,
            "denied": result is not None and not result.ok,
            "error_code": result.error_code if result is not None else None,
        }
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _validate(self, args: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
        """Minimal JSON-schema-style validation (type + required)."""
        required = schema.get("required", [])
        for field in required:
            if field not in args:
                return f"Missing required field: '{field}'"

        properties = schema.get("properties", {})
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        for key, value in args.items():
            if key in properties:
                expected_type = properties[key].get("type")
                if expected_type and expected_type in type_map:
                    if not isinstance(value, type_map[expected_type]):
                        return (
                            f"Field '{key}' expected type '{expected_type}', "
                            f"got {type(value).__name__}."
                        )
        return None
