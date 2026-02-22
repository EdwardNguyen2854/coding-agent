"""Sidebar content as a sticky bottom toolbar for the prompt."""

from collections.abc import Callable

from prompt_toolkit.formatted_text import FormattedText

from coding_agent.workflow import Workflow, WorkflowState


DEFAULT_CONTEXT_LIMIT = 128000


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

        if percentage > 90:
            ctx_style = "fg:ansired"
        elif percentage > 70:
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
            parts += [
                ("", "  │  "),
                ("", f"Workflow: {workflow.state.value}"),
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


def make_sidebar_vertical(
    conversation: object,
    workflow: "Workflow | None",
    branch: str,
    context_limit: int = DEFAULT_CONTEXT_LIMIT,
) -> Callable[[], FormattedText]:
    """Create a vertical sidebar callable for use with the split-pane layout.

    Returns a callable that reads current state on each call, so the sidebar
    stays up-to-date without manual refreshes.

    Args:
        conversation: ConversationManager with a ``token_count`` attribute.
        workflow: Active Workflow instance (or None).
        branch: Current git branch name.
        context_limit: Maximum context tokens.

    Returns:
        A callable that returns FormattedText for the sidebar content.
    """
    _SEP = "─" * 24

    def _sidebar() -> FormattedText:
        token_count = getattr(conversation, "token_count", 0)
        percentage = (token_count / context_limit) * 100

        if percentage > 90:
            ctx_style = "fg:ansired"
        elif percentage > 70:
            ctx_style = "fg:ansiyellow"
        else:
            ctx_style = "fg:ansigreen"

        parts: list[tuple[str, str]] = [
            ("", "\n"),
            ("bold", " STATUS\n"),
            ("ansigray", f" {_SEP}\n"),
            ("", " Context\n"),
            ("fg:#888888", f" {token_count:,} "),
            (ctx_style, f"({percentage:.1f}%)\n"),
            ("", "\n"),
            ("", " Branch\n"),
            ("fg:#888888", f" {branch[:22]}\n"),
        ]

        if workflow and workflow.state != WorkflowState.IDLE:
            parts += [
                ("", "\n"),
                ("", " Workflow\n"),
                ("fg:#888888", f" {workflow.state.value}\n"),
            ]

        if workflow and workflow.todo_list.total > 0:
            todos = workflow.todo_list
            in_progress = next(
                (i for i in todos.items if i.status.value == "in_progress"), None
            )
            summary = f"{todos.completed_count}/{todos.total}"
            parts += [
                ("", "\n"),
                ("", " Todos\n"),
                ("fg:#888888", f" {summary}\n"),
            ]
            if in_progress:
                label = in_progress.description[:20]
                parts.append(("fg:#888888", f" \u25b6 {label}\n"))

        return FormattedText(parts)

    return _sidebar
