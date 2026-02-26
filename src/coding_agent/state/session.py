"""Session management with SQLite persistence."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from coding_agent.state.db import Database
from coding_agent.state import schema

_log = logging.getLogger(__name__)

DEFAULT_SESSIONS_DIR = Path.home() / ".coding-agent" / "sessions"
DEFAULT_DB_PATH = Path.home() / ".coding-agent" / "sessions.db"
DEFAULT_SESSION_CAP = 50
_MAX_TITLE_LEN = 80


class SessionManager:
    """Manages session persistence with SQLite storage."""

    def __init__(
        self,
        db_path: Path | None = None,
        sessions_dir: Path | None = None,
        session_cap: int = DEFAULT_SESSION_CAP,
    ) -> None:
        """Initialize SessionManager.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.coding-agent/sessions.db
            sessions_dir: Deprecated. Directory for JSON sessions (legacy mode).
            session_cap: Maximum number of sessions to keep. Defaults to 50.
        """
        if sessions_dir is not None:
            _log.warning(
                "Using sessions_dir is deprecated. Please use db_path for SQLite storage."
            )
            self._legacy_mode = True
            self._sessions_dir = sessions_dir
            self._db: Database | None = None
            self._db_path = None
            self._ensure_sessions_dir()
        else:
            self._legacy_mode = False
            self._sessions_dir = sessions_dir
            self._db_path = db_path or DEFAULT_DB_PATH
            self._db = Database(self._db_path)
            schema.create_tables(self._db)
            self._ensure_compatibility()

        self._session_cap = session_cap
        self._seq = 0  # monotonic counter for legacy mode ordering

    def _ensure_compatibility(self) -> None:
        """Run migrations and check for JSON files to migrate."""
        if self._legacy_mode or self._db is None:
            return
        if not self._db.table_exists("sessions"):
            schema.create_tables(self._db)
        self._maybe_migrate_from_json()

    def _maybe_migrate_from_json(self) -> bool:
        """Migrate from JSON sessions if they exist and haven't been migrated.

        Returns:
            True if migration was performed.
        """
        if not DEFAULT_SESSIONS_DIR.exists():
            return False
        if not any(DEFAULT_SESSIONS_DIR.glob("*.json")):
            return False
        self.migrate_from_json(DEFAULT_SESSIONS_DIR)
        return True

    def migrate_from_json(self, sessions_dir: Path) -> dict[str, int]:
        """Migrate sessions from JSON files to SQLite.

        Args:
            sessions_dir: Directory containing JSON session files.

        Returns:
            Dict with migration stats: sessions_migrated, messages_migrated.
        """
        if self._legacy_mode:
            _log.warning("Migration not supported in legacy mode")
            return {"sessions_migrated": 0, "messages_migrated": 0}

        stats = {"sessions_migrated": 0, "messages_migrated": 0}

        if not sessions_dir.exists():
            _log.info("No sessions directory found, skipping migration")
            return stats

        json_files = list(sessions_dir.glob("*.json"))
        if not json_files:
            _log.info("No JSON session files found, skipping migration")
            return stats

        for json_file in json_files:
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                session_id = data.get("id", json_file.stem)
                messages = data.get("messages", [])

                now = datetime.now(timezone.utc).isoformat()
                self._db.execute(
                    """INSERT OR REPLACE INTO sessions
                       (id, title, model, created_at, updated_at, token_count, is_compacted)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session_id,
                        data.get("title", "Untitled"),
                        data.get("model", "unknown"),
                        data.get("created_at", now),
                        data.get("updated_at", now),
                        data.get("token_count", 0),
                        False,
                    ),
                )

                for msg in messages:
                    content = msg.get("content", "")
                    if content is None:
                        content = ""
                    self._db.execute(
                        """INSERT INTO messages
                           (session_id, role, content, token_count, created_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            session_id,
                            msg.get("role", "user"),
                            content,
                            self._estimate_tokens([msg]),
                            now,
                        ),
                    )
                    stats["messages_migrated"] += 1

                stats["sessions_migrated"] += 1
            except (json.JSONDecodeError, KeyError) as e:
                _log.warning("Failed to migrate session %s: %s", json_file.name, e)
                continue

        self._db.commit()

        backup_dir = sessions_dir.with_name(sessions_dir.name + ".backup")
        sessions_dir.rename(backup_dir)
        _log.info(
            "Migrated %d sessions, %d messages. Backed up to %s",
            stats["sessions_migrated"],
            stats["messages_migrated"],
            backup_dir,
        )

        return stats

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid.uuid4())

    def _generate_title(self, first_message: str) -> str:
        """Generate session title from first user message."""
        return first_message[:_MAX_TITLE_LEN] if first_message else "Untitled Session"

    def _estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Estimate token count using character heuristic."""
        total = 0
        for msg in messages:
            content = msg.get("content") or ""
            total += len(content) // 4
        return total

    def _get_session_path(self, session_id: str) -> Path:
        """Get path for a legacy session file."""
        return self._sessions_dir / f"{session_id}.json"

    def _atomic_write(self, path: Path, data: str) -> None:
        """Write to .tmp file, then rename. Safe on crash/Ctrl+C."""
        import os

        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(data, encoding="utf-8")
        os.replace(str(tmp_path), str(path))

    def create_session(
        self,
        first_message: str,
        model: str,
        messages: list[dict[str, Any]],
        sub_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new session.

        Args:
            first_message: First user message (used for title generation)
            model: LLM model being used
            messages: Initial conversation messages
            sub_agent_id: Optional sub-agent ID for multi-agent sessions

        Returns:
            Session dict with id, title, messages, created_at, updated_at, model, token_count
        """
        session_id = self._generate_session_id()
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        token_count = self._estimate_tokens(messages)

        if self._legacy_mode:
            session = {
                "id": session_id,
                "title": self._generate_title(first_message),
                "messages": messages,
                "created_at": now,
                "updated_at": now,
                "model": model,
                "token_count": token_count,
                "_seq": self._seq,
            }
            self._seq += 1
            self.save(session)
            self._prune_old_sessions()
            return session

        with self._db.transaction():
            self._db.execute(
                """INSERT INTO sessions
                   (id, title, model, created_at, updated_at, token_count, is_compacted)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    self._generate_title(first_message),
                    model,
                    now,
                    now,
                    token_count,
                    False,
                ),
            )

            for msg in messages:
                self._db.execute(
                    """INSERT INTO messages
                       (session_id, sub_agent_id, role, content, token_count, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        session_id,
                        sub_agent_id,
                        msg.get("role", "user"),
                        msg.get("content", ""),
                        self._estimate_tokens([msg]),
                        now,
                    ),
                )

        self._prune_old_sessions()
        return self.load(session_id)

    def save(
        self,
        session: dict[str, Any],
        new_messages: list[dict[str, Any]] | None = None,
        sub_agent_id: str | None = None,
    ) -> None:
        """Save session to storage.

        Args:
            session: Session dict to save
            new_messages: Optional new messages to append (SQLite mode only)
            sub_agent_id: Optional sub-agent ID for message routing
        """
        session_id = session["id"]
        now = datetime.now(timezone.utc).isoformat()

        if self._legacy_mode:
            session["updated_at"] = now
            session["token_count"] = self._estimate_tokens(session.get("messages", []))
            session_path = self._get_session_path(session_id)
            self._atomic_write(session_path, json.dumps(session, indent=2, ensure_ascii=False))
            return

        token_count = self._estimate_tokens(session.get("messages", []))

        with self._db.transaction():
            self._db.execute(
                """UPDATE sessions
                   SET title = ?, updated_at = ?, token_count = ?
                   WHERE id = ?""",
                (
                    session.get("title", "Untitled"),
                    now,
                    token_count,
                    session_id,
                ),
            )

            if new_messages:
                for msg in new_messages:
                    self._db.execute(
                        """INSERT INTO messages
                           (session_id, sub_agent_id, role, content, token_count, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            session_id,
                            sub_agent_id,
                            msg.get("role", "user"),
                            msg.get("content", ""),
                            self._estimate_tokens([msg]),
                            now,
                        ),
                    )

    def load(
        self,
        session_id: str,
        include_compacted: bool = False,
        sub_agent_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Load a session from storage.

        Args:
            session_id: Session ID to load
            include_compacted: If True, include messages marked as deleted
            sub_agent_id: Optional sub-agent ID to filter messages

        Returns:
            Session dict or None if not found
        """
        if self._legacy_mode:
            return self._load_json(session_id)

        row = self._db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

        if row is None:
            return None

        query = "SELECT * FROM messages WHERE session_id = ?"
        params: tuple[str, ...] = (session_id,)

        if not include_compacted:
            query += " AND is_deleted = FALSE"
        if sub_agent_id is not None:
            query += " AND (sub_agent_id = ? OR sub_agent_id IS NULL)"
            params = (session_id, sub_agent_id)

        query += " ORDER BY id ASC"
        msg_rows = self._db.execute(query, params).fetchall()

        messages = [
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "token_count": r["token_count"],
                "created_at": r["created_at"],
            }
            for r in msg_rows
        ]

        sub_agents = self.get_sub_agents(session_id)

        return {
            "id": row["id"],
            "title": row["title"],
            "model": row["model"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "token_count": row["token_count"],
            "is_compacted": row["is_compacted"],
            "original_token_count": row["original_token_count"],
            "max_tokens_before_compact": row["max_tokens_before_compact"],
            "messages": messages,
            "sub_agents": sub_agents,
        }

    def _load_json(self, session_id: str) -> dict[str, Any] | None:
        """Load session from JSON file (legacy mode)."""
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return None
        try:
            return json.loads(session_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def load_latest(self) -> dict[str, Any] | None:
        """Load the most recent session."""
        sessions = self.list()
        if not sessions:
            return None
        return self.load(sessions[0]["id"])

    def list(
        self,
        limit: int | None = None,
        model: str | None = None,
        is_compacted: bool | None = None,
    ) -> list[dict[str, Any]]:
        """List all saved sessions sorted by most recent.

        Args:
            limit: Maximum number of sessions to return
            model: Optional model filter
            is_compacted: Optional compaction status filter

        Returns:
            List of session dicts with id, title, created_at, updated_at, model, token_count
        """
        if self._legacy_mode:
            return self._list_json()

        query = "SELECT * FROM sessions WHERE 1=1"
        params: tuple = ()

        if model:
            query += " AND model = ?"
            params = (model,)
        if is_compacted is not None:
            query += " AND is_compacted = ?"
            params = (model, is_compacted) if model else (is_compacted,)

        query += " ORDER BY updated_at DESC"

        if limit:
            query += f" LIMIT {limit}"

        rows = self._db.execute(query, params).fetchall()

        return [
            {
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "model": r["model"],
                "token_count": r["token_count"],
                "is_compacted": r["is_compacted"],
            }
            for r in rows
        ]

    def _list_json(self) -> list[dict[str, Any]]:
        """List sessions from JSON files (legacy mode)."""
        if not self._sessions_dir.exists():
            return []

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
                    "_seq": data.get("_seq", -1),
                })
            except (json.JSONDecodeError, OSError):
                continue

        sessions.sort(key=lambda s: (s.get("updated_at", ""), s.get("_seq", -1)), reverse=True)
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False if not found
        """
        if self._legacy_mode:
            session_path = self._get_session_path(session_id)
            if not session_path.exists():
                return False
            session_path.unlink()
            return True

        row = self._db.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return False

        self._db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._db.commit()
        return True

    def _ensure_sessions_dir(self) -> None:
        """Create sessions directory if it doesn't exist (legacy mode)."""
        if self._sessions_dir:
            self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def _prune_old_sessions(self) -> None:
        """Remove oldest sessions if session count exceeds cap."""
        sessions = self.list()
        if len(sessions) <= self._session_cap:
            return
        to_delete = sessions[self._session_cap:]
        for session in to_delete:
            self.delete(session["id"])

    def compact(
        self,
        session_id: str,
        max_tokens: int = 64000,
    ) -> dict[str, Any] | None:
        """Compact a session by pruning old messages.

        Args:
            session_id: Session ID to compact
            max_tokens: Target token count after compaction

        Returns:
            Updated session dict or None if not found
        """
        session = self.load(session_id)
        if session is None:
            return None

        messages = session.get("messages", [])
        if not messages:
            return session

        system_messages = [m for m in messages if m.get("role") == "system"]
        other_messages = [m for m in messages if m.get("role") != "system"]

        current_tokens = sum(m.get("token_count", 0) for m in messages)

        for msg in other_messages[:]:
            if current_tokens <= max_tokens:
                break
            content = msg.get("content", "")
            msg_tokens = len(content) // 4
            current_tokens -= msg_tokens
            other_messages.remove(msg)

            self._db.execute(
                "UPDATE messages SET is_deleted = TRUE WHERE id = ?",
                (msg["id"],),
            )

        compacted_messages = system_messages + other_messages

        session["messages"] = compacted_messages
        session["token_count"] = current_tokens
        session["is_compacted"] = True

        if session.get("original_token_count") is None:
            session["original_token_count"] = session.get("token_count", 0)

        session["max_tokens_before_compact"] = max_tokens

        self._db.execute(
            """UPDATE sessions
               SET token_count = ?, is_compacted = TRUE,
                   original_token_count = ?, max_tokens_before_compact = ?
               WHERE id = ?""",
            (
                current_tokens,
                session.get("original_token_count"),
                max_tokens,
                session_id,
            ),
        )
        self._db.commit()

        return session

    def auto_compact(self, session_id: str, threshold: int | None = None) -> bool:
        """Auto-compact a session if token count exceeds threshold.

        Args:
            session_id: Session ID to check/compact
            threshold: Token threshold. Defaults to max_context_tokens from config.

        Returns:
            True if compaction was performed
        """
        if threshold is None:
            threshold = 128000

        row = self._db.execute(
            "SELECT token_count FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

        if row is None or row["token_count"] <= threshold:
            return False

        self.compact(session_id, threshold)
        return True

    def add_sub_agent(self, session_id: str, name: str, role: str) -> dict[str, Any]:
        """Add a sub-agent to a session.

        Args:
            session_id: Session ID
            name: Sub-agent name
            role: Sub-agent role/description

        Returns:
            Sub-agent dict with id
        """
        if self._legacy_mode:
            raise NotImplementedError("Sub-agents not supported in legacy mode")

        sub_agent_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        self._db.execute(
            """INSERT INTO sub_agents (id, session_id, name, role, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (sub_agent_id, session_id, name, role, now),
        )
        self._db.commit()

        return {
            "id": sub_agent_id,
            "session_id": session_id,
            "name": name,
            "role": role,
            "created_at": now,
        }

    def get_sub_agents(self, session_id: str) -> list[dict[str, Any]]:
        """Get all sub-agents for a session.

        Args:
            session_id: Session ID

        Returns:
            List of sub-agent dicts
        """
        if self._legacy_mode:
            return []

        rows = self._db.execute(
            "SELECT * FROM sub_agents WHERE session_id = ?", (session_id,)
        ).fetchall()

        return [
            {
                "id": r["id"],
                "session_id": r["session_id"],
                "name": r["name"],
                "role": r["role"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def remove_sub_agent(self, sub_agent_id: str) -> bool:
        """Remove a sub-agent from a session.

        Args:
            sub_agent_id: Sub-agent ID to remove

        Returns:
            True if removed
        """
        if self._legacy_mode:
            raise NotImplementedError("Sub-agents not supported in legacy mode")

        row = self._db.execute(
            "SELECT id FROM sub_agents WHERE id = ?", (sub_agent_id,)
        ).fetchone()
        if row is None:
            return False

        self._db.execute(
            "UPDATE messages SET is_deleted = TRUE WHERE sub_agent_id = ?",
            (sub_agent_id,),
        )
        self._db.execute("DELETE FROM sub_agents WHERE id = ?", (sub_agent_id,))
        self._db.commit()

        return True

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search sessions by title.

        Args:
            query: Search query

        Returns:
            Matching sessions
        """
        if self._legacy_mode:
            sessions = self._list_json()
            return [
                s for s in sessions
                if query.lower() in s.get("title", "").lower()
            ]

        rows = self._db.execute(
            "SELECT * FROM sessions WHERE title LIKE ? ORDER BY updated_at DESC",
            (f"%{query}%",),
        ).fetchall()

        return [
            {
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "model": r["model"],
                "token_count": r["token_count"],
                "is_compacted": r["is_compacted"],
            }
            for r in rows
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics.

        Returns:
            Stats dict with session counts and token totals
        """
        if self._legacy_mode:
            sessions = self._list_json()
            return {
                "total_sessions": len(sessions),
                "total_messages": sum(len(self._load_json(s["id"]).get("messages", [])) for s in sessions),
                "total_tokens": sum(s.get("token_count", 0) for s in sessions),
                "by_model": {},
                "sessions_compacted": 0,
            }

        total_sessions = self._db.execute(
            "SELECT COUNT(*) FROM sessions"
        ).fetchone()[0]

        total_messages = self._db.execute(
            "SELECT COUNT(*) FROM messages WHERE is_deleted = FALSE"
        ).fetchone()[0]

        total_tokens = self._db.execute(
            "SELECT SUM(token_count) FROM sessions"
        ).fetchone()[0] or 0

        sessions_compacted = self._db.execute(
            "SELECT COUNT(*) FROM sessions WHERE is_compacted = TRUE"
        ).fetchone()[0]

        model_rows = self._db.execute(
            "SELECT model, COUNT(*) as count FROM sessions GROUP BY model"
        ).fetchall()
        by_model = {r["model"]: r["count"] for r in model_rows}

        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "total_tokens": total_tokens,
            "by_model": by_model,
            "sessions_compacted": sessions_compacted,
        }

    def get_session_stats(self, session_id: str) -> dict[str, Any] | None:
        """Get statistics for a specific session.

        Args:
            session_id: Session ID

        Returns:
            Session stats dict or None if not found
        """
        if self._legacy_mode:
            session = self._load_json(session_id)
            if session is None:
                return None
            return {
                "session_id": session_id,
                "message_count": len(session.get("messages", [])),
                "token_count": session.get("token_count", 0),
                "sub_agent_count": 0,
                "is_compacted": False,
            }

        session_row = self._db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if session_row is None:
            return None

        message_count = self._db.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ? AND is_deleted = FALSE",
            (session_id,),
        ).fetchone()[0]

        sub_agent_count = self._db.execute(
            "SELECT COUNT(*) FROM sub_agents WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]

        return {
            "session_id": session_id,
            "message_count": message_count,
            "token_count": session_row["token_count"],
            "sub_agent_count": sub_agent_count,
            "is_compacted": session_row["is_compacted"],
            "original_token_count": session_row["original_token_count"],
            "max_tokens_before_compact": session_row["max_tokens_before_compact"],
        }

    def export_session(self, session_id: str) -> str | None:
        """Export a session to JSON format.

        Args:
            session_id: Session ID to export

        Returns:
            JSON string or None if not found
        """
        session = self.load(session_id, include_compacted=True)
        if session is None:
            return None
        return json.dumps(session, indent=2, ensure_ascii=False)

    def import_session(self, json_data: str) -> str | None:
        """Import a session from JSON format.

        Args:
            json_data: JSON string containing session data

        Returns:
            New session ID or None if import failed
        """
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            return None

        new_session_id = self._generate_session_id()
        now = datetime.now(timezone.utc).isoformat()

        if self._legacy_mode:
            data["id"] = new_session_id
            data["created_at"] = now
            data["updated_at"] = now
            self.save(data)
            return new_session_id

        self._db.execute(
            """INSERT INTO sessions
               (id, title, model, created_at, updated_at, token_count, is_compacted,
                original_token_count, max_tokens_before_compact)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_session_id,
                data.get("title", "Imported"),
                data.get("model", "unknown"),
                data.get("created_at", now),
                now,
                data.get("token_count", 0),
                data.get("is_compacted", False),
                data.get("original_token_count"),
                data.get("max_tokens_before_compact", 128000),
            ),
        )

        for msg in data.get("messages", []):
            self._db.execute(
                """INSERT INTO messages
                   (session_id, sub_agent_id, role, content, token_count, is_deleted, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_session_id,
                    msg.get("sub_agent_id"),
                    msg.get("role", "user"),
                    msg.get("content", ""),
                    msg.get("token_count", 0),
                    msg.get("is_deleted", False),
                    msg.get("created_at", now),
                ),
            )

        for agent in data.get("sub_agents", []):
            self._db.execute(
                """INSERT INTO sub_agents (id, session_id, name, role, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    agent.get("id", str(uuid.uuid4())),
                    new_session_id,
                    agent.get("name", "Sub-agent"),
                    agent.get("role", ""),
                    agent.get("created_at", now),
                ),
            )

        self._db.commit()
        return new_session_id

    def close(self) -> None:
        """Close database connection."""
        if self._db is not None:
            self._db.close()
