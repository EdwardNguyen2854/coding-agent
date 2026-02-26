"""Bottom toolbar content for the prompt session."""

from coding_agent.workflow import Workflow, WorkflowState


DEFAULT_CONTEXT_LIMIT = 128000
_CTX_CRITICAL = 90
_CTX_WARNING = 70

_WORKFLOW_STYLE_MAP = {
    WorkflowState.AWAITING_PLAN: "fg:ansiyellow",
    WorkflowState.PLAN_CREATED: "fg:ansicyan",
    WorkflowState.AWAITING_APPROVAL: "fg:ansimagenta",
    WorkflowState.EXECUTING: "fg:ansigreen",
    WorkflowState.COMPLETED: "fg:ansigreen",
}


def make_toolbar(
    conversation: object,
    workflow: "Workflow | None",
    branch: str,
    context_limit: int = DEFAULT_CONTEXT_LIMIT,
):
    """Create a bottom_toolbar callable for use with prompt_toolkit PromptSession.

    Returns a callable that reads the current state each time the prompt
    redraws, so the toolbar stays up-to-date without manual refreshes.

    Args:
        conversation: ConversationManager with a ``token_count`` attribute.
        workflow: Active Workflow instance (or None).
        branch: Current git branch name.
        context_limit: Maximum context tokens.

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

        parts: list[tuple[str, str]] = [
            ("", f"  Ctx: {token_count:,} "),
            (ctx_style, f"({percentage:.1f}%)"),
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
            summary = f"{todos.completed_count}/{todos.total}"
            if in_progress:
                label = in_progress.description[:30]
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


