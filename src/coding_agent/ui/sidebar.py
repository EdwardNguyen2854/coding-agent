"""Bottom toolbar content for the prompt session."""

import shutil

from coding_agent.workflow import Workflow, WorkflowState


DEFAULT_CONTEXT_LIMIT = 128000
_CTX_CRITICAL = 90
_CTX_WARNING = 70
_CTX_BAR_WIDTH = 8

_WORKFLOW_STYLE_MAP = {
    WorkflowState.AWAITING_PLAN: "fg:ansiyellow",
    WorkflowState.PLAN_CREATED: "fg:ansiblue",
    WorkflowState.AWAITING_APPROVAL: "fg:ansimagenta",
    WorkflowState.EXECUTING: "fg:ansigreen",
    WorkflowState.COMPLETED: "fg:ansigreen",
}


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

    Returns:
        A callable that returns a list of (style, text) tuples (FormattedText).
    """

    def _toolbar() -> list[tuple[str, str]]:
        token_count = getattr(conversation, "token_count", 0)
        percentage = (token_count / context_limit) * 100

        if percentage > _CTX_CRITICAL:
            ctx_style = "fg:ansired"
        elif percentage > _CTX_WARNING:
            ctx_style = "fg:ansiyellow"
        else:
            ctx_style = "fg:ansigreen"

        parts: list[tuple[str, str]] = []

        # Sub-agent indicator goes first when active
        active_sub_agent = get_active_sub_agent() if get_active_sub_agent is not None else None
        if active_sub_agent:
            parts += [
                ("fg:ansimagenta bold", f"  Sub-agent: {active_sub_agent.capitalize()}"),
                ("", " | "),
            ]
        else:
            parts.append(("", "  "))

        model_name = get_model() if get_model is not None else None
        if model_name:
            # Show only the last segment of the model name (e.g. "gpt-4o" from "litellm/gpt-4o")
            short_model = model_name.split("/")[-1] if "/" in model_name else model_name
            parts += [
                ("fg:ansiblue", short_model),
                ("", "  │  "),
            ]

        ctx_bar = _make_context_bar(percentage)
        parts += [
            ("", f"Context: {token_count:,} "),
            (ctx_style, f"{ctx_bar} ({percentage:.1f}%)"),
            ("", "  │  "),
            ("", f"Branch: {branch}"),
        ]

        if workflow and workflow.state != WorkflowState.IDLE:
            wf_style = _WORKFLOW_STYLE_MAP.get(workflow.state, "")
            parts += [
                ("", "  │  "),
                (wf_style, f"● {workflow.state.value}"),
            ]

        if workflow and workflow.todo_list.total > 0:
            todos = workflow.todo_list
            in_progress = next(
                (i for i in todos.items if i.status.value == "in_progress"), None
            )
            blocked_count = len(todos.get_blocked())
            summary = f"{todos.completed_count}/{todos.total}"
            if blocked_count:
                summary += f"  ✗{blocked_count}"
            if in_progress:
                desc = in_progress.description
                label = desc[:30] + "…" if len(desc) > 30 else desc
                parts += [
                    ("", "  │  "),
                    ("", f"Todos: {summary}  ▶ {label}"),
                ]
            else:
                parts += [
                    ("", "  │  "),
                    ("", f"Todos: {summary}"),
                ]

        parts.append(("", "  "))
        return parts

    return _toolbar


