"""Tests for shell tool."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from coding_agent.tools import shell


class TestShellTool:
    """Test shell tool."""

    def test_shell_basic_command(self):
        """Test basic shell command execution."""
        result = shell.execute({"command": "echo hello"})
        assert result.is_error is False
        assert "hello" in result.output

    def test_shell_missing_command_error(self):
        """Test missing command returns error."""
        result = shell.execute({})
        assert result.is_error is True
        assert "required" in result.error.lower()

    def test_shell_cd_command(self, tmp_path):
        """Test cd command changes directory."""
        test_dir = tmp_path / "testsubdir"
        test_dir.mkdir()

        original_cwd = shell._cwd
        shell._cwd = tmp_path

        try:
            result = shell.execute({"command": "cd testsubdir"})
            assert result.is_error is False
            assert str(test_dir) in result.output
        finally:
            shell._cwd = original_cwd

    def test_shell_cd_nonexistent_directory(self):
        """Test cd to nonexistent directory returns error."""
        original_cwd = shell._cwd

        try:
            result = shell.execute({"command": "cd nonexistentdir12345"})
            assert result.is_error is True
            assert "no such directory" in result.error.lower()
        finally:
            shell._cwd = original_cwd

    def test_shell_cd_no_directory_specified(self):
        """Test cd with no directory returns current directory."""
        result = shell.execute({"command": "cd"})
        assert result.is_error is False
        assert str(shell._cwd) in result.output

    def test_shell_cd_parent_directory(self):
        """Test cd to parent directory."""
        original_cwd = shell._cwd

        try:
            parent = original_cwd.parent
            result = shell.execute({"command": "cd .."})
            assert result.is_error is False
            assert str(parent) in result.output
        finally:
            shell._cwd = original_cwd

    def test_shell_stdout_stderr_capture(self):
        """Test stdout and stderr are captured."""
        result = shell.execute({"command": "echo stdout && echo stderr >&2"})
        assert result.is_error is False
        assert "stdout" in result.output
        assert "stderr" in result.output

    def test_shell_timeout_parameter(self):
        """Test timeout parameter is accepted."""
        result = shell.execute({"command": "echo test", "timeout": 60})
        assert result.is_error is False
        assert "test" in result.output

    def test_shell_timeout_expired(self):
        """Test command timeout."""
        result = shell.execute({"command": "ping -n 10 127.0.0.1", "timeout": 1})
        assert result.is_error is True
        assert "timed out" in result.error.lower()

    def test_shell_invalid_command_error(self):
        """Test invalid command returns error or output with error message."""
        result = shell.execute({"command": "invalidcmdthatdoesnotexist12345"})
        assert result.is_error is True or "not recognized" in result.output

    def test_shell_output_truncation(self):
        """Test output is truncated at 30000 chars."""
        large_output = "a" * 40000

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = large_output
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = shell.execute({"command": "echo test"})

            assert "truncated" in result.output.lower()
            assert len(result.output) <= 31000


class TestShellToolPlatformSpecific:
    """Test platform-specific shell commands."""

    def test_windows_shell_command(self):
        """Test Windows shell uses cmd /c."""
        import platform

        if platform.system() != "Windows":
            pytest.skip("Windows-specific test")

        result = shell.execute({"command": "dir"})
        assert result.is_error is False

    def test_unix_shell_command(self):
        """Test Unix shell uses bash -c."""
        import platform

        if platform.system() != "Windows":
            result = shell.execute({"command": "ls"})
            assert result.is_error is False
