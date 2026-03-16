"""Spawn sub-agent tool — delegates a focused task to a specialized sub-agent."""
from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class SubAgentContext:
    """Runtime dependencies for the spawn_sub_agent tool.

    Collected into a single object so callers inject one argument instead of
    eight module-level globals.  Thread-safety note: mutations to this object
    (e.g. session_data updates) must not race with concurrent tool invocations;
    the caller is responsible for synchronisation if sub-agents run in parallel.
    """

    llm_client: Any = None
    session_manager: Any = None
    session_data: dict[str, Any] | None = None
    config: Any = None
    workspace_root: str | None = None
    renderer: Any = None
    team_mode: bool = False
    active_sub_agent_name: str | None = None


# Single module-level context object — replaces eight individual globals.
_context = SubAgentContext()


def get_active_sub_agent_name() -> str | None:
    """Return the name of the currently running sub-agent, or None."""
    return _context.active_sub_agent_name


def setup_spawn_sub_agent(llm_client, session_manager, config, workspace_root, renderer) -> None:
    """Initialize the spawn_sub_agent tool with runtime dependencies."""
    _context.llm_client = llm_client
    _context.session_manager = session_manager
    _context.config = config
    _context.workspace_root = workspace_root
    _context.renderer = renderer


def update_session_data(session_data: dict[str, Any] | None) -> None:
    """Update the current session data reference (called after session creation)."""
    _context.session_data = session_data


def set_team_mode(enabled: bool) -> None:
    """Enable or disable team mode."""
    _context.team_mode = enabled


def is_team_mode() -> bool:
    """Return True if team mode is active."""
    return _context.team_mode


class SpawnSubAgentTool:
    name = "spawn_sub_agent"

    def __init__(self, context: SubAgentContext | None = None) -> None:
        """Initialise the tool.

        Args:
            context: Dependency context.  When *None* the module-level
                     ``_context`` singleton is used (backward-compatible default).
        """
        self._ctx = context if context is not None else _context

    def schema(self) -> dict[str, Any]:
        return SCHEMA

    def run(self, args: dict[str, Any]) -> ToolResult:
        """Delegate a task to a named sub-agent and return its result.

        Creates (or reuses) a sub-agent with the given ``name`` and ``role``,
        runs the ``task``, persists the sub-agent conversation to the session
        DB, and returns the textual result.

        Error recovery: any exception raised by the sub-agent's ``run()`` is
        caught and returned as a ``SUB_AGENT_ERROR`` failure so the parent
        agent can decide whether to retry or surface the error to the user.

        Args:
            args: Tool arguments — ``name``, ``role``, ``task``, optional ``context``.

        Returns:
            ToolResult with ``data["sub_agent"]`` and ``data["result"]`` on success.
        """
        ctx = self._ctx
        if not ctx.team_mode:
            return ToolResult.failure(
                "TEAM_MODE_DISABLED",
                "spawn_sub_agent is only available in team mode. Enable it with: /agent team-mode on",
            )

        if ctx.llm_client is None or ctx.session_manager is None:
            return ToolResult.failure(
                "NOT_INITIALIZED",
                "spawn_sub_agent tool is not properly initialized.",
            )

        if ctx.session_data is None:
            return ToolResult.failure(
                "NO_SESSION",
                "No active session. Send a message first to create a session.",
            )

        name: str = args["name"]
        role: str = args["role"]
        task: str = args["task"]
        context: str = args.get("context", "")

        session_id = ctx.session_data["id"]

        # Reuse existing sub-agent or create a new one
        sub_agent = ctx.session_manager.get_sub_agent_by_name(session_id, name)
        if sub_agent is None:
            sub_agent = ctx.session_manager.add_sub_agent(session_id, name, role)

        sub_agent_id = sub_agent["id"]

        # Build a fresh conversation for the sub-agent
        from coding_agent.core.conversation import ConversationManager
        model = ctx.config.model if ctx.config else "gpt-4"
        sub_conversation = ConversationManager(system_prompt=role, model=model)

        if context:
            sub_conversation.add_message("user", f"Context:\n{context}")
            sub_conversation.add_message("assistant", "Understood. I have the context. What would you like me to do?")

        # Visual separator
        if ctx.renderer:
            ctx.renderer.print_info(f"--- Sub-agent: {name} [{role}] ---")

        # Create and run the sub-agent (reuses the global tool_registry — no re-registration needed)
        from coding_agent.core.agent import Agent
        sub_agent_instance = Agent(
            llm_client=ctx.llm_client,
            conversation=sub_conversation,
            renderer=ctx.renderer,
            config=ctx.config,
            workspace_root=ctx.workspace_root,
        )

        ctx.active_sub_agent_name = name
        try:
            result = sub_agent_instance.run(task)
        except Exception as exc:
            ctx.active_sub_agent_name = None
            if ctx.renderer:
                ctx.renderer.print_error(f"--- Sub-agent {name} failed ---")
            return ToolResult.failure("SUB_AGENT_ERROR", f"Sub-agent '{name}' encountered an error: {exc}")
        finally:
            ctx.active_sub_agent_name = None

        # Print result summary
        if ctx.renderer and result:
            from rich.panel import Panel
            from rich.text import Text
            summary_text = result[:400] + ("…" if len(result) > 400 else "")
            ctx.renderer.console.print(
                Panel(
                    Text(summary_text),
                    title=f"[bold blue]Sub-agent: {name}[/] — done",
                    border_style="blue",
                    expand=False,
                )
            )
        elif ctx.renderer:
            ctx.renderer.print_info(f"--- Sub-agent {name} done (no output) ---")

        # Persist sub-agent messages to DB
        sub_messages = sub_conversation.get_messages()
        # Skip the system prompt (first message) when saving — it's the role definition
        new_messages = sub_messages[1:] if len(sub_messages) > 1 else []
        if new_messages:
            ctx.session_manager.save(ctx.session_data, new_messages=new_messages, sub_agent_id=sub_agent_id)

        return ToolResult.success(
            data={"sub_agent": name, "result": result},
            message=result or f"Sub-agent '{name}' completed the task.",
        )
