"""Spawn sub-agent tool — delegates a focused task to a specialized sub-agent."""
from __future__ import annotations

from typing import Any

from coding_agent.core.tool_result import ToolResult

SCHEMA = {
    "name": "spawn_sub_agent",
    "description": (
        "Delegate a focused task to a specialized sub-agent. "
        "The sub-agent receives only the provided context (not the full conversation history), "
        "runs the task, and returns its result. "
        "Use this to assign work to specialists (e.g. 'reviewer', 'backend-dev', 'tester'). "
        "Only available in team mode — enable with /agent team-mode on."
    ),
    "properties": {
        "name": {
            "type": "string",
            "description": "Sub-agent identifier, e.g. 'reviewer', 'backend-dev'. Reused if name already exists.",
        },
        "role": {
            "type": "string",
            "description": "Sub-agent role/persona used as its system prompt, e.g. 'Expert Python code reviewer'.",
        },
        "task": {
            "type": "string",
            "description": "Task description to give the sub-agent.",
        },
        "context": {
            "type": "string",
            "description": "Optional relevant context (code snippets, file contents, etc.) to pass to the sub-agent.",
        },
    },
    "required": ["name", "role", "task"],
}

# Module-level state — populated by setup_spawn_sub_agent() and update_session_data()
_llm_client = None
_session_manager = None
_session_data: dict[str, Any] | None = None
_config = None
_workspace_root: str | None = None
_renderer = None
_team_mode: bool = False
_active_sub_agent_name: str | None = None  # set while a sub-agent is running


def get_active_sub_agent_name() -> str | None:
    """Return the name of the currently running sub-agent, or None."""
    return _active_sub_agent_name


def setup_spawn_sub_agent(llm_client, session_manager, config, workspace_root, renderer) -> None:
    """Initialize the spawn_sub_agent tool with runtime dependencies."""
    global _llm_client, _session_manager, _config, _workspace_root, _renderer
    _llm_client = llm_client
    _session_manager = session_manager
    _config = config
    _workspace_root = workspace_root
    _renderer = renderer


def update_session_data(session_data: dict[str, Any] | None) -> None:
    """Update the current session data reference (called after session creation)."""
    global _session_data
    _session_data = session_data


def set_team_mode(enabled: bool) -> None:
    """Enable or disable team mode."""
    global _team_mode
    _team_mode = enabled


def is_team_mode() -> bool:
    """Return True if team mode is active."""
    return _team_mode


class SpawnSubAgentTool:
    name = "spawn_sub_agent"

    def schema(self) -> dict[str, Any]:
        return SCHEMA

    def run(self, args: dict[str, Any]) -> ToolResult:
        if not _team_mode:
            return ToolResult.failure(
                "TEAM_MODE_DISABLED",
                "spawn_sub_agent is only available in team mode. Enable it with: /agent team-mode on",
            )

        if _llm_client is None or _session_manager is None:
            return ToolResult.failure(
                "NOT_INITIALIZED",
                "spawn_sub_agent tool is not properly initialized.",
            )

        if _session_data is None:
            return ToolResult.failure(
                "NO_SESSION",
                "No active session. Send a message first to create a session.",
            )

        name: str = args["name"]
        role: str = args["role"]
        task: str = args["task"]
        context: str = args.get("context", "")

        session_id = _session_data["id"]

        # Reuse existing sub-agent or create a new one
        sub_agent = _session_manager.get_sub_agent_by_name(session_id, name)
        if sub_agent is None:
            sub_agent = _session_manager.add_sub_agent(session_id, name, role)

        sub_agent_id = sub_agent["id"]

        # Build a fresh conversation for the sub-agent
        from coding_agent.core.conversation import ConversationManager
        model = _config.model if _config else "gpt-4"
        sub_conversation = ConversationManager(system_prompt=role, model=model)

        if context:
            sub_conversation.add_message("user", f"Context:\n{context}")
            sub_conversation.add_message("assistant", "Understood. I have the context. What would you like me to do?")

        # Visual separator
        if _renderer:
            _renderer.print_info(f"--- Sub-agent: {name} [{role}] ---")

        # Create and run the sub-agent (reuses the global tool_registry — no re-registration needed)
        from coding_agent.core.agent import Agent
        sub_agent_instance = Agent(
            llm_client=_llm_client,
            conversation=sub_conversation,
            renderer=_renderer,
            config=_config,
            workspace_root=_workspace_root,
        )

        global _active_sub_agent_name
        _active_sub_agent_name = name
        try:
            result = sub_agent_instance.run(task)
        except Exception as exc:
            _active_sub_agent_name = None
            if _renderer:
                _renderer.print_error(f"--- Sub-agent {name} failed ---")
            return ToolResult.failure("SUB_AGENT_ERROR", f"Sub-agent '{name}' encountered an error: {exc}")
        finally:
            _active_sub_agent_name = None

        # Print result summary
        if _renderer and result:
            from rich.panel import Panel
            from rich.text import Text
            summary_text = result[:400] + ("…" if len(result) > 400 else "")
            _renderer.console.print(
                Panel(
                    Text(summary_text),
                    title=f"[bold cyan]Sub-agent: {name}[/] — done",
                    border_style="cyan",
                    expand=False,
                )
            )
        elif _renderer:
            _renderer.print_info(f"--- Sub-agent {name} done (no output) ---")

        # Persist sub-agent messages to DB
        sub_messages = sub_conversation.get_messages()
        # Skip the system prompt (first message) when saving — it's the role definition
        new_messages = sub_messages[1:] if len(sub_messages) > 1 else []
        if new_messages:
            _session_manager.save(_session_data, new_messages=new_messages, sub_agent_id=sub_agent_id)

        return ToolResult.success(
            data={"sub_agent": name, "result": result},
            message=result or f"Sub-agent '{name}' completed the task.",
        )
