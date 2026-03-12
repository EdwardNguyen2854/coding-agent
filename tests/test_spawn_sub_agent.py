"""Tests for the spawn_sub_agent tool."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import coding_agent.tools.spawn_sub_agent as ssa_module
from coding_agent.tools.spawn_sub_agent import (
    SpawnSubAgentTool,
    get_active_sub_agent_name,
    is_team_mode,
    set_team_mode,
    setup_spawn_sub_agent,
    update_session_data,
)
from coding_agent.state.session import SessionManager


@pytest.fixture(autouse=True)
def reset_module_state():
    """Reset all module-level globals before each test."""
    ssa_module._llm_client = None
    ssa_module._session_manager = None
    ssa_module._session_data = None
    ssa_module._config = None
    ssa_module._workspace_root = None
    ssa_module._renderer = None
    ssa_module._team_mode = False
    ssa_module._active_sub_agent_name = None
    yield
    # Cleanup after test
    ssa_module._team_mode = False
    ssa_module._active_sub_agent_name = None


@pytest.fixture
def sqlite_session_manager(tmp_path):
    db_path = tmp_path / "sessions.db"
    return SessionManager(db_path=db_path)


@pytest.fixture
def mock_renderer():
    renderer = MagicMock()
    renderer.console = MagicMock()
    return renderer


@pytest.fixture
def mock_llm_client():
    return MagicMock()


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.model = "test-model"
    return config


@pytest.fixture
def active_session(sqlite_session_manager):
    return sqlite_session_manager.create_session(
        first_message="hello", model="test-model", messages=[]
    )


@pytest.fixture
def initialized_tool(sqlite_session_manager, mock_llm_client, mock_config, mock_renderer, active_session):
    """Tool with all dependencies set up and team mode on."""
    setup_spawn_sub_agent(mock_llm_client, sqlite_session_manager, mock_config, "/tmp", mock_renderer)
    update_session_data(active_session)
    set_team_mode(True)
    return SpawnSubAgentTool()


class TestTeamModeToggle:
    def test_team_mode_off_by_default(self):
        assert is_team_mode() is False

    def test_set_team_mode_on(self):
        set_team_mode(True)
        assert is_team_mode() is True

    def test_set_team_mode_off(self):
        set_team_mode(True)
        set_team_mode(False)
        assert is_team_mode() is False


class TestActiveSubAgentName:
    def test_none_when_idle(self):
        assert get_active_sub_agent_name() is None


class TestSpawnSubAgentToolBlocked:
    def test_blocked_when_team_mode_off(self, sqlite_session_manager, mock_llm_client, mock_config, mock_renderer, active_session):
        setup_spawn_sub_agent(mock_llm_client, sqlite_session_manager, mock_config, "/tmp", mock_renderer)
        update_session_data(active_session)
        # team_mode is False (default)
        tool = SpawnSubAgentTool()
        result = tool.run({"name": "dev", "role": "Developer", "task": "do something"})
        assert result.ok is False
        assert result.error_code == "TEAM_MODE_DISABLED"

    def test_blocked_when_not_initialized(self):
        set_team_mode(True)
        # globals remain None
        tool = SpawnSubAgentTool()
        result = tool.run({"name": "dev", "role": "Developer", "task": "do something"})
        assert result.ok is False
        assert result.error_code == "NOT_INITIALIZED"

    def test_blocked_when_no_session(self, sqlite_session_manager, mock_llm_client, mock_config, mock_renderer):
        setup_spawn_sub_agent(mock_llm_client, sqlite_session_manager, mock_config, "/tmp", mock_renderer)
        # session_data left as None
        set_team_mode(True)
        tool = SpawnSubAgentTool()
        result = tool.run({"name": "dev", "role": "Developer", "task": "do something"})
        assert result.ok is False
        assert result.error_code == "NO_SESSION"


class TestSpawnSubAgentToolRun:
    def test_creates_sub_agent_record(self, initialized_tool, sqlite_session_manager, active_session):
        with patch("coding_agent.core.agent.Agent") as MockAgent:
            MockAgent.return_value.run.return_value = "Task done."
            initialized_tool.run({"name": "reviewer", "role": "Code reviewer", "task": "Review code"})

        agents = sqlite_session_manager.get_sub_agents(active_session["id"])
        assert len(agents) == 1
        assert agents[0]["name"] == "reviewer"
        assert agents[0]["role"] == "Code reviewer"

    def test_returns_success_with_result(self, initialized_tool):
        with patch("coding_agent.core.agent.Agent") as MockAgent:
            MockAgent.return_value.run.return_value = "All checks passed."
            result = initialized_tool.run({"name": "tester", "role": "Tester", "task": "Run tests"})

        assert result.ok is True
        assert result.data["result"] == "All checks passed."
        assert result.data["sub_agent"] == "tester"

    def test_reuses_existing_sub_agent_by_name(self, initialized_tool, sqlite_session_manager, active_session):
        with patch("coding_agent.core.agent.Agent") as MockAgent:
            MockAgent.return_value.run.return_value = "done"
            initialized_tool.run({"name": "reviewer", "role": "Reviewer", "task": "task 1"})
            initialized_tool.run({"name": "reviewer", "role": "Reviewer", "task": "task 2"})

        agents = sqlite_session_manager.get_sub_agents(active_session["id"])
        assert len(agents) == 1  # No duplicate

    def test_active_name_cleared_after_run(self, initialized_tool):
        with patch("coding_agent.core.agent.Agent") as MockAgent:
            MockAgent.return_value.run.return_value = "done"
            initialized_tool.run({"name": "dev", "role": "Developer", "task": "build"})

        assert get_active_sub_agent_name() is None

    def test_active_name_set_during_run(self, initialized_tool):
        captured = []

        def fake_run(task):
            captured.append(get_active_sub_agent_name())
            return "done"

        with patch("coding_agent.core.agent.Agent") as MockAgent:
            MockAgent.return_value.run.side_effect = fake_run
            initialized_tool.run({"name": "worker", "role": "Worker", "task": "work"})

        assert captured == ["worker"]

    def test_active_name_cleared_on_error(self, initialized_tool):
        with patch("coding_agent.core.agent.Agent") as MockAgent:
            MockAgent.return_value.run.side_effect = RuntimeError("boom")
            result = initialized_tool.run({"name": "dev", "role": "Dev", "task": "fail"})

        assert result.ok is False
        assert result.error_code == "SUB_AGENT_ERROR"
        assert get_active_sub_agent_name() is None

    def test_context_passed_to_sub_agent_conversation(self, initialized_tool):
        built_conversations = []

        def capture_agent(llm_client, conversation, renderer, config, workspace_root):
            built_conversations.append(conversation)
            agent = MagicMock()
            agent.run.return_value = "done"
            return agent

        with patch("coding_agent.core.agent.Agent", side_effect=capture_agent):
            initialized_tool.run({
                "name": "dev", "role": "Developer", "task": "build it",
                "context": "relevant snippet here",
            })

        assert len(built_conversations) == 1
        msgs = built_conversations[0].get_messages()
        # system prompt (role) + context user msg + ack assistant msg
        assert msgs[0]["role"] == "system"
        assert "Developer" in msgs[0]["content"]
        assert any("relevant snippet here" in m.get("content", "") for m in msgs)

    def test_result_summary_panel_printed(self, initialized_tool, mock_renderer):
        with patch("coding_agent.core.agent.Agent") as MockAgent:
            MockAgent.return_value.run.return_value = "Here is my analysis."
            initialized_tool.run({"name": "analyst", "role": "Analyst", "task": "analyze"})

        mock_renderer.console.print.assert_called()

    def test_messages_persisted_to_db(self, initialized_tool, sqlite_session_manager, active_session):
        with patch("coding_agent.core.agent.Agent") as MockAgent:
            MockAgent.return_value.run.return_value = "done"
            initialized_tool.run({"name": "dev", "role": "Dev", "task": "build"})

        # Load with sub_agent_id filter — messages should exist
        agents = sqlite_session_manager.get_sub_agents(active_session["id"])
        assert len(agents) == 1
        loaded = sqlite_session_manager.load(active_session["id"], sub_agent_id=agents[0]["id"])
        assert loaded is not None
