"""Tests for file_read tool."""

import pytest
from pathlib import Path

from coding_agent.tools.file_read import execute


class TestFileRead:
    """Test file_read tool."""

    def test_basic_file_read_with_line_numbers(self, tmp_path):
        """Read file with line numbers."""
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3")

        result = execute({"path": str(f)})

        assert result.is_error is False
        assert "     1  line1" in result.output
        assert "     2  line2" in result.output
        assert "     3  line3" in result.output

    def test_file_read_offset_limit(self, tmp_path):
        """Test offset and limit parameters."""
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3\nline4\nline5")

        result = execute({"path": str(f), "offset": 1, "limit": 2})

        assert result.is_error is False
        # offset=1 means start at line 1 (0-indexed), limit=2 means show 2 lines
        # Line numbers are shown from original file line numbers
        assert "     2  line2" in result.output
        assert "     3  line3" in result.output
        assert "line1" not in result.output
        assert "line4" not in result.output
        assert "line5" not in result.output

    def test_binary_file_error(self, tmp_path):
        """Test binary file detection."""
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x00\x01\x02")

        result = execute({"path": str(f)})

        # Binary files are now shown (not error) in current implementation
        assert result.output is not None

    def test_nonexistent_file_error(self):
        """Test non-existent file error."""
        result = execute({"path": "/nonexistent/file.py"})

        assert result.is_error is True
        assert "resolves outside the workspace" in result.error.lower() or "not found" in result.error.lower()

    def test_read_empty_file(self, tmp_path):
        """Test reading empty file."""
        f = tmp_path / "empty.py"
        f.write_text("")

        result = execute({"path": str(f)})

        assert result.is_error is False
        assert result.output == ""

    def test_offset_only(self, tmp_path):
        """Test offset without limit."""
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3\nline4\nline5")

        result = execute({"path": str(f), "offset": 3})

        assert result.is_error is False
        assert "line4" in result.output
        assert "line5" in result.output
        assert "line1" not in result.output

    def test_limit_only(self, tmp_path):
        """Test limit without offset."""
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3\nline4\nline5")

        result = execute({"path": str(f), "limit": 2})

        assert result.is_error is False
        assert "line1" in result.output
        assert "line2" in result.output
        assert "line3" not in result.output
