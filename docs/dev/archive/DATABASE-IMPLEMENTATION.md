# Implementation Plan: SQLite Session Storage

This document outlines the step-by-step implementation for migrating from JSON file storage to SQLite.

---

## Phase 1: Foundation (Core SQLite Support)

**Goal**: Replace JSON files with SQLite while maintaining backward compatibility.

### 1.1 Database Module (`db.py`)

- [ ] Create `src/coding_agent/db.py`
- [ ] Implement `Database` class with:
  - `__init__(db_path: Path)` - establish connection
  - `execute(query, params)` - parameterized queries
  - `executemany(query, params)` - batch operations
  - `commit()` / `rollback()` - transaction control
  - `close()` - connection cleanup
- [ ] **WAL mode**: Enable with `PRAGMA journal_mode=WAL`
- [ ] **Auto-vacuum**: OFF by default (add manual VACUUM later)
- [ ] Add foreign keys: `PRAGMA foreign_keys=ON`
- [ ] Add schema migrations table:
  ```sql
  CREATE TABLE schema_migrations (
      version INTEGER PRIMARY KEY,
      applied_at TEXT NOT NULL
  );
  ```

### 1.2 Schema Definition

- [ ] Create `src/coding_agent/schema.py` with SQL statements
- [ ] Implement `create_tables()` function:
  ```sql
  CREATE TABLE sessions (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      model TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      token_count INTEGER DEFAULT 0,
      is_compacted BOOLEAN DEFAULT FALSE,
      original_token_count INTEGER,
      max_tokens_before_compact INTEGER DEFAULT 128000
  );

  CREATE TABLE sub_agents (
      id TEXT PRIMARY KEY,
      session_id TEXT NOT NULL,
      name TEXT NOT NULL,
      role TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
  );

  CREATE TABLE messages (
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

  CREATE INDEX idx_sessions_updated ON sessions(updated_at DESC);
  CREATE INDEX idx_sessions_title ON sessions(title);
  CREATE INDEX idx_messages_session ON messages(session_id);
  CREATE INDEX idx_messages_sub_agent ON messages(sub_agent_id);
  CREATE INDEX idx_sub_agents_session ON sub_agents(session_id);
  ```

### 1.3 SessionManager Refactor

- [ ] Refactor `src/coding_agent/session.py`:
  - Add `db_path` parameter to `__init__`
  - Add `sessions_dir` parameter for legacy mode
  - Implement `_init_db()` - create tables if not exist
  - Implement `_ensure_compatibility()` - run migrations

### 1.4 CRUD Operations

- [ ] Implement `create_session()`:
  - Insert into `sessions` table
  - Insert all messages into `messages` table
  - Return session dict with messages
- [ ] Implement `save()`:
  - Update `sessions` row
  - Insert new messages (don't overwrite all - append only)
  - Use transaction for atomicity
- [ ] Implement `load()`:
  - SELECT from sessions + messages tables
  - Join sub_agents if any
  - Filter out `is_deleted=True` messages by default
- [ ] Implement `list()`:
  - SELECT from sessions ordered by updated_at DESC
  - Support `limit` parameter for pagination
- [ ] Implement `delete()`:
  - CASCADE deletes messages and sub_agents

### 1.5 Migration from JSON

- [ ] Implement `migrate_from_json(sessions_dir: Path)`:
  - Detect if `sessions/` directory exists
  - Read each JSON file
  - Parse messages and insert into SQLite
  - Track migration stats
  - Rename `sessions/` to `sessions.backup/`
  - Log summary: "Migrated X sessions, Y messages"
- [ ] Add migration trigger on first SQLite load
- [ ] Add `--migrate` CLI flag to force re-migration

### 1.6 Backward Compatibility

- [ ] Default to SQLite at `~/.coding-agent/sessions.db`
- [ ] If `db_path` provided, use SQLite
- [ ] If `sessions_dir` provided, use legacy JSON mode
- [ ] Log warning when using legacy mode

---

## Phase 2: Compaction Support

**Goal**: Implement `/compact` command and auto-compact with SQLite storage.

### 2.1 Compact Method

- [ ] Implement `compact(session_id: str, max_tokens: int = 64000)`:
  - Load all non-deleted messages
  - Calculate current token count
  - Apply compaction strategy (from conversation.py):
    1. Prune old tool outputs (truncate to `_MAX_TOOL_OUTPUT_CHARS`)
    2. Remove oldest user/assistant message pairs
    3. Never remove system prompt
  - Mark removed messages as `is_deleted=TRUE`
  - Update `sessions` table:
    - `token_count` = new count
    - `is_compacted = TRUE`
    - `original_token_count` = before count (if first compact)
    - `max_tokens_before_compact` = threshold used
  - Return compacted session dict

### 2.2 Auto-Compact

- [ ] Implement `auto_compact(session_id: str, threshold: int | None = None)`:
  - Default threshold from config `max_context_tokens`
  - Check if `token_count > threshold`
  - If yes, call `compact()` with threshold
  - Return `True` if compaction performed

### 2.3 Integration with Existing Code

- [ ] Update `slash_commands.py`:
  - Modify `cmd_compact()` to call `session_manager.compact()`
- [ ] Update `agent.py`:
  - Modify auto-compact call to use `session_manager.auto_compact()`
- [ ] Update `conversation.py`:
  - Keep in-memory truncation as fallback
  - Optionally persist truncation to SQLite

### 2.4 Load with Compaction History

- [ ] Implement `load(session_id: str, include_compacted: bool = False)`:
  - Default excludes `is_deleted` messages
  - When `include_compacted=True`, return all messages for debugging

---

## Phase 3: Multi-Sub-Agent Support

**Goal**: Enable multiple agents per session with isolated conversation threads.

### 3.1 Sub-Agent CRUD

- [ ] Implement `add_sub_agent(session_id: str, name: str, role: str)`:
  - Insert into `sub_agents` table
  - Return sub_agent dict with id
- [ ] Implement `get_sub_agents(session_id: str)`:
  - SELECT from sub_agents for session
  - Return list of sub_agent dicts
- [ ] Implement `remove_sub_agent(sub_agent_id: str)`:
  - Soft-delete: set `is_deleted=TRUE` on messages
  - Delete sub_agent row (or soft-delete)
  - Return success bool

### 3.2 Message Routing

- [ ] Modify `create_session()` to accept optional `sub_agent_id`
- [ ] Modify `save()` to accept `sub_agent_id` parameter
- [ ] Modify `load()` to filter by `sub_agent_id`:
  ```python
  def load(self, session_id: str, sub_agent_id: str | None = None) -> dict | None:
      # If sub_agent_id provided, only return messages for that agent
      # If None, return all messages (merged view)
  ```

### 3.3 Agent Integration

- [ ] Update `Agent` class to accept `sub_agent_id`
- [ ] Update `ConversationManager` to track sub-agent context
- [ ] Update CLI to support sub-agent commands:
  - `/agent add <name> <role>` - create sub-agent
  - `/agent list` - show sub-agents
  - `/agent switch <id>` - switch active sub-agent

---

## Phase 4: Query & Search

**Goal**: Enable powerful querying of session history.

### 4.1 Query Methods

- [ ] Implement `search(query: str)`:
  - Full-text search on session titles
  - Use SQL `LIKE` or FTS5 if needed
  - Return matching sessions
- [ ] Implement `list_by_model(model: str)`:
  - Filter sessions by model
  - Support wildcards
- [ ] Implement `list_by_date_range(start: str, end: str)`:
  - Filter by `created_at` or `updated_at`
  - ISO format dates
- [ ] Implement `list_compacted()`:
  - Filter sessions where `is_compacted = TRUE`

### 4.2 Statistics

- [ ] Implement `get_stats()`:
  - Total sessions count
  - Total messages count
  - Total tokens across all sessions
  - Breakdown by model
  - Sessions compacted count
- [ ] Implement `get_session_stats(session_id: str)`:
  - Message count
  - Token count
  - Sub-agent count
  - Compaction history

---

## Phase 5: Cleanup & Optimization

**Goal**: Remove legacy code and optimize performance.

### 5.1 JSON Removal

- [ ] Add deprecation warning when using `sessions_dir`
- [ ] Remove JSON fallback code
- [ ] Remove migration logic (one-time operation done)
- [ ] Update CLI to remove `--migrate` flag

### 5.2 Export/Import

- [ ] Implement `export_session(session_id: str) -> str`:
  - Export to JSON format
  - Include messages, sub_agents, compaction metadata
- [ ] Implement `import_session(json_data: str) -> str`:
  - Import from JSON
  - Return new session_id
- [ ] Add CLI commands:
  - `coding-agent sessions export <id>` - export to file
  - `coding-agent sessions import <file>` - import from file

### 5.3 Performance Tuning

- [ ] Analyze query patterns
- [ ] Add additional indexes if needed
- [ ] Consider VACUUM scheduling
- [ ] Add connection pooling if needed

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `src/coding_agent/db.py` | New | Database connection & queries |
| `src/coding_agent/schema.py` | New | SQL schema definitions |
| `src/coding_agent/session.py` | Modify | Refactor to use SQLite |
| `src/coding_agent/slash_commands.py` | Modify | Integrate compact |
| `src/coding_agent/agent.py` | Modify | Integrate auto-compact |
| `src/coding_agent/config.py` | Modify | Add db_path config option |
| `tests/test_session.py` | Modify | Update tests for SQLite |
| `tests/test_db.py` | New | Database unit tests |

---

## Testing Strategy

### Unit Tests
- Database connection & transactions
- CRUD operations
- Migration from JSON
- Compaction logic
- Sub-agent operations

### Integration Tests
- End-to-end session lifecycle
- Compact command flow
- Multi-sub-agent scenarios

### Manual Tests
- Migration from existing sessions
- Performance comparison (JSON vs SQLite)
- Concurrent access

---

## Dependencies

- `sqlite3` - stdlib, no additional dependency
- Optional: `aiosqlite` for async (future consideration)

---

## Open Questions (Decided)

1. **Database path**: `sessions.db` ✓
2. **WAL mode**: ON by default ✓
3. **Auto-vacuum**: OFF by default (add manual VACUUM command later) ✓
4. **Sub-agent naming**: Auto-generate if missing; user can override ✓
5. **Compaction strategy**: Match existing first; improvements later via flag/config ✓
