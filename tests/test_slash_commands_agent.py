"""Tests for the /agent slash command."""

from unittest.mock import MagicMock

import pytest

import coding_agent.tools.spawn_sub_agent as ssa_module
from coding_agent.tools.spawn_sub_agent import is_team_mode, set_team_mode
from coding_agent.ui.slash_commands import cmd_agent
from coding_agent.state.session import SessionManager


@pytest.fixture(autouse=True)
def reset_team_mode():
    """Ensure team mode is off before each test."""
    ssa_module._context.team_mode = False
    yield
    ssa_module._context.team_mode = False


@pytest.fixture
def sm(tmp_path):
    return SessionManager(db_path=tmp_path / "sessions.db")


@pytest.fixture
def renderer():
    r = MagicMock()
    r.console = MagicMock()
    return r


@pytest.fixture
def conversation():
    return MagicMock()


@pytest.fixture
def agent_with_session(sm):
    """Mock agent with an active session containing sub-agents."""
    session = sm.create_session("test", "model", [])
    sm.add_sub_agent(session["id"], "reviewer", "Code reviewer")
    sm.add_sub_agent(session["id"], "tester", "QA Engineer")
    agent = MagicMock()
    agent.session_data = session
    return agent, session


@pytest.fixture
def agent_no_session():
    agent = MagicMock()
    agent.session_data = None
    return agent


class TestAgentTeamMode:
    def test_team_mode_on(self, conversation, sm, renderer):
        cmd_agent("team-mode on", conversation, sm, renderer)
        assert is_team_mode() is True
        renderer.print_info.assert_called_once()
        msg = renderer.print_info.call_args[0][0]
        assert "Team mode ON" in msg

    def test_team_mode_off(self, conversation, sm, renderer):
        set_team_mode(True)
        cmd_agent("team-mode off", conversation, sm, renderer)
        assert is_team_mode() is False
        renderer.print_info.assert_called_once()
        msg = renderer.print_info.call_args[0][0]
        assert "Solo dev mode" in msg

    def test_team_mode_invalid_arg(self, conversation, sm, renderer):
        cmd_agent("team-mode maybe", conversation, sm, renderer)
        renderer.print_error.assert_called_once()
        assert is_team_mode() is False  # unchanged

    def test_team_mode_missing_arg(self, conversation, sm, renderer):
        cmd_agent("team-mode", conversation, sm, renderer)
        renderer.print_error.assert_called_once()

    def test_returns_true(self, conversation, sm, renderer):
        result = cmd_agent("team-mode on", conversation, sm, renderer)
        assert result is True


class TestAgentList:
    def test_list_with_sub_agents(self, conversation, sm, renderer, agent_with_session):
        agent, session = agent_with_session
        cmd_agent("list", conversation, sm, renderer, agent=agent)
        renderer.console.print.assert_called_once()

    def test_list_empty(self, conversation, sm, renderer):
        session = sm.create_session("test", "model", [])
        agent = MagicMock()
        agent.session_data = session
        cmd_agent("list", conversation, sm, renderer, agent=agent)
        renderer.print_info.assert_called_once()
        assert "No sub-agents" in renderer.print_info.call_args[0][0]

    def test_list_no_session(self, conversation, sm, renderer, agent_no_session):
        cmd_agent("list", conversation, sm, renderer, agent=agent_no_session)
        renderer.print_info.assert_called_once()
        assert "No active session" in renderer.print_info.call_args[0][0]

    def test_list_no_agent(self, conversation, sm, renderer):
        cmd_agent("list", conversation, sm, renderer, agent=None)
        renderer.print_info.assert_called_once()


class TestAgentStatus:
    def test_status_shows_solo_mode_by_default(self, conversation, sm, renderer):
        agent = MagicMock()
        agent.session_data = None
        cmd_agent("status", conversation, sm, renderer, agent=agent)
        calls = [c[0][0] for c in renderer.print_info.call_args_list]
        assert any("Solo dev mode" in c for c in calls)

    def test_status_shows_team_mode_when_on(self, conversation, sm, renderer):
        set_team_mode(True)
        agent = MagicMock()
        agent.session_data = None
        cmd_agent("status", conversation, sm, renderer, agent=agent)
        calls = [c[0][0] for c in renderer.print_info.call_args_list]
        assert any("Team mode" in c for c in calls)

    def test_status_shows_sub_agent_count(self, conversation, sm, renderer, agent_with_session):
        agent, _ = agent_with_session
        cmd_agent("status", conversation, sm, renderer, agent=agent)
        calls = [c[0][0] for c in renderer.print_info.call_args_list]
        assert any("2" in c for c in calls)

    def test_status_default_when_no_args(self, conversation, sm, renderer):
        agent = MagicMock()
        agent.session_data = None
        result = cmd_agent("", conversation, sm, renderer, agent=agent)
        assert result is True
        renderer.print_info.assert_called()


class TestAgentUnknownSubcommand:
    def test_unknown_subcommand_prints_error(self, conversation, sm, renderer):
        cmd_agent("foobar", conversation, sm, renderer)
        renderer.print_error.assert_called_once()

    def test_returns_true_on_unknown(self, conversation, sm, renderer):
        result = cmd_agent("foobar", conversation, sm, renderer)
        assert result is True
