"""Tests for Agent (ReAct loop orchestrator)."""

import pytest
from unittest.mock import MagicMock, patch

from coding_agent.agent import Agent


def _make_mock_display():
    """Create a mock streaming display context manager."""
    mock_display = MagicMock()
    mock_display.__enter__ = MagicMock(return_value=mock_display)
    mock_display.__exit__ = MagicMock(return_value=False)
    mock_display.full_text = ""
    return mock_display


class TestAgent:
    """Test Agent ReAct loop."""

    @patch("coding_agent.agent.get_openai_tools")
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

    @patch("coding_agent.agent.get_openai_tools")
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

    @patch("coding_agent.agent.get_openai_tools")
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

    @patch("coding_agent.agent.get_openai_tools")
    def test_run_tracks_consecutive_failures(self, mock_get_tools):
        """run() tracks consecutive failures for retry logic."""
        mock_llm = MagicMock()
        mock_conv = MagicMock()
        mock_renderer = MagicMock()

        agent = Agent(mock_llm, mock_conv, mock_renderer)
        assert agent.consecutive_failures == 0
        assert agent.max_retries == 3

    @patch("coding_agent.agent.get_openai_tools")
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

    @patch("coding_agent.agent.get_openai_tools")
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

        with patch("coding_agent.agent.execute_tool") as mock_exec:
            mock_exec.return_value = MagicMock(is_error=False, error=None, output="file1\nfile2")
            with patch("coding_agent.agent.PermissionSystem") as mock_perm_cls:
                mock_perm_cls.return_value.check_approval.return_value = True
                agent = Agent(mock_llm, mock_conv, mock_renderer)
                agent.run("list files")

        mock_renderer.render_separator.assert_called_once()
