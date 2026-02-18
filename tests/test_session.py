"""Tests for SessionManager."""

import json
import tempfile
from pathlib import Path

import pytest

from coding_agent.session import SessionManager


class TestSessionManager:
    """Verify SessionManager behavior for session persistence."""

    @pytest.fixture
    def temp_sessions_dir(self):
        """Create a temporary sessions directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def session_manager(self, temp_sessions_dir):
        """Create a SessionManager with temp directory."""
        return SessionManager(sessions_dir=temp_sessions_dir)

    def test_create_session(self, session_manager):
        """create_session() creates a new session with all required fields."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]

        session = session_manager.create_session(
            first_message="Hello, world! This is my first message.",
            model="litellm/gpt-4o",
            messages=messages,
        )

        assert "id" in session
        assert session["title"] == "Hello, world! This is my first message."
        assert session["model"] == "litellm/gpt-4o"
        assert session["messages"] == messages
        assert "created_at" in session
        assert "updated_at" in session
        assert "token_count" in session

    def test_create_session_title_truncated_to_80_chars(self, session_manager):
        """create_session() truncates title to 80 characters."""
        long_message = "a" * 100
        session = session_manager.create_session(
            first_message=long_message,
            model="test",
            messages=[],
        )

        assert len(session["title"]) == 80

    def test_save_and_load(self, session_manager, temp_sessions_dir):
        """save() and load() roundtrip works correctly."""
        session = session_manager.create_session(
            first_message="Test session",
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
        )

        loaded = session_manager.load(session["id"])

        assert loaded is not None
        assert loaded["id"] == session["id"]
        assert loaded["title"] == session["title"]
        assert loaded["messages"] == session["messages"]

    def test_load_nonexistent(self, session_manager):
        """load() returns None for nonexistent session."""
        result = session_manager.load("nonexistent-id")
        assert result is None

    def test_list_sessions(self, session_manager):
        """list() returns all sessions sorted by most recent."""
        session_manager.create_session("First", "model", [])
        session_manager.create_session("Second", "model", [])
        session_manager.create_session("Third", "model", [])

        sessions = session_manager.list()

        assert len(sessions) == 3
        # Most recent first
        assert sessions[0]["title"] == "Third"
        assert sessions[1]["title"] == "Second"
        assert sessions[2]["title"] == "First"

    def test_delete_session(self, session_manager):
        """delete() removes a session."""
        session = session_manager.create_session("To delete", "model", [])
        session_id = session["id"]

        result = session_manager.delete(session_id)
        assert result is True

        loaded = session_manager.load(session_id)
        assert loaded is None

    def test_delete_nonexistent(self, session_manager):
        """delete() returns False for nonexistent session."""
        result = session_manager.delete("nonexistent-id")
        assert result is False

    def test_session_cap(self, temp_sessions_dir):
        """Prunes old sessions when cap is exceeded."""
        manager = SessionManager(sessions_dir=temp_sessions_dir, session_cap=3)

        for i in range(5):
            manager.create_session(f"Session {i}", "model", [])

        sessions = manager.list()
        assert len(sessions) == 3
        # Most recent 3 should remain
        assert sessions[0]["title"] == "Session 4"
        assert sessions[1]["title"] == "Session 3"
        assert sessions[2]["title"] == "Session 2"

    def test_atomic_write(self, session_manager, temp_sessions_dir):
        """Atomic write pattern - .tmp file is renamed to final path."""
        session = session_manager.create_session("Atomic test", "model", [])

        # Check .tmp file doesn't exist
        tmp_files = list(temp_sessions_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

        # Check final file exists
        session_file = temp_sessions_dir / f"{session['id']}.json"
        assert session_file.exists()

    def test_estimate_tokens(self, session_manager):
        """_estimate_tokens() uses len//4 heuristic."""
        messages = [
            {"role": "user", "content": "Hello"},  # 5 chars
            {"role": "assistant", "content": "Hi there"},  # 8 chars
        ]

        tokens = session_manager._estimate_tokens(messages)
        # 5 + 8 = 13 // 4 = 3
        assert tokens == 3

    def test_sessions_directory_created(self, temp_sessions_dir):
        """Sessions directory is created if it doesn't exist."""
        sessions_dir = temp_sessions_dir / "new_sessions_dir"
        manager = SessionManager(sessions_dir=sessions_dir)

        assert sessions_dir.exists()
