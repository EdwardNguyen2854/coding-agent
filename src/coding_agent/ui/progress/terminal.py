"""Terminal capability detection."""

import os
import sys
from dataclasses import dataclass


@dataclass
class TerminalCapabilities:
    """Terminal capability information."""

    is_tty: bool
    width: int
    height: int
    supports_color: bool
    supports_ansi: bool


def get_terminal_capabilities() -> TerminalCapabilities:
    """Detect terminal capabilities.

    Returns:
        TerminalCapabilities with detected features.
    """
    is_tty = sys.stdout.isatty()

    width = _get_terminal_width()
    height = _get_terminal_height()

    supports_ansi = _supports_ansi()
    supports_color = _supports_color(supports_ansi)

    return TerminalCapabilities(
        is_tty=is_tty,
        width=width,
        height=height,
        supports_color=supports_color,
        supports_ansi=supports_ansi,
    )


def _get_terminal_width() -> int:
    """Get terminal width."""
    try:
        import shutil
        return shutil.get_terminal_size().columns
    except Exception:
        return 80


def _get_terminal_height() -> int:
    """Get terminal height."""
    try:
        import shutil
        return shutil.get_terminal_size().lines
    except Exception:
        return 24


def _supports_ansi() -> bool:
    """Check if terminal supports ANSI escape sequences."""
    if not sys.stdout.isatty():
        return False

    if os.environ.get("TERM") == "dumb":
        return False

    return True


def _supports_color(supports_ansi: bool) -> bool:
    """Check if terminal supports color output."""
    if not supports_ansi:
        return False

    if os.environ.get("NO_COLOR"):
        return False

    term = os.environ.get("TERM", "")
    if "color" in term.lower() or term.startswith("xterm") or term.startswith("screen"):
        return True

    if os.environ.get("FORCE_COLOR"):
        return True

    return False


def should_show_progress() -> bool:
    """Determine if progress display should be shown.

    Returns False for dumb terminals, non-TTY, or when NO_COLOR is set.
    """
    if not sys.stdout.isatty():
        return False

    if os.environ.get("TERM") == "dumb":
        return False

    return True
