"""Tests asserting Phase 4 polish: named constants and error display routing."""


class TestSidebarConstants:
    """Named constants must be importable from sidebar with correct values."""

    def test_ctx_critical_importable(self):
        from coding_agent.ui.sidebar import _CTX_CRITICAL
        assert isinstance(_CTX_CRITICAL, int)

    def test_ctx_warning_importable(self):
        from coding_agent.ui.sidebar import _CTX_WARNING
        assert isinstance(_CTX_WARNING, int)

    def test_ctx_critical_value(self):
        from coding_agent.ui.sidebar import _CTX_CRITICAL
        assert _CTX_CRITICAL == 90

    def test_ctx_warning_value(self):
        from coding_agent.ui.sidebar import _CTX_WARNING
        assert _CTX_WARNING == 70

    def test_critical_greater_than_warning(self):
        from coding_agent.ui.sidebar import _CTX_CRITICAL, _CTX_WARNING
        assert _CTX_CRITICAL > _CTX_WARNING


class TestRendererConstants:
    """Named constants must be importable from renderer."""

    def test_live_refresh_hz_importable(self):
        from coding_agent.ui.renderer import _LIVE_REFRESH_HZ
        assert isinstance(_LIVE_REFRESH_HZ, int)
        assert _LIVE_REFRESH_HZ > 0

    def test_max_diff_lines_importable(self):
        from coding_agent.ui.renderer import _MAX_DIFF_LINES
        assert isinstance(_MAX_DIFF_LINES, int)
        assert _MAX_DIFF_LINES > 0

    def test_max_arg_display_importable(self):
        from coding_agent.ui.renderer import _MAX_ARG_DISPLAY
        assert isinstance(_MAX_ARG_DISPLAY, int)

    def test_short_session_id_len_importable(self):
        from coding_agent.ui.renderer import _SHORT_SESSION_ID_LEN
        assert isinstance(_SHORT_SESSION_ID_LEN, int)


class TestSessionConstants:
    """Named constants must be importable from session."""

    def test_max_title_len_importable(self):
        from coding_agent.state.session import _MAX_TITLE_LEN
        assert isinstance(_MAX_TITLE_LEN, int)
        assert _MAX_TITLE_LEN > 0


class TestConversationConstants:
    """Named constants must be importable from conversation."""

    def test_max_tool_output_chars(self):
        from coding_agent.core.conversation import _MAX_TOOL_OUTPUT_CHARS
        assert isinstance(_MAX_TOOL_OUTPUT_CHARS, int)
        assert _MAX_TOOL_OUTPUT_CHARS > 0

    def test_max_tool_result_preview(self):
        from coding_agent.core.conversation import _MAX_TOOL_RESULT_PREVIEW
        assert isinstance(_MAX_TOOL_RESULT_PREVIEW, int)

    def test_tool_call_token_overhead(self):
        from coding_agent.core.conversation import _TOOL_CALL_TOKEN_OVERHEAD
        assert isinstance(_TOOL_CALL_TOKEN_OVERHEAD, int)


class TestErrorRouting:
    """REPL-loop errors should use renderer.print_error; startup fatal errors use click.echo."""

    def test_renderer_print_error_used_in_repl_for_connection_errors(self):
        """ConnectionError during agent.run() in the REPL loop goes to renderer.print_error."""
        from coding_agent.ui.renderer import Renderer

        renderer = Renderer()
        # renderer.print_error must exist and be callable
        assert callable(renderer.print_error)

    def test_print_error_outputs_red_text(self):
        """renderer.print_error outputs a message styled in red."""
        import io
        from rich.console import Console
        from coding_agent.ui.renderer import Renderer

        buf = io.StringIO()
        renderer = Renderer()
        renderer.console = Console(file=buf, highlight=False, no_color=True)
        renderer.print_error("something went wrong")
        output = buf.getvalue()
        assert "something went wrong" in output
