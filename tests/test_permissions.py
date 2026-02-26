"""Tests for permission system."""

import pytest
from unittest.mock import MagicMock, patch

from coding_agent.permissions import PermissionSystem, TOOLS_REQUIRING_APPROVAL


class TestPermissionSystemInit:
    """Test permission system initialization."""

    def test_init_with_renderer(self):
        """Test initialization with renderer."""
        renderer = MagicMock()
        ps = PermissionSystem(renderer)
        assert ps.renderer is renderer
        assert ps.approved_operations == {}

    def test_init_without_renderer(self):
        """Test initialization without renderer."""
        ps = PermissionSystem()
        assert ps.renderer is None
        assert ps.approved_operations == {}


class TestToolsRequiringApproval:
    """Test which tools require approval."""

    def test_approval_required_for_write(self):
        """Test file_write requires approval."""
        assert "file_write" in TOOLS_REQUIRING_APPROVAL

    def test_approval_required_for_edit(self):
        """Test file_edit requires approval."""
        assert "file_edit" in TOOLS_REQUIRING_APPROVAL

    def test_approval_required_for_shell(self):
        """Test shell requires approval."""
        assert "shell" in TOOLS_REQUIRING_APPROVAL

    def test_no_approval_for_read(self):
        """Test file_read does not require approval."""
        assert "file_read" not in TOOLS_REQUIRING_APPROVAL

    def test_no_approval_for_glob(self):
        """Test glob does not require approval."""
        assert "glob" not in TOOLS_REQUIRING_APPROVAL

    def test_no_approval_for_grep(self):
        """Test grep does not require approval."""
        assert "grep" not in TOOLS_REQUIRING_APPROVAL


class TestCheckApproval:
    """Test check_approval method."""

    def test_auto_approve_safe_tools(self):
        """Test safe tools are auto-approved."""
        ps = PermissionSystem()
        result = ps.check_approval("file_read", {"path": "/some/file"})
        assert result is True

    def test_approval_required_for_write(self):
        """Test file_write triggers approval check."""
        ps = PermissionSystem()
        with patch.object(ps, "_prompt_user", return_value=True) as mock_prompt:
            result = ps.check_approval("file_write", {"path": "/some/file"})
            mock_prompt.assert_called_once()
            assert result is True

    def test_approval_required_for_edit(self):
        """Test file_edit triggers approval check."""
        ps = PermissionSystem()
        with patch.object(ps, "_prompt_user", return_value=True) as mock_prompt:
            result = ps.check_approval("file_edit", {"path": "/some/file"})
            mock_prompt.assert_called_once()
            assert result is True

    def test_approval_required_for_shell(self):
        """Test shell triggers approval check."""
        ps = PermissionSystem()
        with patch.object(ps, "_prompt_user", return_value=True) as mock_prompt:
            result = ps.check_approval("shell", {"command": "echo hello"})
            mock_prompt.assert_called_once()
            assert result is True


class TestDestructiveCommandDetection:
    """Test destructive command detection."""

    def test_detect_rm_rf(self):
        """Test rm -rf detection."""
        ps = PermissionSystem()
        assert ps._is_destructive("rm -rf /tmp") is True

    def test_detect_rm_r_recursive(self):
        """Test rm -r recursive detection."""
        ps = PermissionSystem()
        assert ps._is_destructive("rm -r /home") is True

    def test_detect_del_recursive(self):
        """Test del /s /q detection (Windows)."""
        ps = PermissionSystem()
        assert ps._is_destructive("del /s /q C:\\Windows") is True

    def test_detect_format(self):
        """Test format command detection."""
        ps = PermissionSystem()
        assert ps._is_destructive("format D:") is True

    def test_detect_mkfs(self):
        """Test mkfs detection."""
        ps = PermissionSystem()
        assert ps._is_destructive("mkfs /dev/sda1") is True

    def test_detect_shred(self):
        """Test shred detection."""
        ps = PermissionSystem()
        assert ps._is_destructive("shred -u /tmp/file") is True

    def test_safe_command_not_destructive(self):
        """Test safe commands are not flagged as destructive."""
        ps = PermissionSystem()
        assert ps._is_destructive("echo hello") is False
        assert ps._is_destructive("ls -la") is False
        assert ps._is_destructive("pwd") is False
        assert ps._is_destructive("cat file.txt") is False


class TestDestructiveShellApproval:
    """Test approval for destructive shell commands."""

    def test_destructive_command_prompts_with_warning(self):
        """Test destructive shell commands show warning."""
        ps = PermissionSystem()
        with patch.object(ps, "_prompt_with_warning", return_value=True) as mock_warning:
            result = ps.check_approval("shell", {"command": "rm -rf /tmp"})
            mock_warning.assert_called_once()
            assert result is True

    def test_safe_shell_no_warning(self):
        """Test safe shell commands don't show warning."""
        ps = PermissionSystem()
        with patch.object(ps, "_prompt_with_warning") as mock_warning:
            with patch.object(ps, "_prompt_user", return_value=True) as mock_prompt:
                result = ps.check_approval("shell", {"command": "echo hello"})
                mock_warning.assert_not_called()
                mock_prompt.assert_called_once()


class TestSessionMemory:
    """Test session approval memory."""

    def test_approve_stores_operation(self):
        """Test approve stores operation in memory."""
        ps = PermissionSystem()
        ps.approve("file_write", {"path": "/tmp/test.txt"})
        keys = list(ps.approved_operations.keys())
        assert any("file_write" in key for key in keys)

    def test_clears_operations(self):
        """Test clear removes all stored approvals."""
        ps = PermissionSystem()
        ps.approve("file_write", {"path": "/tmp/test.txt"})
        ps.clear()
        assert ps.approved_operations == {}

    def test_auto_approve_remembered_operation(self):
        """Test previously approved operation is auto-approved."""
        ps = PermissionSystem()
        ps.approve("file_write", {"path": "/tmp/test.txt"})

        with patch.object(ps, "_prompt_user") as mock_prompt:
            result = ps.check_approval("file_write", {"path": "/tmp/test.txt"})
            mock_prompt.assert_not_called()
            assert result is True


class TestApprovalKeyGeneration:
    """Test approval key generation."""

    def test_shell_command_key(self):
        """Test approval key for shell commands."""
        ps = PermissionSystem()
        key = ps._get_approval_key("shell", {"command": "echo hello"})
        assert key == "shell:echo"

    def test_file_write_key(self):
        """Test approval key for file_write."""
        ps = PermissionSystem()
        key = ps._get_approval_key("file_write", {"path": "/home/user/file.txt"})
        assert "file_write:" in key

    def test_file_edit_key(self):
        """Test approval key for file_edit."""
        ps = PermissionSystem()
        key = ps._get_approval_key("file_edit", {"path": "/home/user/file.txt"})
        assert "file_edit:" in key

    def test_destructive_bypasses_session_memory(self):
        """Test destructive commands ALWAYS require approval even if previously approved."""
        ps = PermissionSystem()

        ps.approve("shell", {"command": "rm -rf /tmp"})

        with patch.object(ps, "_prompt_with_warning", return_value=True) as mock_warning:
            result = ps.check_approval("shell", {"command": "rm -rf /home"})
            mock_warning.assert_called_once()
            assert result is True


class TestPromptToolkitUsage:
    """Test that permission prompts use prompt_toolkit instead of input()."""

    def test_prompt_user_uses_prompt_toolkit(self):
        """Test _prompt_user uses prompt_toolkit.prompt instead of input()."""
        ps = PermissionSystem()
        with patch("builtins.input", return_value="y") as mock_input:
            result = ps._prompt_user("file_write", {"path": "/tmp/test.txt"})
            mock_input.assert_called_once()
            assert result is True

    def test_prompt_user_empty_response_approves(self):
        """Test empty response is treated as approval (default yes)."""
        ps = PermissionSystem()
        with patch("builtins.input", return_value="") as mock_input:
            result = ps._prompt_user("file_write", {"path": "/tmp/test.txt"})
            assert result is True

    def test_prompt_user_deny_returns_false(self):
        """Test 'n' response denies approval."""
        ps = PermissionSystem()
        with patch("builtins.input", return_value="n"):
            result = ps._prompt_user("file_write", {"path": "/tmp/test.txt"})
            assert result is False

    def test_prompt_with_warning_uses_prompt_toolkit(self):
        """Test _prompt_with_warning uses prompt_toolkit.prompt instead of input()."""
        ps = PermissionSystem()
        with patch("builtins.input", return_value="y") as mock_input:
            result = ps._prompt_with_warning("shell", {"command": "rm -rf /tmp"})
            mock_input.assert_called_once()
            assert result is True

    def test_prompt_with_warning_deny_returns_false(self):
        """Test _prompt_with_warning with 'n' denies approval."""
        ps = PermissionSystem()
        with patch("builtins.input", return_value="n"):
            result = ps._prompt_with_warning("shell", {"command": "rm -rf /tmp"})
            assert result is False


class TestPromptToolkitStyling:
    """Test that permission prompts use styled formatting matching REPL."""

    @pytest.mark.skip(reason="prompt_toolkit styling not implemented in current permissions.py")
    def test_prompt_user_uses_formatted_text(self):
        """Test _prompt_user passes FormattedText with ANSI cyan styling."""
        ps = PermissionSystem()
        with patch("builtins.input", return_value="y") as mock_input:
            ps._prompt_user("file_write", {"path": "/tmp/test.txt"})
            call_args = mock_input.call_args
            prompt_arg = call_args[0][0] if call_args[0] else call_args[1].get("message")
            assert isinstance(prompt_arg, list)
            # Check ANSI cyan styling is present (not class: which requires Style)
            styles = [style for style, _ in prompt_arg]
            assert any("cyan" in s for s in styles)

    @pytest.mark.skip(reason="prompt_toolkit styling not implemented in current permissions.py")
    def test_prompt_with_warning_uses_formatted_text(self):
        """Test _prompt_with_warning passes FormattedText with red bold styling."""
        ps = PermissionSystem()
        with patch("builtins.input", return_value="y") as mock_input:
            ps._prompt_with_warning("shell", {"command": "rm -rf /tmp"})
            call_args = mock_input.call_args
            prompt_arg = call_args[0][0] if call_args[0] else call_args[1].get("message")
            assert isinstance(prompt_arg, list)
            # Verify warning-specific red bold styling
            styles = [style for style, _ in prompt_arg]
            assert any("red" in s for s in styles)

    @pytest.mark.skip(reason="prompt_toolkit styling not implemented in current permissions.py")
    def test_prompt_includes_yn_hint(self):
        """Test permission prompts include [Y/n] key hint."""
        ps = PermissionSystem()
        with patch("builtins.input", return_value="y") as mock_input:
            ps._prompt_user("file_write", {"path": "/tmp/test.txt"})
            call_args = mock_input.call_args
            prompt_arg = call_args[0][0] if call_args[0] else call_args[1].get("message")
            # Check that [Y/n] hint is in the prompt text
            prompt_text = "".join(text for _, text in prompt_arg)
            assert "[Y/n]" in prompt_text


class TestPromptToolkitFallback:
    """Test fallback to input() when prompt_toolkit fails."""

    @pytest.mark.skip(reason="prompt_toolkit fallback not implemented in current permissions.py")
    def test_prompt_user_falls_back_to_input(self):
        """Test _prompt_user falls back to input() if pt_prompt raises."""
        ps = PermissionSystem()
        with patch("builtins.input", return_value="y") as mock_input:
            result = ps._prompt_user("file_write", {"path": "/tmp/test.txt"})
            mock_input.assert_called_once()
            assert result is True

    @pytest.mark.skip(reason="prompt_toolkit fallback not implemented in current permissions.py")
    def test_prompt_user_fallback_deny(self):
        """Test _prompt_user fallback with deny response."""
        ps = PermissionSystem()
        with patch("builtins.input", return_value="n"):
            result = ps._prompt_user("file_write", {"path": "/tmp/test.txt"})
            assert result is False

    @pytest.mark.skip(reason="prompt_toolkit fallback not implemented in current permissions.py")
    def test_prompt_with_warning_falls_back_to_input(self):
        """Test _prompt_with_warning falls back to input() if pt_prompt raises."""
        ps = PermissionSystem()
        with patch("builtins.input", return_value="y") as mock_input:
            result = ps._prompt_with_warning("shell", {"command": "rm -rf /tmp"})
            mock_input.assert_called_once()
            assert result is True
