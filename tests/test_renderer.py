"""Tests for Rich-based terminal renderer."""

from unittest.mock import MagicMock, patch

import pytest
from rich.markdown import Markdown

from coding_agent.renderer import Renderer


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
    def test_render_streaming_markdown_renders_complete_text(self, mock_console_cls):
        """render_streaming_markdown() reuses markdown rendering."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_streaming_markdown("final streamed response")

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
        mock_console.status.assert_called_once_with("Thinking...")

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

    @patch("coding_agent.renderer.Console")
    def test_render_status_line_with_all_params(self, mock_console_cls):
        """render_status_line() displays model, tokens, and session ID."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_status_line("gpt-4", 1234, "session-123-abc")

        assert mock_console.print.call_count == 1
        from rich.table import Table
        call_arg = mock_console.print.call_args.args[0]
        assert isinstance(call_arg, Table)

    @patch("coding_agent.renderer.Console")
    def test_render_status_line_with_optional_params(self, mock_console_cls):
        """render_status_line() handles None optional parameters."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_status_line("gpt-4", None, None)

        assert mock_console.print.call_count == 1

    @patch("coding_agent.renderer.Console")
    def test_render_tool_panel_with_args(self, mock_console_cls):
        """render_tool_panel() displays tool name and arguments."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        tool_args = {"path": "/test/file.py", "content": "print('hello')"}
        renderer.render_tool_panel("file_write", tool_args)

        assert mock_console.print.call_count == 1
        from rich.panel import Panel
        call_arg = mock_console.print.call_args.args[0]
        assert isinstance(call_arg, Panel)

    @patch("coding_agent.renderer.Console")
    def test_render_tool_panel_empty_args(self, mock_console_cls):
        """render_tool_panel() handles empty arguments."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_tool_panel("shell", {})

        assert mock_console.print.call_count == 1

    @patch("coding_agent.renderer.Console")
    def test_render_diff_preview_shows_changes(self, mock_console_cls):
        """render_diff_preview() displays before/after with +/- markers."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        old_content = "line 1\nline 2\nline 3"
        new_content = "line 1\nmodified line\nline 3"
        renderer.render_diff_preview(old_content, new_content)

        assert mock_console.print.call_count == 1
        from rich.panel import Panel
        call_arg = mock_console.print.call_args.args[0]
        assert isinstance(call_arg, Panel)

    @patch("coding_agent.renderer.Console")
    def test_render_diff_preview_empty_content(self, mock_console_cls):
        """render_diff_preview() handles empty content."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        renderer = Renderer()

        renderer.render_diff_preview("", "new content")

        assert mock_console.print.call_count == 1
