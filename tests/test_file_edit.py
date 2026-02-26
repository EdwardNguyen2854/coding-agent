"""Tests for file_edit tool."""

import pytest
from pathlib import Path

from coding_agent.tools.file_edit import execute


class TestFileEdit:
    """Test file_edit tool."""

    def test_single_occurrence_replaced(self, tmp_path):
        """Test single occurrence is replaced."""
        f = tmp_path / "test.py"
        f.write_text("hello world")

        result = execute({"path": str(f), "old_string": "world", "new_string": "there"})

        assert result.is_error is False
        assert f.read_text() == "hello there"

    def test_multiple_occurrences_error(self, tmp_path):
        """Test multiple occurrences returns error with count."""
        f = tmp_path / "test.py"
        f.write_text("hello world world")

        result = execute({"path": str(f), "old_string": "world", "new_string": "there"})

        assert result.is_error is True
        assert "2 times" in result.error

    def test_no_occurrence_error(self, tmp_path):
        """Test no occurrence returns error."""
        f = tmp_path / "test.py"
        f.write_text("hello world")

        result = execute({"path": str(f), "old_string": "xyz", "new_string": "abc"})

        assert result.is_error is True
        assert "not found" in result.error.lower()

    def test_nonexistent_file_error(self):
        """Test nonexistent file returns error."""
        result = execute({"path": "/nonexistent/file.py", "old_string": "a", "new_string": "b"})

        assert result.is_error is True
        assert "resolves outside the workspace" in result.error.lower() or "not found" in result.error.lower()

    def test_empty_old_string_error(self, tmp_path):
        """Test empty old_string returns error."""
        f = tmp_path / "test.py"
        f.write_text("hello")

        result = execute({"path": str(f), "old_string": "", "new_string": "x"})

        assert result.is_error is True
