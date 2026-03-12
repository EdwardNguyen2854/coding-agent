"""Tests for the sidebar toolbar, including sub-agent indicator."""

from unittest.mock import MagicMock

import pytest

from coding_agent.ui.sidebar import make_toolbar
from coding_agent.workflow import WorkflowState


def _text(parts):
    """Concatenate text portions of (style, text) tuples."""
    return "".join(t for _, t in parts)


def _styles(parts):
    """Return list of (style, text) for non-empty styles only."""
    return [(s, t) for s, t in parts if s]


@pytest.fixture
def mock_conversation():
    conv = MagicMock()
    conv.token_count = 5000
    return conv


@pytest.fixture
def mock_workflow():
    wf = MagicMock()
    wf.state = WorkflowState.IDLE
    wf.todo_list.total = 0
    return wf


class TestToolbarWithoutSubAgent:
    def test_shows_context_and_branch(self, mock_conversation, mock_workflow):
        toolbar = make_toolbar(mock_conversation, mock_workflow, branch="main")
        parts = toolbar()
        text = _text(parts)

        assert "Context:" in text
        assert "5,000" in text
        assert "Branch: main" in text

    def test_no_sub_agent_prefix_when_none(self, mock_conversation, mock_workflow):
        toolbar = make_toolbar(
            mock_conversation, mock_workflow, branch="main",
            get_active_sub_agent=lambda: None,
        )
        parts = toolbar()
        text = _text(parts)

        assert "Sub-agent:" not in text

    def test_no_sub_agent_prefix_when_getter_not_provided(self, mock_conversation, mock_workflow):
        toolbar = make_toolbar(mock_conversation, mock_workflow, branch="main")
        parts = toolbar()
        text = _text(parts)

        assert "Sub-agent:" not in text

    def test_context_percentage_shown(self, mock_workflow):
        conv = MagicMock()
        conv.token_count = 64000  # 50% of 128000
        toolbar = make_toolbar(conv, mock_workflow, branch="main", context_limit=128000)
        parts = toolbar()
        text = _text(parts)

        assert "50.0%" in text

    def test_ctx_style_green_below_warning(self, mock_workflow):
        conv = MagicMock()
        conv.token_count = 1000  # well below 70%
        toolbar = make_toolbar(conv, mock_workflow, branch="main", context_limit=128000)
        parts = toolbar()

        ctx_part = next((s for s, t in parts if "fg:ansigreen" in s), None)
        assert ctx_part is not None

    def test_ctx_style_red_above_critical(self, mock_workflow):
        conv = MagicMock()
        conv.token_count = 120000  # above 90%
        toolbar = make_toolbar(conv, mock_workflow, branch="main", context_limit=128000)
        parts = toolbar()

        ctx_part = next((s for s, t in parts if "fg:ansired" in s), None)
        assert ctx_part is not None


class TestToolbarWithSubAgent:
    def test_sub_agent_name_shown_at_start(self, mock_conversation, mock_workflow):
        toolbar = make_toolbar(
            mock_conversation, mock_workflow, branch="main",
            get_active_sub_agent=lambda: "reviewer",
        )
        parts = toolbar()
        text = _text(parts)

        assert "Sub-agent: Reviewer" in text

    def test_sub_agent_name_capitalized(self, mock_conversation, mock_workflow):
        toolbar = make_toolbar(
            mock_conversation, mock_workflow, branch="main",
            get_active_sub_agent=lambda: "backend-dev",
        )
        parts = toolbar()
        text = _text(parts)

        assert "Sub-agent: Backend-dev" in text

    def test_sub_agent_comes_before_context(self, mock_conversation, mock_workflow):
        toolbar = make_toolbar(
            mock_conversation, mock_workflow, branch="main",
            get_active_sub_agent=lambda: "reviewer",
        )
        parts = toolbar()
        text = _text(parts)

        sub_pos = text.index("Sub-agent:")
        ctx_pos = text.index("Context:")
        assert sub_pos < ctx_pos

    def test_sub_agent_separator_pipe(self, mock_conversation, mock_workflow):
        toolbar = make_toolbar(
            mock_conversation, mock_workflow, branch="main",
            get_active_sub_agent=lambda: "dev",
        )
        parts = toolbar()
        text = _text(parts)

        # Format: "Sub-agent: Dev | Context: ..."
        assert " | " in text

    def test_sub_agent_style_is_magenta(self, mock_conversation, mock_workflow):
        toolbar = make_toolbar(
            mock_conversation, mock_workflow, branch="main",
            get_active_sub_agent=lambda: "reviewer",
        )
        parts = toolbar()
        magenta_parts = [(s, t) for s, t in parts if "ansimagenta" in s]

        assert len(magenta_parts) > 0
        assert any("Sub-agent" in t for _, t in magenta_parts)

    def test_context_still_shown_with_sub_agent(self, mock_conversation, mock_workflow):
        toolbar = make_toolbar(
            mock_conversation, mock_workflow, branch="main",
            get_active_sub_agent=lambda: "dev",
        )
        parts = toolbar()
        text = _text(parts)

        assert "Context:" in text
        assert "Branch: main" in text
