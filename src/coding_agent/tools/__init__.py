"""
coding_agent.tools
~~~~~~~~~~~~~~~~~~
All tool classes in one place. Import from here so callers don't need to know
individual module paths.

Quick registration example::

    from coding_agent.tools import build_tools

    tools = build_tools(workspace_root="/workspace")
    tool_map = {t.name: t.handler for t in tools}
    schemas  = [t.schema for t in tools]

Legacy API (used by agent.py, llm.py)::

    from coding_agent.tools import get_openai_tools, execute_tool
"""
from __future__ import annotations

from typing import Any, Optional

from coding_agent.tools.base import ToolDefinition
from coding_agent.tools.dependencies_read import DependenciesReadTool
from coding_agent.tools.file_delete import FileDeleteTool
from coding_agent.tools.file_edit import FileEditTool
from coding_agent.tools.file_list import FileListTool
from coding_agent.tools.file_move import FileMoveTool
from coding_agent.tools.file_patch import FilePatchTool
from coding_agent.tools.file_read import FileReadTool
from coding_agent.tools.file_write import FileWriteTool
from coding_agent.tools.git_commit import GitCommitTool
from coding_agent.tools.git_diff import GitDiffTool
from coding_agent.tools.git_status import GitStatusTool
from coding_agent.tools.glob import GlobTool
from coding_agent.tools.grep import GrepTool
from coding_agent.tools.run_lint import RunLintTool
from coding_agent.tools.run_tests import RunTestsTool
from coding_agent.tools.safe_shell import SafeShellTool
from coding_agent.tools.shell import ShellTool
from coding_agent.tools.state_store import StateGetTool, StateSetTool
from coding_agent.tools.symbols_index import SymbolsIndexTool
from coding_agent.tools.typecheck import TypecheckTool
from coding_agent.tools.workspace_info import WorkspaceInfoTool

__all__ = [
    "ToolDefinition",
    "FileReadTool", "FileWriteTool", "FileEditTool", "FilePatchTool",
    "FileListTool", "FileMoveTool", "FileDeleteTool",
    "GlobTool", "GrepTool", "ShellTool", "SafeShellTool",
    "WorkspaceInfoTool",
    "GitStatusTool", "GitDiffTool", "GitCommitTool",
    "RunTestsTool", "RunLintTool", "TypecheckTool",
    "DependenciesReadTool", "SymbolsIndexTool", "StateGetTool", "StateSetTool",
    "build_tools", "get_openai_tools", "execute_tool",
    "register_tool", "tool_registry",
]


def build_tools(
    workspace_root: str,
    policy: Optional[dict[str, Any]] = None,
    safe_shell_config_path: Optional[str] = None,
) -> list[ToolDefinition]:
    p = policy or {}
    # state_get and state_set share a single in-process store per build_tools() call
    _shared_store: dict[str, Any] = {}
    instances = [
        FileReadTool(workspace_root, p),
        FileWriteTool(workspace_root, p),
        FileEditTool(workspace_root, p),
        FilePatchTool(workspace_root, p),
        FileListTool(workspace_root, p),
        FileMoveTool(workspace_root, p),
        FileDeleteTool(workspace_root, p),
        GlobTool(workspace_root, p),
        GrepTool(workspace_root, p),
        ShellTool(workspace_root, p),
        SafeShellTool(workspace_root, p, safe_shell_config_path),
        WorkspaceInfoTool(workspace_root, p),
        GitStatusTool(workspace_root, p),
        GitDiffTool(workspace_root, p),
        GitCommitTool(workspace_root, p),
        RunTestsTool(workspace_root, p),
        RunLintTool(workspace_root, p),
        TypecheckTool(workspace_root, p),
        DependenciesReadTool(workspace_root, p),
        SymbolsIndexTool(workspace_root, p),
        StateSetTool(workspace_root, p, _shared_store),
        StateGetTool(workspace_root, p, _shared_store),
    ]
    return [
        ToolDefinition(
            name=t.name,
            description=t.schema()["description"],
            parameters=t.schema().get("properties", {}),
            handler=t.run,
            schema=t.schema(),
        )
        for t in instances
    ]


# ── Legacy compatibility ───────────────────────────────────────────────────

tool_registry: dict[str, ToolDefinition] = {}


def register_tool(tool: ToolDefinition) -> None:
    tool_registry[tool.name] = tool


def get_openai_tools(
    workspace_root: str,
    policy: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Return OpenAI-format tool schemas and populate tool_registry."""
    tools = build_tools(workspace_root, policy)
    for t in tools:
        tool_registry[t.name] = t
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": {
                    "type": "object",
                    "properties": t.parameters,
                    "required": t.schema.get("required", []),
                },
            },
        }
        for t in tools
    ]


def execute_tool(name: str, args: dict[str, Any]) -> Any:
    """Dispatch a tool call by name. Call get_openai_tools() first."""
    from coding_agent.core.tool_result import ToolResult
    if name not in tool_registry:
        return ToolResult.failure(
            "TOOL_NOT_FOUND",
            f"Tool '{name}' is not registered. Call get_openai_tools() first.",
        )
    return tool_registry[name].handler(args)
