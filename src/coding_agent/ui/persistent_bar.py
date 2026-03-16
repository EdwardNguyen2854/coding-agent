"""Persistent bottom status bar that stays visible during agent processing.

Runs a background thread that uses ANSI cursor-save / cursor-restore codes
to overwrite the last terminal row without disturbing normal scrolling output.
"""
from __future__ import annotations

import os
import sys
import shutil
import threading
from typing import Callable

# ---------------------------------------------------------------------------
# Global suppress flag — lets streaming displays pause bar drawing to avoid
# cursor-position conflicts with Rich Live / Status contexts.
# ---------------------------------------------------------------------------
_SUPPRESS = threading.Event()


def suppress_bar() -> None:
    """Pause persistent bar drawing (call before starting a Rich Live context)."""
    _SUPPRESS.set()


def unsuppress_bar() -> None:
    """Resume persistent bar drawing (call after a Rich Live context exits)."""
    _SUPPRESS.clear()

# ---------------------------------------------------------------------------
# Prompt-toolkit style → ANSI escape code mapping
# ---------------------------------------------------------------------------

_ANSI_FG_MAP: dict[str, str] = {
    "fg:ansiblack":          "\033[30m",
    "fg:ansidarkred":        "\033[31m",
    "fg:ansidarkgreen":      "\033[32m",
    "fg:ansibrown":          "\033[33m",
    "fg:ansidarkblue":       "\033[34m",
    "fg:ansipurple":         "\033[35m",
    "fg:ansiteal":           "\033[36m",
    "fg:ansilightgray":      "\033[37m",
    "fg:ansidarkgray":       "\033[90m",
    "fg:ansired":            "\033[91m",
    "fg:ansibrightred":      "\033[91m",
    "fg:ansigreen":          "\033[92m",
    "fg:ansibrightgreen":    "\033[92m",
    "fg:ansiyellow":         "\033[93m",
    "fg:ansibrightyellow":   "\033[93m",
    "fg:ansiblue":           "\033[94m",
    "fg:ansibrightblue":     "\033[94m",
    "fg:ansifuchsia":        "\033[95m",
    "fg:ansibrightmagenta":  "\033[95m",
    "fg:ansimagenta":        "\033[95m",
    "fg:ansicyan":           "\033[96m",
    "fg:ansibrightcyan":     "\033[96m",
    "fg:ansiwhite":          "\033[97m",
}

_BAR_BG  = "\033[48;5;235m"   # near-black background for the status bar
_BAR_FG  = "\033[38;5;253m"   # light grey default foreground
_RESET   = "\033[0m"


def _style_to_ansi(style: str) -> str:
    """Convert a prompt-toolkit style string to ANSI escape sequences.

    Handles ``fg:ansi*`` names, ``fg:#rrggbb`` hex colours, and ``bold``.
    Unknown tokens are silently ignored.
    """
    if not style:
        return ""
    codes: list[str] = []
    for token in style.split():
        if token == "bold":
            codes.append("\033[1m")
        elif token in _ANSI_FG_MAP:
            codes.append(_ANSI_FG_MAP[token])
        elif token.startswith("fg:#") and len(token) == 10:
            try:
                r = int(token[4:6], 16)
                g = int(token[6:8], 16)
                b = int(token[8:10], 16)
                codes.append(f"\033[38;2;{r};{g};{b}m")
            except ValueError:
                pass
    return "".join(codes)


def _enable_windows_vt() -> None:
    """Enable ANSI Virtual Terminal Processing on Windows consoles.

    Without this, the Windows console strips ESC bytes from stdout instead of
    interpreting them as ANSI escape sequences.  A no-op on non-Windows platforms.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong(0)
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:
        pass


def _write_ansi(seq: str) -> None:
    """Write an ANSI escape sequence directly, bypassing text-encoding layers.

    Uses ``sys.stdout.buffer`` (bytes layer) when available so that ESC bytes
    are never mangled by a TextIOWrapper codec.  Falls back to os.write() on
    fd 1, and finally to plain sys.stdout.write().
    """
    data = seq.encode("utf-8", errors="replace")
    try:
        buf = getattr(sys.stdout, "buffer", None)
        if buf is not None:
            buf.write(data)
            buf.flush()
            return
    except Exception:
        pass
    try:
        os.write(1, data)
        return
    except Exception:
        pass
    try:
        sys.stdout.write(seq)
        sys.stdout.flush()
    except Exception:
        pass


class PersistentStatusBar:
    """Background thread that keeps a status line at the last terminal row.

    Uses ANSI ``\\033[s`` / ``\\033[u`` (save/restore cursor) to draw a styled
    status line at the bottom of the terminal independently of any scrolling
    output produced by Rich or other code running in the main thread.

    Works on any terminal that supports ANSI cursor codes (xterm, Windows
    Terminal, most modern emulators).  On terminals without support the draw
    call silently no-ops.

    Usage::

        bar = PersistentStatusBar(toolbar_func)
        with bar:
            agent.run(task)
        # bar is cleared automatically on exit
    """

    _REFRESH_HZ = 5  # redraws per second

    def __init__(self, toolbar_func: Callable[[], list[tuple[str, str]]]) -> None:
        """Create the bar.

        Args:
            toolbar_func: Callable that returns a list of ``(style, text)``
                tuples in the same format used by prompt-toolkit's
                ``bottom_toolbar``.  Called on every refresh tick.
        """
        self._toolbar_func = toolbar_func
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_line(self, cols: int) -> str:
        """Build a coloured ANSI status line from toolbar FormattedText parts.

        The visible text is truncated / padded to exactly *cols* characters so
        the bar always fills the terminal width.  ANSI escape sequences are
        inserted for each styled segment but do not count toward the visible
        width.
        """
        try:
            parts = self._toolbar_func()
        except Exception:
            return ""

        # First pass: measure visible length so we can truncate / pad exactly.
        visible_len = sum(len(content) for _, content in parts)
        if visible_len > cols:
            # Trim the last segment(s) until we fit.
            trimmed: list[tuple[str, str]] = []
            remaining = cols
            for style, content in parts:
                if remaining <= 0:
                    break
                if len(content) > remaining:
                    content = content[:remaining]
                trimmed.append((style, content))
                remaining -= len(content)
            parts = trimmed
            visible_len = cols

        # Second pass: build the ANSI-coloured string.
        segments: list[str] = [_BAR_BG]
        for style, content in parts:
            if style:
                segments.append(_style_to_ansi(style))
                segments.append(content)
                segments.append(_BAR_BG + _BAR_FG)  # restore bar default fg
            else:
                segments.append(_BAR_FG)
                segments.append(content)

        # Pad to full terminal width so the background colour fills the row.
        pad = cols - visible_len
        if pad > 0:
            segments.append(" " * pad)

        return "".join(segments)

    def _draw(self) -> None:
        """Overwrite the last terminal row with the current status."""
        try:
            cols, rows = shutil.get_terminal_size()
            line = self._build_line(cols)
            # ANSI sequence breakdown:
            #   \033[s          – save cursor position
            #   \033[{rows};1H  – move to last row, column 1
            #   {line}          – coloured status text (padded to `cols`)
            #   \033[0m         – reset all attributes
            #   \033[u          – restore cursor position
            _write_ansi(
                "\033[s"
                f"\033[{rows};1H"
                f"{line}"
                "\033[0m"
                "\033[u"
            )
        except Exception:
            pass

    def _clear(self) -> None:
        """Erase the status bar line and leave the cursor where it was."""
        try:
            _, rows = shutil.get_terminal_size()
            _write_ansi(
                "\033[s"
                f"\033[{rows};1H"
                "\033[2K"   # erase entire line
                "\033[u"
            )
        except Exception:
            pass

    def _run(self) -> None:
        interval = 1.0 / self._REFRESH_HZ
        while not self._stop.wait(interval):
            if not _SUPPRESS.is_set():
                self._draw()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background refresh thread."""
        _enable_windows_vt()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="persistent-status-bar"
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the thread and clear the status bar."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._clear()

    def __enter__(self) -> "PersistentStatusBar":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
