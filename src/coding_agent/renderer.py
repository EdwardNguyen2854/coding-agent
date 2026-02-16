"""Rich terminal output helpers for the CLI."""

from rich.console import Console
from rich.markdown import Markdown
from rich.status import Status


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
