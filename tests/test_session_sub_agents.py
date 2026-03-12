"""Tests for SessionManager sub-agent methods."""

import tempfile
from pathlib import Path

import pytest

from coding_agent.state.session import SessionManager


@pytest.fixture
def sm(tmp_path):
    """SQLite-backed SessionManager (non-legacy)."""
    return SessionManager(db_path=tmp_path / "sessions.db")


@pytest.fixture
def sm_legacy(tmp_path):
    """Legacy JSON-backed SessionManager."""
    return SessionManager(sessions_dir=tmp_path / "sessions")


@pytest.fixture
def session(sm):
    return sm.create_session(first_message="hello", model="test", messages=[])


class TestGetSubAgentByName:
    def test_returns_none_when_not_found(self, sm, session):
        result = sm.get_sub_agent_by_name(session["id"], "nonexistent")
        assert result is None

    def test_returns_sub_agent_after_add(self, sm, session):
        sm.add_sub_agent(session["id"], "reviewer", "Expert code reviewer")
        result = sm.get_sub_agent_by_name(session["id"], "reviewer")

        assert result is not None
        assert result["name"] == "reviewer"
        assert result["role"] == "Expert code reviewer"
        assert result["session_id"] == session["id"]
        assert "id" in result
        assert "created_at" in result

    def test_returns_none_for_different_session(self, sm):
        s1 = sm.create_session("s1", "test", [])
        s2 = sm.create_session("s2", "test", [])
        sm.add_sub_agent(s1["id"], "dev", "Developer")

        result = sm.get_sub_agent_by_name(s2["id"], "dev")
        assert result is None

    def test_returns_none_in_legacy_mode(self, sm_legacy):
        result = sm_legacy.get_sub_agent_by_name("any-session-id", "dev")
        assert result is None

    def test_name_lookup_is_exact(self, sm, session):
        sm.add_sub_agent(session["id"], "reviewer", "Reviewer")

        assert sm.get_sub_agent_by_name(session["id"], "review") is None
        assert sm.get_sub_agent_by_name(session["id"], "REVIEWER") is None
        assert sm.get_sub_agent_by_name(session["id"], "reviewer") is not None


class TestAddAndGetSubAgents:
    def test_add_sub_agent_returns_dict(self, sm, session):
        result = sm.add_sub_agent(session["id"], "tester", "QA Engineer")

        assert result["name"] == "tester"
        assert result["role"] == "QA Engineer"
        assert result["session_id"] == session["id"]
        assert "id" in result
        assert "created_at" in result

    def test_get_sub_agents_empty(self, sm, session):
        assert sm.get_sub_agents(session["id"]) == []

    def test_get_sub_agents_multiple(self, sm, session):
        sm.add_sub_agent(session["id"], "dev", "Developer")
        sm.add_sub_agent(session["id"], "reviewer", "Reviewer")

        agents = sm.get_sub_agents(session["id"])
        assert len(agents) == 2
        names = {a["name"] for a in agents}
        assert names == {"dev", "reviewer"}

    def test_get_sub_agents_isolated_per_session(self, sm):
        s1 = sm.create_session("s1", "test", [])
        s2 = sm.create_session("s2", "test", [])
        sm.add_sub_agent(s1["id"], "dev", "Developer")

        assert sm.get_sub_agents(s2["id"]) == []


class TestRemoveSubAgent:
    def test_remove_returns_true(self, sm, session):
        agent = sm.add_sub_agent(session["id"], "dev", "Developer")
        assert sm.remove_sub_agent(agent["id"]) is True

    def test_remove_deletes_record(self, sm, session):
        agent = sm.add_sub_agent(session["id"], "dev", "Developer")
        sm.remove_sub_agent(agent["id"])

        assert sm.get_sub_agents(session["id"]) == []
        assert sm.get_sub_agent_by_name(session["id"], "dev") is None

    def test_remove_nonexistent_returns_false(self, sm):
        assert sm.remove_sub_agent("nonexistent-id") is False
