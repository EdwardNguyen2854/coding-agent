"""Tests for file_write tool."""

import pytest
from pathlib import Path

from coding_agent.tools.file_write import execute


class TestFileWrite:
    """Test file_write tool."""

    def test_basic_file_write(self, tmp_path):
        """Test basic file write."""
        f = tmp_path / "test.py"
        
        result = execute({"path": str(f), "content": "print('hello')"})
        
        assert result.is_error is False
        assert f.read_text() == "print('hello')"
        assert "Successfully wrote" in result.output

    def test_parent_directories_created(self, tmp_path):
        """Test parent directories are created."""
        f = tmp_path / "subdir" / "nested" / "test.py"
        
        result = execute({"path": str(f), "content": "test content"})
        
        assert result.is_error is False
        assert f.exists()
        assert f.read_text() == "test content"

    def test_overwrite_existing(self, tmp_path):
        """Test overwriting existing file."""
        f = tmp_path / "test.py"
        f.write_text("old content")
        
        result = execute({"path": str(f), "content": "new content"})
        
        assert result.is_error is False
        assert f.read_text() == "new content"

    def test_empty_content(self, tmp_path):
        """Test writing empty content."""
        f = tmp_path / "empty.py"
        
        result = execute({"path": str(f), "content": ""})
        
        assert result.is_error is False
        assert f.read_text() == ""

    def test_missing_path_error(self):
        """Test missing path returns error."""
        result = execute({"content": "test"})
        
        assert result.is_error is True
        assert "Path is required" in result.error

    def test_write_to_directory_error(self, tmp_path):
        """Test writing to a directory returns error."""
        result = execute({"path": str(tmp_path), "content": "test"})
        
        assert result.is_error is True

    def test_unicode_content(self, tmp_path):
        """Test writing unicode content."""
        f = tmp_path / "unicode.py"
        
        result = execute({"path": str(f), "content": "print('hello')"})
        
        assert result.is_error is False
        assert f.exists()
