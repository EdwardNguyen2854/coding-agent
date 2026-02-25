from __future__ import annotations

from typing import Any, Dict, Optional

from coding_agent.tool_guard import ToolGuard
from coding_agent.tool_result import ToolResult

STATE_SET_SCHEMA = {
    "name": "state_set",
    "description": (
        "Store a JSON-serializable value under a key for the current session. "
        "State is scoped to this agent session and is not persisted across restarts. "
        "Different sessions never share state. Use sparingly — prefer scaffolding-level state "
        "when available, as in-tool state creates subtle bugs when conversations are replayed."
    ),
    "properties": {
        "key": {
            "type": "string",
            "description": "State key. Must be a non-empty string.",
        },
        "value": {
            "description": "Any JSON-serializable value to store.",
        },
    },
    "required": ["key", "value"],
}

STATE_GET_SCHEMA = {
    "name": "state_get",
    "description": (
        "Retrieve a value previously stored with state_set. "
        "Returns found=false (not an error) when the key is missing."
    ),
    "properties": {
        "key": {
            "type": "string",
            "description": "State key to look up.",
        },
    },
    "required": ["key"],
}

# Session-level store: maps (session_id, key) → value.
# Using a class-level dict ensures different SymbolsIndexTool instances
# get isolated stores when constructed independently (separate sessions).
_SENTINEL = object()


class StateSetTool:
    name = "state_set"

    def __init__(
        self,
        workspace_root: str,
        policy: Optional[Dict[str, Any]] = None,
        _store: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        # _store is injected at construction so get/set share the same dict
        self._store: Dict[str, Any] = _store if _store is not None else {}

    def schema(self) -> Dict[str, Any]:
        return STATE_SET_SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=STATE_SET_SCHEMA)
        if blocked is not None:
            return blocked

        key: str = args["key"]
        if not key:
            return ToolResult.failure("INVALID_KEY", "Key must be a non-empty string.")

        value = args["value"]
        # Validate JSON-serializability
        import json
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            return ToolResult.failure("NOT_SERIALIZABLE", f"Value is not JSON-serializable: {exc}")

        self._store[key] = value
        return ToolResult.success(
            data={"key": key, "stored": True},
            message=f"Stored key '{key}'",
        )


class StateGetTool:
    name = "state_get"

    def __init__(
        self,
        workspace_root: str,
        policy: Optional[Dict[str, Any]] = None,
        _store: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._store: Dict[str, Any] = _store if _store is not None else {}

    def schema(self) -> Dict[str, Any]:
        return STATE_GET_SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=STATE_GET_SCHEMA)
        if blocked is not None:
            return blocked

        key: str = args["key"]
        value = self._store.get(key, _SENTINEL)
        found = value is not _SENTINEL

        return ToolResult.success(
            data={
                "key": key,
                "value": value if found else None,
                "found": found,
            },
            message=f"Key '{key}' {'found' if found else 'not found'}",
        )
