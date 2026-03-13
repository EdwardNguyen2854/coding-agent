"""Progress rendering utilities."""

import time
from typing import Optional

from coding_agent.ui.progress.terminal import get_terminal_capabilities
from coding_agent.ui.progress.types import ProgressStyle


class ProgressRenderer:
    """Renders progress bars in various styles."""

    BAR_CHARS = ["█", "░"]
    DOTS_CHARS = ["●", "○"]
    MINIMAL_CHARS = ["=", "-"]

    def __init__(self, style: ProgressStyle = ProgressStyle.BAR):
        self.style = style
        self.term = get_terminal_capabilities()

    def render(
        self,
        current: int,
        total: int,
        description: str = "",
        elapsed: float = 0,
        step_info: Optional[str] = None,
    ) -> str:
        """Render a progress line.

        Args:
            current: Current progress value.
            total: Total value.
            description: Description text.
            elapsed: Elapsed time in seconds.
            step_info: Current step info (e.g., "Step 3/5").

        Returns:
            Formatted progress string.
        """
        if total <= 0:
            return description or ""

        percentage = min(100, max(0, int(current / total * 100)))

        parts = []

        if self.style == ProgressStyle.BAR:
            parts.append(self._render_bar(percentage))
        elif self.style == ProgressStyle.DOTS:
            parts.append(self._render_dots(percentage))
        elif self.style == ProgressStyle.MINIMAL:
            parts.append(f"{percentage}%")
        else:
            parts.append(self._render_bar(percentage))

        parts.append(f"{percentage}%")

        if step_info:
            parts.append(f"| {step_info}")

        if description:
            parts.append(f"| {description}")

        if elapsed > 0 and self.term.is_tty:
            elapsed_str = self._format_time(elapsed)
            parts.append(f"| {elapsed_str}")

        return " ".join(parts)

    def _render_bar(self, percentage: int) -> str:
        """Render a progress bar sized to the terminal width."""
        bar_width = max(10, min(40, self.term.width // 4))
        filled = int(bar_width * percentage / 100)
        bar = self.BAR_CHARS[0] * filled + self.BAR_CHARS[1] * (bar_width - filled)
        return f"[{bar}]"

    def _render_dots(self, percentage: int) -> str:
        """Render progress as dots sized to the terminal width."""
        num_dots = max(5, min(20, self.term.width // 8))
        filled = int(num_dots * percentage / 100)
        dots = self.DOTS_CHARS[0] * filled + self.DOTS_CHARS[1] * (num_dots - filled)
        return f"[{dots}]"

    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to mm:ss or ss.s."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def clear_line(self) -> str:
        """Return string to clear the current line."""
        if self.term.is_tty:
            return "\r\033[K"
        return "\r"


class SpinnerRenderer:
    """Renders animated spinners."""

    FRAMES = {
        "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
        "line": ["|", "/", "─", "\\"],
        "bouncing": ["⠁", "⠂", "⠄", "⢅", "⠆", "⠇", "⠏", "⠎", "⠌", "⠊"],
    }

    def __init__(self, style: str = "dots"):
        self.style = style
        self.frames = self.FRAMES.get(style, self.FRAMES["dots"])
        self.frame_index = 0

    def next_frame(self) -> str:
        """Get the next spinner frame."""
        frame = self.frames[self.frame_index]
        self.frame_index = (self.frame_index + 1) % len(self.frames)
        return frame

    def render(self, message: str = "") -> str:
        """Render spinner with optional message."""
        frame = self.next_frame()
        if message:
            return f"{frame} {message}"
        return f"{frame}"

    def reset(self) -> None:
        """Reset to first frame."""
        self.frame_index = 0


def create_progress_renderer(style: str = "bar") -> ProgressRenderer:
    """Create a progress renderer with the specified style."""
    return ProgressRenderer(style=ProgressStyle(style))


def create_spinner_renderer(style: str = "dots") -> SpinnerRenderer:
    """Create a spinner renderer with the specified style."""
    return SpinnerRenderer(style=style)
