"""Rich terminal output helpers for the CLI."""

import difflib
import sys
from contextlib import contextmanager
from collections.abc import Generator

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.status import Status
from rich.table import Table
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
        self._live.update(Spinner("dots", text="Thinking...", style="dim"))

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


class Renderer:
    """Render markdown and styled status/error output in terminal."""

    def __init__(self) -> None:
        self.console = Console()

    def render_markdown(self, text: str) -> None:
        """Render markdown content with Rich formatting."""
        self.console.print(Markdown(text))

    def render_streaming_live(self) -> StreamingDisplay | PlainStreamingDisplay:
        """Return a streaming display context manager.

        Uses Rich Live for interactive terminals, plain print for
        piped or dumb terminals.

        Returns:
            A StreamingDisplay or PlainStreamingDisplay context manager.
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

    def print_success(self, message: str) -> None:
        """Print a styled success message."""
        self.console.print(f"[green]{message}[/green]", highlight=False)

    def status_spinner(self, message: str) -> Status:
        """Return a spinner context manager for status display."""
        return self.console.status(message)

    def render_separator(self) -> None:
        """Render a dim horizontal rule as a separator."""
        self.console.print(Rule(style="dim"))

    def render_banner(self, version: str) -> None:
        """Render the application banner as a slim rule.

        Args:
            version: Application version string.
        """
        self.console.print(Rule(f"coding-agent v{version}", style="dim"))

    def render_config(self, config_items: dict) -> None:
        """Render configuration as a single inline dim line.

        Args:
            config_items: Dict of config key -> value to display.
        """
        parts = [f"{k}: {v}" for k, v in config_items.items()]
        self.console.print("  " + "  ·  ".join(parts), style="dim", highlight=False)

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
        self.console.print(f"  [bold cyan]◆[/bold cyan] [cyan]{tool_name}[/cyan]")
        for key, value in tool_args.items():
            value_str = str(value)
            if len(value_str) > 80:
                value_str = value_str[:77] + "..."
            self.console.print(f"    [dim]{key}[/dim]: {value_str}", highlight=False)

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
