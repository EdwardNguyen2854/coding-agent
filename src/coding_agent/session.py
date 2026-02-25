"""Session management for persisting conversation history."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

DEFAULT_SESSIONS_DIR = Path.home() / ".coding-agent" / "sessions"
DEFAULT_SESSION_CAP = 50
_MAX_TITLE_LEN = 80


class SessionManager:
    """Manages session persistence with atomic writes."""

    def __init__(self, sessions_dir: Path | None = None, session_cap: int = DEFAULT_SESSION_CAP):
        """Initialize SessionManager.

        Args:
            sessions_dir: Directory to store sessions. Defaults to ~/.coding-agent/sessions/
            session_cap: Maximum number of sessions to keep. Defaults to 50.
        """
        self._sessions_dir = sessions_dir or DEFAULT_SESSIONS_DIR
        self._session_cap = session_cap
        self._ensure_sessions_dir()

    def _ensure_sessions_dir(self) -> None:
        """Create sessions directory if it doesn't exist."""
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, path: Path, data: str) -> None:
        """Write to .tmp file, then rename. Safe on crash/Ctrl+C."""
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(data, encoding="utf-8")
        os.replace(str(tmp_path), str(path))

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid.uuid4())

    def _generate_title(self, first_message: str) -> str:
        """Generate session title from first user message, truncated to _MAX_TITLE_LEN chars."""
        return first_message[:_MAX_TITLE_LEN] if first_message else "Untitled Session"

    def _get_session_path(self, session_id: str) -> Path:
        """Get path for a session file."""
        return self._sessions_dir / f"{session_id}.json"

    def create_session(self, first_message: str, model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Create a new session.

        Args:
            first_message: First user message (used for title generation)
            model: LLM model being used
            messages: Initial conversation messages

        Returns:
            Session dict with id, title, messages, created_at, updated_at, model, token_count
        """
        session_id = self._generate_session_id()
        now = datetime.now(timezone.utc).isoformat()

        session = {
            "id": session_id,
            "title": self._generate_title(first_message),
            "messages": messages,
            "created_at": now,
            "updated_at": now,
            "model": model,
            "token_count": self._estimate_tokens(messages),
        }

        self.save(session)
        self._prune_old_sessions()

        return session

    def save(self, session: dict[str, Any]) -> None:
        """Save session to disk with atomic write.

        Args:
            session: Session dict to save
        """
        session_id = session["id"]
        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        session["token_count"] = self._estimate_tokens(session.get("messages", []))

        session_path = self._get_session_path(session_id)
        self._ensure_sessions_dir()

        self._atomic_write(session_path, json.dumps(session, indent=2, ensure_ascii=False))

    def load(self, session_id: str) -> dict[str, Any] | None:
        """Load a session from disk.

        Args:
            session_id: Session ID to load

        Returns:
            Session dict or None if not found
        """
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            return None

        try:
            data = session_path.read_text(encoding="utf-8")
            return json.loads(data)
        except (json.JSONDecodeError, OSError):
            return None

    def load_latest(self) -> dict[str, Any] | None:
        """Load the most recent session.

        Returns:
            Most recent session dict or None if no sessions exist
        """
        sessions = self.list()
        if not sessions:
            return None

        latest_id = sessions[0]["id"]
        return self.load(latest_id)

    def list(self) -> list[dict[str, Any]]:
        """List all saved sessions sorted by most recent.

        Returns:
            List of session dicts with id, title, created_at, updated_at, model, token_count
        """
        sessions = []

        for session_file in self._sessions_dir.glob("*.json"):
            if session_file.suffix == ".tmp":
                continue

            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                sessions.append({
                    "id": data.get("id", session_file.stem),
                    "title": data.get("title", "Untitled"),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "model": data.get("model", "unknown"),
                    "token_count": data.get("token_count", 0),
                })
            except (json.JSONDecodeError, OSError) as e:
                _log.debug("Skipping session %s: %s", session_file, e)
                continue

        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False if not found
        """
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            return False

        session_path.unlink()
        return True

    def _prune_old_sessions(self) -> None:
        """Remove oldest sessions if session count exceeds cap."""
        sessions = self.list()

        if len(sessions) <= self._session_cap:
            return

        to_delete = sessions[self._session_cap:]
        for session in to_delete:
            self.delete(session["id"])

    def _estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Estimate token count using character heuristic (len/4)."""
        total = 0
        for msg in messages:
            content = msg.get("content") or ""
            total += len(content) // 4
        return total
