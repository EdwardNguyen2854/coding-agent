"""SQL schema definitions for session storage."""

from __future__ import annotations

CREATE_SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""

CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    is_compacted BOOLEAN DEFAULT FALSE,
    original_token_count INTEGER,
    max_tokens_before_compact INTEGER DEFAULT 128000,
    runtime_config TEXT
);
"""

CREATE_SUB_AGENTS_TABLE = """
CREATE TABLE IF NOT EXISTS sub_agents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
"""

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    sub_agent_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (sub_agent_id) REFERENCES sub_agents(id) ON DELETE SET NULL
);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_title ON sessions(title);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_sub_agent ON messages(sub_agent_id);
CREATE INDEX IF NOT EXISTS idx_sub_agents_session ON sub_agents(session_id);
"""

ALL_SCHEMA_STATEMENTS = [
    CREATE_SCHEMA_MIGRATIONS,
    CREATE_SESSIONS_TABLE,
    CREATE_SUB_AGENTS_TABLE,
    CREATE_MESSAGES_TABLE,
    CREATE_INDEXES,
]


def create_tables(db: "Database") -> None:
    """Create all database tables and indexes.

    Args:
        db: Database instance.
    """
    for statement in ALL_SCHEMA_STATEMENTS:
        db.execute(statement)
    db.commit()
