"""Interrupt handler for breaking out of LLM loops."""

import signal
import sys
import threading
from typing import Callable


class InterruptHandler:
    """Handles interrupts (Ctrl+C, ESC) to break LLM loops."""

    def __init__(self):
        self._interrupted = False
        self._callbacks: list[Callable[[], None]] = []
        self._original_signal_handler: signal.Handler | None = None
        self._keyboard_thread: threading.Thread | None = None
        self._stop_keyboard_listener = threading.Event()

    def is_interrupted(self) -> bool:
        """Check if an interrupt was requested."""
        return self._interrupted

    def clear(self) -> None:
        """Clear the interrupt flag."""
        self._interrupted = False

    def interrupt(self) -> None:
        """Trigger an interrupt."""
        self._interrupted = True
        for callback in self._callbacks:
            try:
                callback()
            except Exception:
                pass

    def add_callback(self, callback: Callable[[], None]) -> None:
        """Add a callback to be called on interrupt."""
        self._callbacks.append(callback)

    def setup_signal_handler(self) -> None:
        """Setup SIGINT handler for Ctrl+C."""
        self._original_signal_handler = signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        self.interrupt()

    def restore_signal_handler(self) -> None:
        """Restore original signal handler."""
        if self._original_signal_handler:
            signal.signal(signal.SIGINT, self._original_signal_handler)

    def start_keyboard_listener(self) -> None:
        """Start a background thread to listen for ESC key."""
        if self._keyboard_thread is not None and self._keyboard_thread.is_alive():
            return

        self._stop_keyboard_listener.clear()
        self._keyboard_thread = threading.Thread(target=self._keyboard_listener, daemon=True)
        self._keyboard_thread.start()

    def stop_keyboard_listener(self) -> None:
        """Stop the keyboard listener thread."""
        self._stop_keyboard_listener.set()
        if self._keyboard_thread is not None:
            self._keyboard_thread.join(timeout=1.0)

    def _keyboard_listener(self) -> None:
        """Listen for keyboard input in a background thread."""
        try:
            if sys.platform == "win32":
                import msvcrt
                while not self._stop_keyboard_listener.is_set():
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b'\x1b':  # ESC key
                            self.interrupt()
                        elif key == b'\x03':  # Ctrl+C
                            self.interrupt()
                    import time
                    time.sleep(0.05)
            else:
                import tty
                import termios
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setcbreak(fd)
                    while not self._stop_keyboard_listener.is_set():
                        import select
                        if select.select([sys.stdin], [], [], 0.05)[0]:
                            key = sys.stdin.read(1)
                            if key == '\x1b':  # ESC
                                self.interrupt()
                                break
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            pass


_global_handler: InterruptHandler | None = None


def get_interrupt_handler() -> InterruptHandler:
    """Get the global interrupt handler."""
    global _global_handler
    if _global_handler is None:
        _global_handler = InterruptHandler()
    return _global_handler


def is_interrupted() -> bool:
    """Check if an interrupt was requested."""
    return get_interrupt_handler().is_interrupted()


def clear_interrupt() -> None:
    """Clear the interrupt flag."""
    get_interrupt_handler().clear()


def trigger_interrupt() -> None:
    """Trigger an interrupt."""
    get_interrupt_handler().interrupt()
