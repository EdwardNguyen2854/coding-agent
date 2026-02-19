"""Rich terminal output helpers for the CLI."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.status import Status
from rich.table import Table


class Renderer:
    """Render markdown and styled status/error output in terminal."""

    def __init__(self) -> None:
        self.console = Console()

    def render_markdown(self, text: str) -> None:
        """Render markdown content with Rich formatting."""
        self.console.print(Markdown(text))

    def render_streaming_markdown(self, text: str) -> None:
        """Render full streamed response once streaming has completed."""
        self.render_markdown(text)

    def print_error(self, message: str) -> None:
        """Print a styled error message."""
        self.console.print(f"[red]{message}[/red]", highlight=False)

    def print_info(self, message: str) -> None:
        """Print a styled informational message."""
        self.console.print(f"[dim]{message}[/dim]", highlight=False)

    def status_spinner(self, message: str) -> Status:
        """Return a spinner context manager for status display."""
        return self.console.status(message)

    def render_status_line(self, model: str, token_count: int | None, session_id: str | None) -> None:
        """Render status line after each assistant response.

        Args:
            model: The model name being used
            token_count: Estimated token count (optional)
            session_id: Current session ID (optional)
        """
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="dim")
        table.add_column(style="cyan")
        
        table.add_row("Model:", model)
        if token_count is not None:
            table.add_row("Tokens:", str(token_count))
        if session_id is not None:
            table.add_row("Session:", session_id[:8] + "..." if len(session_id) > 8 else session_id)
        
        self.console.print(table)

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
