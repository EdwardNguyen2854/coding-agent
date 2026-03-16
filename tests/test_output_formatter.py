"""Tests for tool output formatter."""

import pytest

from coding_agent.config import OutputConfig
from coding_agent.ui.output.formatter import (
    ToolOutputFormatter,
    detect_output_type,
    detect_status,
    format_timing,
    truncate_output_text,
    OutputType,
    ToolStatus,
)


class TestOutputTypeDetection:
    """Test output type detection."""

    def test_detect_diff(self):
        assert detect_output_type("git_diff", "--- a/file\n+++ b/file") == OutputType.DIFF
        assert detect_output_type("file_patch", "--- a/file\n+++ b/file") == OutputType.DIFF

    def test_detect_json(self):
        json_output = '{"key": "value", "count": 42}'
        assert detect_output_type("workspace_info", json_output) == OutputType.JSON

    def test_detect_table(self):
        assert detect_output_type("run_tests", "Passed: 10/10") == OutputType.TABLE
        assert detect_output_type("run_lint", "errors: 0") == OutputType.TABLE
        assert detect_output_type("typecheck", "Found 0 errors") == OutputType.TABLE

    def test_detect_shell(self):
        assert detect_output_type("shell", "output") == OutputType.SHELL
        assert detect_output_type("safe_shell", "output") == OutputType.SHELL
        assert detect_output_type("run_command", "output") == OutputType.SHELL

    def test_detect_code(self):
        assert detect_output_type("file_read", "some content") == OutputType.CODE

    def test_detect_plain_default(self):
        assert detect_output_type("unknown_tool", "some content") == OutputType.PLAIN


class TestStatusDetection:
    """Test tool status detection."""

    def test_success_status(self):
        assert detect_status("file created successfully") == ToolStatus.SUCCESS

    def test_error_status(self):
        assert detect_status("error: something failed", is_error=True) == ToolStatus.ERROR
        assert detect_status("Failed to connect to server") == ToolStatus.ERROR
        assert detect_status("error occurred") == ToolStatus.ERROR

    def test_no_false_positive_on_no_errors(self):
        # "no errors found" should NOT trigger ERROR status
        assert detect_status("no errors found") != ToolStatus.ERROR

    def test_warning_status(self):
        assert detect_status("warning: deprecated API") == ToolStatus.WARNING
        assert detect_status("Warning: disk space low") == ToolStatus.WARNING

    def test_info_status(self):
        assert detect_status("workspace: /home/user/project") == ToolStatus.INFO


class TestTruncation:
    """Test smart truncation."""

    def test_no_truncation_needed(self):
        text = "line1\nline2\nline3"
        result, truncated, lines_removed = truncate_output_text(text, 10, 100)
        assert result == text
        assert truncated is False
        assert lines_removed == 0

    def test_truncation_with_context(self):
        lines = [f"line{i}" for i in range(100)]
        text = "\n".join(lines)
        
        result, truncated, lines_removed = truncate_output_text(text, 10, 100)
        
        assert truncated is True
        assert lines_removed == 90
        assert "line0" in result
        assert "line99" in result
        assert "... (90 more lines) ..." in result


class TestTimingFormatting:
    """Test timing value formatting."""

    def test_format_ms(self):
        assert format_timing(123.4, "ms") == "123.4ms"
        assert format_timing(0.8, "ms") == "0.8ms"

    def test_format_s(self):
        assert format_timing(1234.5, "s") == "1.23s"
        assert format_timing(500, "s") == "0.50s"

    def test_format_human(self):
        assert format_timing(500, "human") == "500ms"
        assert format_timing(1500, "human") == "1.5s"
        assert format_timing(5000, "human") == "5.0s"


class TestToolOutputFormatter:
    """Test ToolOutputFormatter class."""

    def test_formatter_defaults(self):
        formatter = ToolOutputFormatter()
        assert formatter.config.enabled is True
        assert formatter.config.truncate is True
        assert formatter.config.max_lines == 50
        assert formatter.config.show_timing is True

    def test_formatter_with_config(self):
        config = OutputConfig(
            enabled=False,
            truncate=False,
            max_lines=10,
            show_timing=False,
        )
        formatter = ToolOutputFormatter(config)
        assert formatter.config.enabled is False
        assert formatter.config.truncate is False

    def test_format_with_timing(self):
        formatter = ToolOutputFormatter()
        result = formatter.format("file_read", "content", timing_ms=150.5)
        
        assert result.timing_ms == 150.5

    def test_get_status_indicator(self):
        formatter = ToolOutputFormatter()
        
        assert formatter.get_status_indicator(ToolStatus.SUCCESS) == "✓"
        assert formatter.get_status_indicator(ToolStatus.ERROR) == "✗"
        assert formatter.get_status_indicator(ToolStatus.WARNING) == "⚠"
        assert formatter.get_status_indicator(ToolStatus.INFO) == "→"

    def test_get_status_style(self):
        formatter = ToolOutputFormatter()
        
        assert formatter.get_status_style(ToolStatus.SUCCESS) == "green"
        assert formatter.get_status_style(ToolStatus.ERROR) == "red"
        assert formatter.get_status_style(ToolStatus.WARNING) == "yellow"
        assert formatter.get_status_style(ToolStatus.INFO) == "cyan"
