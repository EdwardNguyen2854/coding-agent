"""Bottom toolbar content for the prompt session."""

import shutil

from coding_agent.workflow import Workflow, WorkflowState


DEFAULT_CONTEXT_LIMIT = 128000
_CTX_CRITICAL = 90
_CTX_WARNING = 70
_CTX_BAR_WIDTH = 10

_WORKFLOW_STYLE_MAP = {
    WorkflowState.AWAITING_PLAN: "fg:ansibrightyellow",
    WorkflowState.PLAN_CREATED: "fg:ansibrightblue",
    WorkflowState.AWAITING_APPROVAL: "fg:ansibrightmagenta",
    WorkflowState.EXECUTING: "fg:ansibrightgreen",
    WorkflowState.COMPLETED: "fg:ansibrightgreen",
}

_SEP = ("fg:#555555", "  │  ")


def _make_context_bar(percentage: float, width: int = _CTX_BAR_WIDTH) -> str:
    """Create a visual fill bar for context usage.

    Args:
        percentage: Context usage as a percentage (0–100).
        width: Total bar width in characters.

    Returns:
        A string of ``▓`` (filled) and ``░`` (empty) characters, e.g. ``▓▓▓▓░░░░``.
    """
    filled = min(width, round((percentage / 100) * width))
    return "▓" * filled + "░" * (width - filled)


def make_toolbar(
    conversation: object,
    workflow: "Workflow | None",
    branch: str,
    context_limit: int = DEFAULT_CONTEXT_LIMIT,
    get_active_sub_agent: "object | None" = None,
    get_model: "object | None" = None,
    get_team_mode: "object | None" = None,
):
    """Create a bottom_toolbar callable for use with prompt_toolkit PromptSession.

    Returns a callable that reads the current state each time the prompt
    redraws, so the toolbar stays up-to-date without manual refreshes.

    Args:
        conversation: ConversationManager with a ``token_count`` attribute.
        workflow: Active Workflow instance (or None).
        branch: Current git branch name.
        context_limit: Maximum context tokens.
        get_active_sub_agent: Callable returning the active sub-agent name or None.
        get_model: Callable returning the current model name string, or None.
        get_team_mode: Callable returning True when team mode is active, or None.

    Returns:
        A callable that returns a list of (style, text) tuples (FormattedText).
    """

    def _toolbar() -> list[tuple[str, str]]:
        token_count = getattr(conversation, "token_count", 0)
        percentage = (token_count / context_limit) * 100

        if percentage > _CTX_CRITICAL:
            ctx_style = "fg:ansibrightred bold"
        elif percentage > _CTX_WARNING:
            ctx_style = "fg:ansibrightyellow"
        else:
            ctx_style = "fg:ansibrightgreen"

        parts: list[tuple[str, str]] = [("", " ")]

        # Sub-agent indicator — shown prominently when active
        active_sub_agent = get_active_sub_agent() if get_active_sub_agent is not None else None
        if active_sub_agent:
            parts += [
                ("fg:ansibrightmagenta bold", f"◈ {active_sub_agent.capitalize()}"),
                _SEP,
            ]

        # Model name
        model_name = get_model() if get_model is not None else None
        if model_name:
            short_model = model_name.split("/")[-1] if "/" in model_name else model_name
            parts += [
                ("fg:ansicyan", f"◉ {short_model}"),
                _SEP,
            ]

        # Team mode indicator
        team_mode = get_team_mode() if get_team_mode is not None else False
        if team_mode:
            parts += [
                ("fg:ansibrightyellow bold", "⚡ TEAM"),
                _SEP,
            ]

        # Context usage bar
        ctx_bar = _make_context_bar(percentage)
        parts += [
            ("fg:#888888", "ctx "),
            (ctx_style, ctx_bar),
            ("fg:#888888", f" {percentage:.0f}%"),
            _SEP,
        ]

        # Git branch — dim when unknown
        branch_style = "fg:#888888" if branch in ("N/A", "", "unknown") else "fg:ansiwhite"
        parts += [
            (branch_style, f"⎇  {branch}"),
        ]

        # Workflow state
        if workflow and workflow.state != WorkflowState.IDLE:
            wf_style = _WORKFLOW_STYLE_MAP.get(workflow.state, "")
            parts += [
                _SEP,
                (wf_style, f"● {workflow.state.value}"),
            ]

        # Todo progress
        if workflow and workflow.todo_list.total > 0:
            todos = workflow.todo_list
            in_progress = next(
                (i for i in todos.items if i.status.value == "in_progress"), None
            )
            blocked_count = len(todos.get_blocked())
            summary = f"{todos.completed_count}/{todos.total}"
            if blocked_count:
                summary += f" ✗{blocked_count}"
            if in_progress:
                desc = in_progress.description
                label = desc[:28] + "…" if len(desc) > 28 else desc
                parts += [
                    _SEP,
                    ("fg:ansibrightcyan", f"✦ {summary}"),
                    ("fg:#888888", f"  ▶ {label}"),
                ]
            else:
                parts += [
                    _SEP,
                    ("fg:ansibrightcyan", f"✦ {summary}"),
                ]

        parts.append(("", " "))
        return parts

    return _toolbar


