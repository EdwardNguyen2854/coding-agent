"""Stability tests for Phase 2 fixes."""

from unittest.mock import MagicMock, patch


class TestPermissionEOF:
    """Test that permission prompts handle EOF gracefully."""

    def test_permission_prompt_handles_eof(self):
        """_prompt_user returns False when input() raises EOFError."""
        from coding_agent.permissions import PermissionSystem

        ps = PermissionSystem()
        with patch("builtins.input", side_effect=EOFError):
            result = ps._prompt_user("file_write", {"path": "/tmp/test.txt"})
        assert result is False

    def test_permission_prompt_with_warning_handles_eof(self):
        """_prompt_with_warning returns False when input() raises EOFError."""
        from coding_agent.permissions import PermissionSystem

        ps = PermissionSystem()
        with patch("builtins.input", side_effect=EOFError):
            result = ps._prompt_with_warning("shell", {"command": "rm -rf /"})
        assert result is False


class TestTruncateLoop:
    """Test that truncate_if_needed terminates when no progress is made."""

    def test_truncate_terminates_on_no_progress(self):
        """Loop exits when removal returns False immediately (nothing to prune)."""
        from coding_agent.conversation import ConversationManager

        conv = ConversationManager("system prompt")
        # Patch _estimate_tokens to always return a large value and
        # _prune_oldest_tool_output / _remove_oldest_message_pair to return False.
        with (
            patch.object(conv, "_estimate_tokens", return_value=999999),
            patch.object(conv, "_prune_oldest_tool_output", return_value=False),
            patch.object(conv, "_remove_oldest_message_pair", return_value=False),
        ):
            # Should return without infinite loop
            conv.truncate_if_needed(max_tokens=1000)
        # If we reach here, the loop terminated correctly

    def test_truncate_exits_when_estimate_stagnates(self):
        """Loop exits when estimate stops decreasing even if removals return True."""
        from coding_agent.conversation import ConversationManager

        conv = ConversationManager("system prompt")
        call_count = [0]

        def fake_estimate():
            # Always return the same value, simulating no progress
            return 999999

        with (
            patch.object(conv, "_estimate_tokens", side_effect=fake_estimate),
            patch.object(conv, "_prune_oldest_tool_output", return_value=True),
            patch.object(conv, "_remove_oldest_message_pair", return_value=True),
        ):
            conv.truncate_if_needed(max_tokens=1000)
        # Loop should have broken due to estimate == prev_estimate


class TestDiffPreviewException:
    """Test that diff preview exceptions do not propagate."""

    def test_diff_preview_exception_does_not_propagate(self):
        """OSError in diff preview is logged but not raised."""
        from coding_agent.agent import Agent

        llm_client = MagicMock()
        conversation = MagicMock()
        conversation.get_messages.return_value = []
        conversation.truncate_if_needed = MagicMock()

        renderer = MagicMock()
        renderer.render_streaming_live.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        renderer.render_streaming_live.return_value.__exit__ = MagicMock(
            return_value=False
        )
        renderer.status_spinner.return_value.__enter__ = MagicMock(
            return_value=None
        )
        renderer.status_spinner.return_value.__exit__ = MagicMock(return_value=False)

        agent = Agent(llm_client, conversation, renderer)
        agent.permissions = MagicMock()
        agent.permissions.check_approval.return_value = True

        tool_call = MagicMock()
        tool_call.function.name = "file_edit"
        tool_call.function.arguments = '{"path": "/nonexistent/file.txt", "old_string": "x", "new_string": "y"}'
        tool_call.id = "tc1"

        mock_result = MagicMock()
        mock_result.is_error = False
        mock_result.error = None
        mock_result.output = "ok"
        mock_result.message = ""  # Add message attribute
        with patch("coding_agent.agent.execute_tool", return_value=mock_result):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text", side_effect=OSError("permission denied")):
                    # Should not raise
                    agent._handle_tool_call(tool_call)
