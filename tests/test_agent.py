"""Tests for Agent (ReAct loop orchestrator)."""

import pytest
from unittest.mock import MagicMock, patch

from coding_agent.agent import Agent


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
