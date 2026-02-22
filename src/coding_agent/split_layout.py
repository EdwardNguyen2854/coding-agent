"""True split-pane TUI using prompt_toolkit Application with VSplit layout."""

import asyncio
import io
import threading
from collections import deque
from typing import Callable

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import ANSI, FormattedText
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.filters import has_completions
from prompt_toolkit.layout.containers import (
    ConditionalContainer, Float, FloatContainer, HSplit, VSplit, Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.margins import Margin, ScrollbarMargin
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.styles import Style

from coding_agent.interrupt import trigger_interrupt

SIDEBAR_WIDTH = 26
SCROLL_WHEEL_LINES = 10
SCROLL_PAGE_LINES = 30


class _ScrollableTextControl(FormattedTextControl):
    """FormattedTextControl that intercepts mouse wheel events.

    The Window dispatches mouse events to ``self.content.mouse_handler`` first.
    By returning ``None`` (handled) for SCROLL_UP/DOWN, we prevent the Window's
    own ``_mouse_handler`` from updating ``Window.vertical_scroll`` directly —
    which would be overridden by ``get_vertical_scroll`` on the next render anyway.
    Instead we call our callbacks that update ``_scroll_position``.
    """

    on_scroll_up: Callable[[int], None] | None = None
    on_scroll_down: Callable[[int], None] | None = None

    def mouse_handler(self, mouse_event):  # type: ignore[override]
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            if self.on_scroll_up:
                self.on_scroll_up(SCROLL_WHEEL_LINES)
            return None  # consumed
        if mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            if self.on_scroll_down:
                self.on_scroll_down(SCROLL_WHEEL_LINES)
            return None  # consumed
        return NotImplemented  # let Window handle everything else


class OutputCapture(io.TextIOBase):
    """Thread-safe text buffer for capturing Rich output in split-pane mode."""

    def __init__(self) -> None:
        self._lines: deque[str] = deque(maxlen=5000)
        self._lock = threading.Lock()
        self._on_update: Callable[[], None] | None = None

    def write(self, text: str) -> int:
        with self._lock:
            self._lines.append(text)
        if self._on_update:
            self._on_update()
        return len(text)

    def flush(self) -> None:
        pass

    def get_lines(self) -> list[str]:
        with self._lock:
            return list(self._lines)

    def clear(self) -> None:
        with self._lock:
            self._lines.clear()

    def _roll_back(self, count: int) -> None:
        """Remove the last *count* entries from the buffer.

        Used by CapturedStreamingDisplay to replace raw tokens with
        Rich Markdown-rendered output.
        """
        with self._lock:
            for _ in range(min(count, len(self._lines))):
                self._lines.pop()


class SplitLayout:
    """Full-screen split-pane TUI with main output area and sticky sidebar.

    Scroll design
    -------------
    prompt_toolkit's Window always calls ``do_scroll`` after ``get_vertical_scroll``
    to ensure the *cursor* remains visible.  Because ``FormattedTextControl``
    defaults the cursor to line 0, any scroll > 0 would immediately be reset to 0.

    The fix: supply ``get_cursor_position`` so the cursor tracks ``_scroll_position``.
    ``do_scroll`` then leaves the scroll untouched (cursor is already visible at the
    top of the viewport).  For auto-scroll ``_scroll_position = 99999`` and cursor is
    clamped to the last content line; ``do_scroll`` naturally scrolls to the bottom.

    After each render, ``Window.vertical_scroll`` holds the actual clamped position
    used by prompt_toolkit, which is the reliable base for the next scroll step.

    Key bindings
    ------------
    - Enter        : submit message
    - Ctrl+C       : interrupt agent
    - Ctrl+D       : exit
    - Up/Down      : history navigation
    - PageUp/Down  : scroll output 10 lines
    - Ctrl+PageUp  : jump to top
    - Ctrl+PageDown: jump to bottom (re-enable auto-scroll)
    - Mouse wheel  : scroll output 3 lines (via _ScrollableTextControl.mouse_handler)
    """

    def __init__(
        self,
        output_capture: OutputCapture,
        sidebar_func: Callable[[], FormattedText],
        process_message: Callable[[str], None],
        completer=None,
    ) -> None:
        self._output_capture = output_capture
        self._sidebar_func = sidebar_func
        self._process_message = process_message
        self._agent_running = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._output_window: Window | None = None
        # Scroll state
        self._scroll_position = 0      # desired scroll position (used when auto_scroll is False)
        self._content_line_count = 0   # last-known newline count in output text
        self._auto_scroll = True       # when True, _get_vertical_scroll targets bottom
        self._pending_permission_done = None  # (result_list, done_event) when waiting

        input_buf = Buffer(
            name="input",
            completer=completer,
            history=InMemoryHistory(),
        )
        self._input_buf = input_buf

        kb = KeyBindings()

        @kb.add("enter")
        def _handle_enter(event):
            buf = event.app.current_buffer
            if buf.complete_state is not None and buf.complete_state.current_completion is not None:
                buf.apply_completion(buf.complete_state.current_completion)
                return

            # If a permission prompt is pending, resolve it
            if self._pending_permission_done is not None:
                resp = input_buf.text.strip().lower()
                input_buf.reset()
                result_list, done_event = self._pending_permission_done
                result_list[0] = resp in ("", "y", "yes")
                done_event.set()
                return

            text = input_buf.text.strip()
            if text:
                input_buf.reset(append_to_history=True)
                threading.Thread(
                    target=self._run_thread,
                    args=(text,),
                    daemon=True,
                ).start()
            else:
                input_buf.reset()

        @kb.add("c-c")
        def _handle_ctrl_c(event):
            trigger_interrupt()
            self._output_capture.write("\n\033[33m⚡ Interrupted\033[0m\n")
            self._schedule_invalidate()

        @kb.add("c-d")
        def _handle_ctrl_d(event):
            event.app.exit()

        @kb.add("up", filter=~has_completions)
        def _handle_up(event):
            input_buf.history_backward()

        @kb.add("down", filter=~has_completions)
        def _handle_down(event):
            input_buf.history_forward()

        @kb.add("up", filter=has_completions)
        def _handle_up_completion(event):
            event.app.current_buffer.complete_previous()

        @kb.add("down", filter=has_completions)
        def _handle_down_completion(event):
            event.app.current_buffer.complete_next()

        @kb.add("tab")
        def _handle_tab(event):
            input_buf.start_completion()

        @kb.add("pageup")
        def _handle_pageup(event):
            self._scroll_up(SCROLL_PAGE_LINES)

        @kb.add("pagedown")
        def _handle_pagedown(event):
            self._scroll_down(SCROLL_PAGE_LINES)

        @kb.add("c-pageup")
        def _handle_ctrl_pageup(event):
            self._scroll_to_top()

        @kb.add("c-pagedown")
        def _handle_ctrl_pagedown(event):
            self._scroll_to_bottom()

        @kb.add(Keys.ScrollUp)
        def _handle_scroll_up(event):
            self._scroll_up(SCROLL_WHEEL_LINES)

        @kb.add(Keys.ScrollDown)
        def _handle_scroll_down(event):
            self._scroll_down(SCROLL_WHEEL_LINES)

        output_control = _ScrollableTextControl(
            text=self._get_output,
            get_cursor_position=self._get_cursor_position,
            show_cursor=False,
        )
        output_control.on_scroll_up = self._scroll_up
        output_control.on_scroll_down = self._scroll_down

        class SpaceMargin(Margin):
            def get_width(self, get_ui_content):
                return 2

            def create_margin(self, window_render_info, width, height):
                return []

        output_window = Window(
            content=output_control,
            wrap_lines=True,
            get_vertical_scroll=self._get_vertical_scroll,
            left_margins=[SpaceMargin()],
            right_margins=[SpaceMargin(), ScrollbarMargin(display_arrows=True)],
        )
        self._output_window = output_window

        # Input area with prompt label and separator line
        input_control = BufferControl(
            buffer=input_buf,
            input_processors=[BeforeInput([("class:prompt-label", " > ")])],
        )
        input_separator = Window(height=1, char="─", style="class:input-border")
        input_pad_top = Window(height=1, style="class:input-area")
        input_window = Window(
            content=input_control,
            height=Dimension(min=1, max=3, preferred=1),
            style="class:input-area",
        )
        input_pad_bottom = Window(height=1, style="class:input-area")
        # Hint line below input
        hint_control = FormattedTextControl(
            [("class:hint", "  Enter send | Ctrl+C interrupt | Ctrl+D exit | PgUp/PgDn scroll")]
        )
        hint_window = Window(content=hint_control, height=1, style="class:hint")

        bottom_pad = Window(height=1, style="class:input-area")

        main_area = HSplit([
            output_window,
            input_separator,
            input_pad_top,
            input_window,
            input_pad_bottom,
            hint_window,
            bottom_pad,
        ])

        sidebar = Window(
            width=SIDEBAR_WIDTH,
            content=FormattedTextControl(self._get_sidebar),
            style="class:sidebar",
        )

        layout = Layout(
            FloatContainer(
                content=VSplit([main_area, Window(width=3), sidebar]),
                floats=[
                    Float(
                        xcursor=True,
                        ycursor=True,
                        content=CompletionsMenu(max_height=16, scroll_offset=1),
                    ),
                ],
            )
        )

        style = Style.from_dict({
            "separator": "ansigray",
            "sidebar": "bg:#2d2d2d fg:#e0e0e0",
            "prompt": "ansicyan bold",
            "prompt-running": "ansiyellow",
            "input-border": "#555555",
            "input-area": "bg:#333333",
            "prompt-label": "ansicyan bold",
            "hint": "bg:#333333 #888888",
        })

        self._app = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=True,
            style=style,
            mouse_support=True,
        )

    # ------------------------------------------------------------------
    # Content callbacks (called by prompt_toolkit during rendering)
    # ------------------------------------------------------------------

    def _get_output(self) -> ANSI:
        """Return captured output as ANSI-formatted text, updating line count."""
        lines = self._output_capture.get_lines()
        text = "".join(lines)
        # Count newlines = index of last content line (used to clamp cursor)
        self._content_line_count = text.count("\n")
        return ANSI(text)

    def _get_sidebar(self) -> FormattedText:
        return self._sidebar_func()

    def _get_vertical_scroll(self, window: Window) -> int:
        """Return the desired scroll position (prompt_toolkit starts from here)."""
        if self._auto_scroll:
            # Always jump to the bottom when auto-scroll is enabled.
            # Keep _scroll_position in sync so that the first scroll-up
            # starts from the current bottom position, not a stale value.
            pos = max(0, self._content_line_count)
            self._scroll_position = pos
            return pos
        return self._scroll_position

    def _get_cursor_position(self) -> Point:
        """Return cursor position so that do_scroll anchors to the scroll target.

        By placing the cursor at the desired scroll line (clamped to content),
        prompt_toolkit's do_scroll keeps it visible — matching our scroll position.

        For auto-scroll the cursor is placed at the last content line,
        so do_scroll scrolls to the bottom automatically.
        """
        if self._auto_scroll:
            return Point(x=0, y=self._content_line_count)
        y = min(self._scroll_position, self._content_line_count)
        return Point(x=0, y=y)

    # ------------------------------------------------------------------
    # Scroll helpers
    # ------------------------------------------------------------------

    def _schedule_invalidate(self) -> None:
        """Schedule an app redraw from any thread (thread-safe).

        When auto_scroll is enabled, _get_vertical_scroll and _get_cursor_position
        will automatically target the bottom of content during the next render.
        """
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._app.invalidate)

    def _scroll_up(self, lines: int = 1) -> None:
        self._auto_scroll = False
        self._scroll_position = max(0, self._scroll_position - lines)
        self._schedule_invalidate()

    def _scroll_down(self, lines: int = 1) -> None:
        new_pos = self._scroll_position + lines
        # Re-enable auto-scroll when scrolling past (or near) the bottom
        if new_pos >= self._content_line_count:
            self._auto_scroll = True
        else:
            self._auto_scroll = False
            self._scroll_position = new_pos
        self._schedule_invalidate()

    def _scroll_to_top(self) -> None:
        self._auto_scroll = False
        self._scroll_position = 0
        self._schedule_invalidate()

    def _scroll_to_bottom(self) -> None:
        self._auto_scroll = True
        self._schedule_invalidate()

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------

    def _run_thread(self, text: str) -> None:
        """Run process_message in a worker thread, updating agent_running state."""
        self._agent_running = True
        self._schedule_invalidate()
        try:
            self._process_message(text)
        finally:
            self._agent_running = False
            self._schedule_invalidate()

    # ------------------------------------------------------------------
    # Permission callback
    # ------------------------------------------------------------------

    def make_permission_callback(self):
        """Return a TUI-safe permission prompt callback.

        Shows the permission request in the output area and waits for the
        user to type 'y' or 'n' in the input buffer.
        """
        def callback(tool_name: str, params: dict, is_warning: bool) -> bool:
            if self._loop is None:
                try:
                    resp = input(f"\nAllow {tool_name}? [Y/n]: ").strip().lower()
                except EOFError:
                    resp = ""
                return resp in ("", "y", "yes")

            # Show prompt in the output area
            if is_warning:
                self._output_capture.write("\n\033[33m⚠  WARNING: Potentially destructive command!\033[0m\n")
            self._output_capture.write(f"\n\033[1mAllow {tool_name}?\033[0m [Y/n] ")
            self._schedule_invalidate()

            # Wait for user to submit via Enter in the input buffer
            result: list[bool] = [False]
            done = threading.Event()

            original_accept = self._pending_permission_done
            self._pending_permission_done = (result, done)

            done.wait(timeout=120.0)
            self._pending_permission_done = None

            status = "\033[32m✓ allowed\033[0m" if result[0] else "\033[31m✗ denied\033[0m"
            self._output_capture.write(f"{status}\n")
            self._schedule_invalidate()
            return result[0]

        return callback

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def request_exit(self) -> None:
        """Request the application to exit cleanly from any thread."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._app.exit)
        else:
            self._app.exit()

    def run(self) -> None:
        """Run the split-pane TUI (blocks until exit)."""
        async def _run():
            self._loop = asyncio.get_running_loop()
            await self._app.run_async()

        asyncio.run(_run())
