"""Rich terminal output helpers for the CLI."""

import difflib

_LIVE_REFRESH_HZ = 8
_MAX_DIFF_LINES = 80
_MAX_ARG_DISPLAY = 50
_SHORT_SESSION_ID_LEN = 12

from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.status import Status
from rich.text import Text


class _LazyMarkdown:
    """Renderable that rebuilds Markdown only when text has changed.

    Rich Live calls ``__rich_console__`` at most ``refresh_per_second`` times.
    This avoids building a new ``Markdown`` object on every token received.
    """

    def __init__(self) -> None:
        self._text = ""
        self._cached: Markdown | None = None

    def append(self, delta: str) -> None:
        """Append new text and invalidate the cache."""
        self._text += delta
        self._cached = None

    def __rich_console__(self, console, options):
        if self._cached is None:
            self._cached = Markdown(self._text)
        yield from self._cached.__rich_console__(console, options)


class StreamingDisplay:
    """Progressive markdown streaming display using Rich Live.

    Context manager that accumulates streamed text and re-renders
    it as Rich Markdown at most ``refresh_per_second`` times per second
    via ``_LazyMarkdown`` (not once per token).
    """

    def __init__(self, console: Console) -> None:
        self._console = console
        self._renderable = _LazyMarkdown()
        self._live = Live(
            self._renderable,
            console=console,
            refresh_per_second=_LIVE_REFRESH_HZ,
            vertical_overflow="visible",
        )

    def __enter__(self) -> "StreamingDisplay":
        self._live.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._live.__exit__(exc_type, exc_val, exc_tb)

    def start_thinking(self) -> None:
        """Show a thinking spinner before the first token arrives."""
        pass  # Removed "Thinking..." text to keep conversation cleaner

    def update(self, delta: str) -> None:
        """Append new text; Markdown is rebuilt only on the next Live refresh."""
        self._renderable.append(delta)

    @property
    def full_text(self) -> str:
        """Return the accumulated text."""
        return self._renderable._text


class PlainStreamingDisplay:
    """Fallback streaming display for non-capable terminals (piped/dumb).

    Uses plain print() calls instead of Rich Live.
    """

    def __init__(self) -> None:
        self._text = ""

    def __enter__(self) -> "PlainStreamingDisplay":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._text.strip():
            print()

    def start_thinking(self) -> None:
        """No-op for plain display."""

    def update(self, delta: str) -> None:
        """Print delta directly to stdout."""
        self._text += delta
        print(delta, end="", flush=True)

    @property
    def full_text(self) -> str:
        """Return the accumulated text."""
        return self._text


class Renderer:
    """Render markdown and styled status/error output in terminal."""

    def __init__(self) -> None:
        self.console = Console()

    def render_markdown(self, text: str) -> None:
        """Render markdown content with Rich formatting."""
        self.console.print(Markdown(text))

    def render_streaming_live(self) -> "StreamingDisplay | PlainStreamingDisplay":
        """Return a streaming display context manager.

        Uses Rich Live for interactive terminals, plain print for piped/dumb terminals.

        Returns:
            A streaming display context manager.
        """
        if self.console.is_terminal:
            return StreamingDisplay(self.console)
        return PlainStreamingDisplay()

    def print_error(self, message: str) -> None:
        """Print a styled error message."""
        self.console.print(f"[red]{message}[/red]", highlight=False)

    def print_info(self, message: str) -> None:
        """Print a styled informational message."""
        self.console.print(f"[dim]{message}[/dim]", highlight=False)

    def print_warning(self, message: str) -> None:
        """Print a styled warning message."""
        self.console.print(f"[yellow]{message}[/yellow]", highlight=False)

    def print_success(self, message: str) -> None:
        """Print a styled success message."""
        self.console.print(f"[green]{message}[/green]", highlight=False)

    def status_spinner(self, message: str) -> "Status":
        """Return a spinner context manager for status display.

        Args:
            message: Status message to display.

        Returns:
            A Rich Status spinner.
        """
        return self.console.status(message)

    def render_separator(self) -> None:
        """Render a dim horizontal rule as a separator."""
        self.console.print(Rule(style="dim"))

    def render_user_message(self, text: str) -> None:
        """Render the user's message in the output area.

        Args:
            text: The user's input text.
        """
        self.console.print()
        self.console.print(Text.assemble(
            ("You", "bold cyan"),
            (" > ", "green"),
            (text, ""),
        ), highlight=False)
        self.console.print()

    def render_banner(self, version: str) -> None:
        """Render the application banner.

        Args:
            version: Application version string.
        """
        content = Text.assemble(
            ("coding-agent", "bold cyan"),
            ("  v" + version, "dim"),
        )
        self.console.print(Panel(
            Align.left(content),
            border_style="cyan dim",
            expand=False,
            padding=(0, 2),
        ))

    def render_config(self, config_items: dict) -> None:
        """Render configuration items one per line, left-aligned.

        Args:
            config_items: Dict of config key -> value to display.
        """
        for key, value in config_items.items():
            line = Text.assemble(
                (f"{key}: ", "dim"),
                (value, "#888888"),
            )
            self.console.print(line, highlight=False)

    def render_status_line(self, model: str, token_count: int | None, session_id: str | None) -> None:
        """Render compact status line after each assistant response.

        Args:
            model: The model name being used
            token_count: Estimated token count (optional)
            session_id: Current session ID (optional)
        """
        parts = [model]
        if token_count is not None:
            parts.append(f"{token_count:,} tokens")
        if session_id is not None:
            short_id = session_id[:_SHORT_SESSION_ID_LEN] + "..." if len(session_id) > _SHORT_SESSION_ID_LEN else session_id
            parts.append(short_id)

        line = Text(" | ".join(parts), style="dim")
        self.console.print(line)

    def render_tool_panel(self, tool_name: str, tool_args: dict) -> None:
        """Render a compact inline display for tool execution.

        Args:
            tool_name: Name of the tool being executed
            tool_args: Dictionary of tool arguments
        """
        self.console.print(f"[bold cyan]◆[/bold cyan] [cyan]{tool_name}[/cyan]")
        for key, value in tool_args.items():
            value_str = str(value)
            if len(value_str) > _MAX_ARG_DISPLAY:
                value_str = value_str[:_MAX_ARG_DISPLAY - 3] + "..."
            self.console.print(f"  [dim]{key}[/dim]: {value_str}", highlight=False)

    def render_diff_preview(self, old_content: str, new_content: str, file_path: str = "") -> None:
        """Render before/after diff preview for file edits using unified diff format.

        Args:
            old_content: Original file content
            new_content: New file content
            file_path: File path for diff header labels
        """
        diff = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{file_path}" if file_path else "before",
            tofile=f"b/{file_path}" if file_path else "after",
            n=3,
        ))
        if not diff:
            return
        diff_text = "".join(diff[:_MAX_DIFF_LINES])
        if len(diff) > _MAX_DIFF_LINES:
            diff_text += f"\n  ... ({len(diff) - _MAX_DIFF_LINES} more lines)"
        self.console.print(Syntax(diff_text, "diff", theme="ansi_dark"))

