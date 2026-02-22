"""Rich terminal output helpers for the CLI."""

import contextlib
import difflib
import io

from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.status import Status
from rich.text import Text


class StreamingDisplay:
    """Progressive markdown streaming display using Rich Live.

    Context manager that accumulates streamed text and re-renders
    it as Rich Markdown on each update.
    """

    def __init__(self, console: Console) -> None:
        self._console = console
        self._text = ""
        self._live = Live(
            "",
            console=console,
            refresh_per_second=8,
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
        """Append new text and re-render the full markdown."""
        self._text += delta
        self._live.update(Markdown(self._text))

    @property
    def full_text(self) -> str:
        """Return the accumulated text."""
        return self._text


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


class CapturedStreamingDisplay:
    """Streaming display that renders markdown to an output file.

    Used in split-pane mode. During streaming, raw tokens are written for
    immediate feedback. On exit, the raw tokens are replaced with Rich
    Markdown-rendered output so that bold, code blocks, etc. display correctly.
    """

    def __init__(self, output_file: io.TextIOBase, capture: "object | None" = None) -> None:
        self._output_file = output_file
        self._capture = capture  # OutputCapture instance for clearing raw tokens
        self._text = ""
        self._token_count = 0  # number of raw write() calls to roll back

    def __enter__(self) -> "CapturedStreamingDisplay":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self._text:
            return
        # Roll back the raw tokens from the capture buffer and replace
        # with Rich Markdown-rendered output.
        if self._capture is not None and self._token_count > 0:
            self._capture._roll_back(self._token_count)
        # Render markdown through a Rich Console targeting the output file
        console = Console(
            file=self._output_file, force_terminal=True, highlight=False,
            width=120,
        )
        console.print(Markdown(self._text))

    def start_thinking(self) -> None:
        """No-op for captured display."""

    def update(self, delta: str) -> None:
        """Write delta directly to the output file for immediate feedback.

        Args:
            delta: New text chunk to write.
        """
        self._text += delta
        self._output_file.write(delta)
        self._output_file.flush()
        self._token_count += 1

    @property
    def full_text(self) -> str:
        """Return the accumulated text."""
        return self._text


class Renderer:
    """Render markdown and styled status/error output in terminal."""

    def __init__(self, output_file: io.TextIOBase | None = None, capture: "object | None" = None) -> None:
        self._output_file = output_file
        self._capture = capture  # OutputCapture for CapturedStreamingDisplay rollback
        if output_file is not None:
            self.console = Console(file=output_file, force_terminal=True, highlight=False)
        else:
            self.console = Console()

    def render_markdown(self, text: str) -> None:
        """Render markdown content with Rich formatting."""
        self.console.print(Markdown(text))

    def render_streaming_live(self) -> "StreamingDisplay | PlainStreamingDisplay | CapturedStreamingDisplay":
        """Return a streaming display context manager.

        Uses CapturedStreamingDisplay when output is captured (split-pane mode),
        Rich Live for interactive terminals, plain print for piped/dumb terminals.

        Returns:
            A streaming display context manager.
        """
        if self._output_file is not None:
            return CapturedStreamingDisplay(self._output_file, capture=self._capture)
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

    def status_spinner(self, message: str) -> "Status | contextlib.AbstractContextManager":
        """Return a spinner context manager for status display.

        Returns a no-op context manager in captured mode to avoid
        cursor-movement ANSI codes appearing as garbage in the output buffer.

        Args:
            message: Status message to display.

        Returns:
            A Rich Status spinner, or a no-op context manager in captured mode.
        """
        if self._output_file is not None:
            return contextlib.nullcontext()
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
            short_id = session_id[:12] + "..." if len(session_id) > 12 else session_id
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
            if len(value_str) > 50:
                value_str = value_str[:47] + "..."
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
        diff_text = "".join(diff[:80])
        if len(diff) > 80:
            diff_text += f"\n  ... ({len(diff) - 80} more lines)"
        self.console.print(Syntax(diff_text, "diff", theme="ansi_dark"))

