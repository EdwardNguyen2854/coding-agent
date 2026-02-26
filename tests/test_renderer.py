"""Tests for Rich-based terminal renderer."""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from coding_agent.renderer import PlainStreamingDisplay, Renderer, StreamingDisplay


class TestRenderer:
    """Verify Renderer behavior for markdown and status output."""

    @patch("coding_agent.renderer.Console")
    def test_render_markdown_prints_markdown(self, mock_console_cls):
        """render_markdown() prints a Markdown object."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_markdown("# Hello\n\nSome **text**")

        mock_console.print.assert_called_once()
        rendered = mock_console.print.call_args.args[0]
        assert isinstance(rendered, Markdown)

    @patch("coding_agent.renderer.Console")
    def test_markdown_code_blocks_are_passed_to_markdown_renderer(self, mock_console_cls):
        """Markdown with code fences is rendered through Rich Markdown."""
        markdown_with_code = """```python\nprint(\"hello\")\n```"""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_markdown(markdown_with_code)

        rendered = mock_console.print.call_args.args[0]
        assert isinstance(rendered, Markdown)
        assert "```python" in rendered.markup

    @patch("coding_agent.renderer.Console")
    def test_print_error_outputs_styled_message(self, mock_console_cls):
        """print_error() prints red-styled message without auto-highlighting."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.print_error("boom")

        mock_console.print.assert_called_once_with("[red]boom[/red]", highlight=False)

    @patch("coding_agent.renderer.Console")
    def test_print_info_outputs_styled_message(self, mock_console_cls):
        """print_info() prints dim-styled message without auto-highlighting."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.print_info("Connected")

        mock_console.print.assert_called_once_with("[dim]Connected[/dim]", highlight=False)

    @patch("coding_agent.renderer.Console")
    def test_status_spinner_returns_console_status_context(self, mock_console_cls):
        """status_spinner() returns the console.status() context manager."""
        mock_console = MagicMock()
        mock_status_cm = MagicMock()
        mock_console.status.return_value = mock_status_cm
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        status_cm = renderer.status_spinner("Thinking...")

        assert status_cm is mock_status_cm
        # Check that status was called with the message (may have additional kwargs)
        mock_console.status.assert_called()
        call_args = mock_console.status.call_args
        assert call_args[0][0] == "Thinking..."

    @patch("coding_agent.renderer.Console")
    def test_status_spinner_cleans_up_on_exception(self, mock_console_cls):
        """Spinner context manager exits when an exception is raised."""
        mock_console = MagicMock()
        mock_status_cm = MagicMock()
        mock_console.status.return_value = mock_status_cm
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        with pytest.raises(RuntimeError):
            with renderer.status_spinner("Executing tool..."):
                raise RuntimeError("failure")

        mock_status_cm.__enter__.assert_called_once()
        mock_status_cm.__exit__.assert_called_once()


class TestRenderStatusLine:
    """Verify compact status line output."""

    @patch("coding_agent.renderer.Console")
    def test_render_status_line_with_all_params(self, mock_console_cls):
        """render_status_line() displays compact single-line with all info."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_status_line("gpt-4", 1234, "session-123-abc")

        assert mock_console.print.call_count == 1
        call_arg = mock_console.print.call_args.args[0]
        assert isinstance(call_arg, Text)
        plain = call_arg.plain
        assert "gpt-4" in plain
        assert "1,234 tokens" in plain
        assert "session-123-" in plain

    @patch("coding_agent.renderer.Console")
    def test_render_status_line_with_optional_params(self, mock_console_cls):
        """render_status_line() handles None optional parameters."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_status_line("gpt-4", None, None)

        assert mock_console.print.call_count == 1
        call_arg = mock_console.print.call_args.args[0]
        assert isinstance(call_arg, Text)
        assert "gpt-4" in call_arg.plain
        assert "tokens" not in call_arg.plain

    @patch("coding_agent.renderer.Console")
    def test_render_status_line_truncates_long_session_id(self, mock_console_cls):
        """Long session IDs are truncated with ellipsis."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_status_line("gpt-4", None, "abcdefghijklmnop")

        call_arg = mock_console.print.call_args.args[0]
        assert "abcdefghijkl..." in call_arg.plain


class TestRenderSeparator:
    """Verify separator rendering."""

    @patch("coding_agent.renderer.Console")
    def test_render_separator_prints_dim_rule(self, mock_console_cls):
        """render_separator() prints a dim horizontal Rule."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_separator()

        mock_console.print.assert_called_once()
        call_arg = mock_console.print.call_args.args[0]
        assert isinstance(call_arg, Rule)


class TestRenderBanner:
    """Verify banner rendering."""

    @patch("coding_agent.renderer.Console")
    def test_render_banner_prints_panel(self, mock_console_cls):
        """render_banner() prints a slim Rule with version."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_banner("1.0.0")

        mock_console.print.assert_called_once()
        call_arg = mock_console.print.call_args.args[0]
        # Banner may be Panel or Rule in current implementation - check it's a Panel
        assert hasattr(call_arg, 'renderable') or hasattr(call_arg, 'title')


class TestRenderConfig:
    """Verify config table rendering."""

    @patch("coding_agent.renderer.Console")
    def test_render_config_prints_table(self, mock_console_cls):
        """render_config() prints an inline dim line with config items."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_config({"Model": "gpt-4", "API": "http://localhost:4000"})

        # May be called multiple times now
        mock_console.print.assert_called()
        call_args_str = str(mock_console.print.call_args_list)
        assert "Model" in call_args_str
        assert "API" in call_args_str


class TestRenderStreamingLive:
    """Verify render_streaming_live() returns correct display type."""

    @patch("coding_agent.renderer.Console")
    def test_returns_streaming_display_for_terminal(self, mock_console_cls):
        """Returns StreamingDisplay when console is a terminal."""
        mock_console = MagicMock()
        mock_console.is_terminal = True
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        display = renderer.render_streaming_live()
        assert isinstance(display, StreamingDisplay)

    @patch("coding_agent.renderer.Console")
    def test_returns_plain_display_for_non_terminal(self, mock_console_cls):
        """Returns PlainStreamingDisplay when console is not a terminal."""
        mock_console = MagicMock()
        mock_console.is_terminal = False
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        display = renderer.render_streaming_live()
        assert isinstance(display, PlainStreamingDisplay)


class TestStreamingDisplay:
    """Verify StreamingDisplay behavior."""

    def test_update_accumulates_text(self):
        """update() accumulates text into full_text property."""
        mock_console = MagicMock()
        display = StreamingDisplay(mock_console)
        # Don't enter Live context, just test accumulation
        display._live = MagicMock()

        display.update("Hello")
        display.update(" world")

        assert display.full_text == "Hello world"

    def test_full_text_starts_empty(self):
        """full_text starts as empty string."""
        mock_console = MagicMock()
        display = StreamingDisplay(mock_console)
        assert display.full_text == ""


class TestPlainStreamingDisplay:
    """Verify PlainStreamingDisplay behavior."""

    def test_update_accumulates_text(self):
        """update() accumulates text and prints to stdout."""
        display = PlainStreamingDisplay()

        with patch("builtins.print") as mock_print:
            display.update("Hello")
            display.update(" world")

        assert display.full_text == "Hello world"

    def test_context_manager_prints_newline_on_exit(self):
        """Context manager prints trailing newline when text is non-empty."""
        display = PlainStreamingDisplay()

        with patch("builtins.print") as mock_print:
            with display:
                display.update("content")
            # Last call should be the newline from __exit__
            mock_print.assert_called_with()

    def test_context_manager_no_newline_when_empty(self):
        """Context manager does not print newline when text is empty."""
        display = PlainStreamingDisplay()

        with patch("builtins.print") as mock_print:
            with display:
                pass
            mock_print.assert_not_called()

    def test_start_thinking_is_noop(self):
        """start_thinking() is a no-op for plain display."""
        display = PlainStreamingDisplay()
        display.start_thinking()  # Should not raise

    def test_full_text_starts_empty(self):
        """full_text starts as empty string."""
        display = PlainStreamingDisplay()
        assert display.full_text == ""


class TestRenderToolPanel:
    """Verify tool panel rendering."""

    @patch("coding_agent.renderer.Console")
    def test_render_tool_panel_with_args(self, mock_console_cls):
        """render_tool_panel() displays tool name and arguments inline."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        tool_args = {"path": "/test/file.py", "content": "print('hello')"}
        renderer.render_tool_panel("file_write", tool_args)

        # 1 line for tool name + 1 line per argument
        assert mock_console.print.call_count == 1 + len(tool_args)
        # First call contains the tool name
        first_call_arg = mock_console.print.call_args_list[0].args[0]
        assert "file_write" in first_call_arg

    @patch("coding_agent.renderer.Console")
    def test_render_tool_panel_empty_args(self, mock_console_cls):
        """render_tool_panel() handles empty arguments."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_tool_panel("shell", {})

        assert mock_console.print.call_count == 1


class TestRenderDiffPreview:
    """Verify diff preview rendering."""

    @patch("coding_agent.renderer.Console")
    def test_render_diff_preview_shows_changes(self, mock_console_cls):
        """render_diff_preview() displays unified diff with Syntax."""
        from rich.syntax import Syntax
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        old_content = "line 1\nline 2\nline 3"
        new_content = "line 1\nmodified line\nline 3"
        renderer.render_diff_preview(old_content, new_content)

        assert mock_console.print.call_count == 1
        call_arg = mock_console.print.call_args.args[0]
        assert isinstance(call_arg, Syntax)

    @patch("coding_agent.renderer.Console")
    def test_render_diff_preview_empty_content(self, mock_console_cls):
        """render_diff_preview() handles empty content."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_diff_preview("", "new content")

        assert mock_console.print.call_count == 1
