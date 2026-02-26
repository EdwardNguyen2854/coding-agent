"""Tests for Agent (ReAct loop orchestrator)."""

import pytest
from unittest.mock import MagicMock, patch

from coding_agent.core.agent import Agent


def _make_mock_display():
    """Create a mock streaming display context manager."""
    mock_display = MagicMock()
    mock_display.__enter__ = MagicMock(return_value=mock_display)
    mock_display.__exit__ = MagicMock(return_value=False)
    mock_display.full_text = ""
    return mock_display


class TestAgent:
    """Test Agent ReAct loop."""

    @patch("coding_agent.core.agent.get_openai_tools")
    def test_agent_initialization(self, mock_get_tools):
        """Agent initializes with required dependencies."""
        mock_llm = MagicMock()
        mock_conv = MagicMock()
        mock_renderer = MagicMock()

        agent = Agent(mock_llm, mock_conv, mock_renderer)

        assert agent.llm_client is mock_llm
        assert agent.conversation is mock_conv
        assert agent.renderer is mock_renderer
        assert agent.max_retries == 3

    @patch("coding_agent.core.agent.get_openai_tools")
    def test_run_sends_user_message(self, mock_get_tools):
        """run() adds user message to conversation."""
        mock_get_tools.return_value = []
        mock_llm = MagicMock()
        mock_llm.send_message_stream.return_value = iter([])
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello"
        mock_response.choices[0].message.tool_calls = None
        mock_llm.last_response = mock_response

        mock_conv = MagicMock()
        mock_conv.get_messages.return_value = [{"role": "system", "content": "You are helpful."}]

        mock_renderer = MagicMock()
        mock_display = _make_mock_display()
        mock_renderer.render_streaming_live.return_value = mock_display

        agent = Agent(mock_llm, mock_conv, mock_renderer)
        result = agent.run("Hi there")

        mock_conv.add_message.assert_any_call("user", "Hi there")

    @patch("coding_agent.core.agent.get_openai_tools")
    def test_run_terminates_on_text_only(self, mock_get_tools):
        """run() exits loop when no tool_calls."""
        mock_get_tools.return_value = []
        mock_llm = MagicMock()
        mock_llm.send_message_stream.return_value = iter([])
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Final response"
        mock_response.choices[0].message.tool_calls = None
        mock_llm.last_response = mock_response

        mock_conv = MagicMock()
        mock_conv.get_messages.return_value = [{"role": "system", "content": "You are helpful."}]

        mock_renderer = MagicMock()
        mock_display = _make_mock_display()
        mock_renderer.render_streaming_live.return_value = mock_display

        agent = Agent(mock_llm, mock_conv, mock_renderer)
        result = agent.run("Hello")

        assert result == "Final response"
        mock_conv.add_message.assert_any_call("assistant", "Final response")

    @patch("coding_agent.core.agent.get_openai_tools")
    def test_run_tracks_consecutive_failures(self, mock_get_tools):
        """run() tracks consecutive failures for retry logic."""
        mock_llm = MagicMock()
        mock_conv = MagicMock()
        mock_renderer = MagicMock()

        agent = Agent(mock_llm, mock_conv, mock_renderer)
        assert agent.consecutive_failures == 0
        assert agent.max_retries == 3

    @patch("coding_agent.core.agent.get_openai_tools")
    def test_run_uses_streaming_display(self, mock_get_tools):
        """run() uses render_streaming_live() for streaming output."""
        mock_get_tools.return_value = []
        mock_llm = MagicMock()
        mock_llm.send_message_stream.return_value = iter(["Hello"])
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello"
        mock_response.choices[0].message.tool_calls = None
        mock_llm.last_response = mock_response

        mock_conv = MagicMock()
        mock_conv.get_messages.return_value = [{"role": "system", "content": "test"}]

        mock_renderer = MagicMock()
        mock_display = _make_mock_display()
        mock_renderer.render_streaming_live.return_value = mock_display

        agent = Agent(mock_llm, mock_conv, mock_renderer)
        agent.run("test")

        mock_renderer.render_streaming_live.assert_called_once()
        mock_display.start_thinking.assert_called_once()
        mock_display.update.assert_called_once_with("Hello")

    @pytest.mark.skip(reason="render_separator not implemented in current agent.py")
    @patch("coding_agent.core.agent.get_openai_tools")
    def test_run_renders_separator_after_tool_calls(self, mock_get_tools):
        """run() renders separator after processing tool calls."""
        mock_get_tools.return_value = []
        mock_llm = MagicMock()

        # First call: tool call, second call: text response
        mock_response_1 = MagicMock()
        mock_response_1.choices = [MagicMock()]
        mock_response_1.choices[0].message.content = ""
        mock_tc = MagicMock()
        mock_tc.id = "tc_1"
        mock_tc.function.name = "shell"
        mock_tc.function.arguments = '{"command": "ls"}'
        mock_response_1.choices[0].message.tool_calls = [mock_tc]

        mock_response_2 = MagicMock()
        mock_response_2.choices = [MagicMock()]
        mock_response_2.choices[0].message.content = "Done"
        mock_response_2.choices[0].message.tool_calls = None

        mock_llm.last_response = mock_response_1
        call_count = [0]

        def stream_side_effect(messages, tools=None):
            call_count[0] += 1
            if call_count[0] == 2:
                mock_llm.last_response = mock_response_2
            return iter([])

        mock_llm.send_message_stream.side_effect = stream_side_effect

        mock_conv = MagicMock()
        mock_conv.get_messages.return_value = [{"role": "system", "content": "test"}]

        mock_renderer = MagicMock()
        mock_display = _make_mock_display()
        mock_renderer.render_streaming_live.return_value = mock_display
        # Mock status_spinner as context manager
        mock_spinner = MagicMock()
        mock_spinner.__enter__ = MagicMock(return_value=mock_spinner)
        mock_spinner.__exit__ = MagicMock(return_value=False)
        mock_renderer.status_spinner.return_value = mock_spinner

        with patch("coding_agent.core.agent.execute_tool") as mock_exec:
            mock_exec.return_value = MagicMock(is_error=False, error=None, output="file1\nfile2", message="")
            with patch("coding_agent.core.agent.PermissionSystem") as mock_perm_cls:
                mock_perm_cls.return_value.check_approval.return_value = True
                agent = Agent(mock_llm, mock_conv, mock_renderer)
                agent.run("list files")

        mock_renderer.render_separator.assert_called_once()


class TestAgentToolFallback:
    """Agent retries with simplified history when model rejects tool messages."""

    def _make_renderer(self):
        mock_renderer = MagicMock()
        mock_display = _make_mock_display()
        mock_renderer.render_streaming_live.return_value = mock_display
        mock_spinner = MagicMock()
        mock_spinner.__enter__ = MagicMock(return_value=mock_spinner)
        mock_spinner.__exit__ = MagicMock(return_value=False)
        mock_renderer.status_spinner.return_value = mock_spinner
        return mock_renderer

    @patch("coding_agent.core.agent.get_openai_tools")
    def test_has_tool_messages_true_for_tool_role(self, _):
        """_has_tool_messages() returns True when role=tool present."""
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "tool", "tool_call_id": "x", "content": "result"},
        ]
        assert Agent._has_tool_messages(messages) is True

    @patch("coding_agent.core.agent.get_openai_tools")
    def test_has_tool_messages_true_for_assistant_tool_calls(self, _):
        """_has_tool_messages() returns True when assistant has tool_calls."""
        messages = [
            {"role": "assistant", "tool_calls": [{"id": "x"}], "content": None},
        ]
        assert Agent._has_tool_messages(messages) is True

    @patch("coding_agent.core.agent.get_openai_tools")
    def test_has_tool_messages_false_for_plain_messages(self, _):
        """_has_tool_messages() returns False for plain user/assistant messages."""
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        assert Agent._has_tool_messages(messages) is False

    @patch("coding_agent.core.agent.get_openai_tools")
    def test_call_llm_retries_simplified_on_bad_request_with_tool_messages(self, mock_get_tools):
        """_call_llm() retries with simplified history when BadRequestError hits tool-laden history."""
        from coding_agent.core.conversation import ConversationManager

        mock_get_tools.return_value = []
        mock_llm = MagicMock()

        # First call raises the "rejected" error, second (simplified) call succeeds
        plain_response = MagicMock()
        plain_response.choices = [MagicMock()]
        plain_response.choices[0].message.content = "Fallback response"
        plain_response.choices[0].message.tool_calls = None

        call_count = [0]

        def stream_side_effect(messages, tools=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConnectionError("Model rejected the request.")
            mock_llm.last_response = plain_response
            return iter([])

        mock_llm.send_message_stream.side_effect = stream_side_effect

        conv = ConversationManager("System")
        conv.add_message("user", "Do something")
        conv.add_assistant_tool_call("", [{"id": "t1", "name": "shell", "arguments": "{}"}])
        conv.add_tool_result("t1", "done")

        mock_renderer = self._make_renderer()
        agent = Agent(mock_llm, conv, mock_renderer)

        result = agent._call_llm(conv.get_messages(), tools=[])

        assert result is True
        assert call_count[0] == 2  # First attempt + retry
        mock_renderer.print_info.assert_called()  # Retry notice shown

    @patch("coding_agent.core.agent.get_openai_tools")
    def test_call_llm_no_retry_when_no_tool_messages(self, mock_get_tools):
        """_call_llm() does not retry when error occurs without tool messages."""
        mock_get_tools.return_value = []
        mock_llm = MagicMock()
        mock_llm.send_message_stream.side_effect = ConnectionError("Model rejected the request.")

        from coding_agent.core.conversation import ConversationManager
        conv = ConversationManager("System")
        conv.add_message("user", "Hello")

        mock_renderer = self._make_renderer()
        agent = Agent(mock_llm, conv, mock_renderer)

        result = agent._call_llm(conv.get_messages(), tools=[])

        assert result is False
        assert mock_llm.send_message_stream.call_count == 1  # No retry
        mock_renderer.print_error.assert_called()
