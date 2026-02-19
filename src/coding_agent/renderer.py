"""Rich terminal output helpers for the CLI."""

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

    def status_spinner(self, message: str) -> Status:
        """Return a spinner context manager for status display."""
        return self.console.status(message)

    def render_separator(self) -> None:
        """Render a dim horizontal rule as a separator."""
        self.console.print(Rule(style="dim"))

    def render_banner(self, version: str) -> None:
        """Render the application banner with a Rich Panel.

        Args:
            version: Application version string.
        """
        banner_text = Text()
        banner_text.append("EMN CODING AGENT", style="bold cyan")
        banner_text.append(f" v{version}", style="cyan")

        panel = Panel(
            banner_text,
            subtitle="AI-powered coding assistant",
            border_style="cyan",
            padding=(0, 2),
        )
        self.console.print(panel)

    def render_config(self, config_items: dict) -> None:
        """Render configuration as a styled table.

        Args:
            config_items: Dict of config key -> value to display.
        """
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="dim")
        table.add_column(style="cyan")

        for key, value in config_items.items():
            table.add_row(key, str(value))

        self.console.print(table)

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
        """Render a styled panel for tool execution.

        Args:
            tool_name: Name of the tool being executed
            tool_args: Dictionary of tool arguments
        """
        args_lines = []
        for key, value in tool_args.items():
            value_str = str(value)
            if len(value_str) > 80:
                value_str = value_str[:77] + "..."
            args_lines.append(f"  {key}: {value_str}")

        args_text = "\n".join(args_lines) if args_lines else "  (no arguments)"

        panel = Panel(
            args_text,
            title=f"[bold cyan]{tool_name}[/bold cyan]",
            border_style="blue",
            padding=(0, 1),
        )
        self.console.print(panel)

    def render_diff_preview(self, old_content: str, new_content: str, language: str = "python") -> None:
        """Render before/after diff preview for file edits.

        Args:
            old_content: Original file content
            new_content: New file content
            language: Language for syntax highlighting
        """
        old_lines = old_content.split("\n") if old_content else []
        new_lines = new_content.split("\n") if new_content else []

        diff_lines = []
        max_lines = max(len(old_lines), len(new_lines))

        for i in range(max_lines):
            old_line = old_lines[i] if i < len(old_lines) else None
            new_line = new_lines[i] if i < len(new_lines) else None

            if old_line == new_line:
                diff_lines.append(f"  {old_line}")
            else:
                if old_line is not None:
                    diff_lines.append(f"[-] {old_line}")
                if new_line is not None:
                    diff_lines.append(f"[+] {new_line}")

        diff_text = "\n".join(diff_lines[:50])
        if len(diff_lines) > 50:
            diff_text += f"\n  ... ({len(diff_lines) - 50} more lines)"

        syntax = Syntax(diff_text, language, theme="monokai", line_numbers=True)

        panel = Panel(
            syntax,
            title="[bold yellow]Diff Preview[/bold yellow]",
            border_style="yellow",
            padding=(0, 1),
        )
        self.console.print(panel)
