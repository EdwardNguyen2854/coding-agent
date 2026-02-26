# Proposal: SQLite Session Storage

## Overview

This proposal outlines migrating session storage from JSON files to SQLite database. This change provides better performance, reliability, and enables future features like querying session history and full-text search.

## Motivation

### Current State (JSON Files)

The current `SessionManager` stores sessions as JSON files in `~/.coding-agent/sessions/`:
- One file per session (`{session_id}.json`)
- Atomic writes using `.tmp` + rename pattern
- Character-based token estimation

### Problems with Current Approach

1. **No transaction safety**: Multiple simultaneous writes can corrupt data
2. **Slow listing**: Must read every JSON file to list sessions
3. **No query capability**: Cannot search/filter sessions
4. **Token estimation**: Rough `len/4` heuristic is inaccurate
5. **File system issues**: Sensitive to file permissions, network drives
6. **No indexing**: Cannot efficiently filter by date, model, or title

### Benefits of SQLite

1. **ACID transactions**: Atomic writes, crash-safe
2. **Fast queries**: Indexed columns for filtering
3. **SQL support**: Rich querying capabilities
4. **Built-in token counting**: Can store actual token counts
5. **Single file**: Easier to backup/migrate
6. **Concurrent access**: Safe for multiple processes
7. **Smaller storage**: Compressed, no JSON overhead

---

## Proposed Architecture

### Database Schema

```sql
-- Sessions table (top-level container)
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    is_compacted BOOLEAN DEFAULT FALSE
);

-- Sub-agents table (future: multiple agents per session)
CREATE TABLE sub_agents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Messages table (normalized, with sub_agent_id for future)
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    sub_agent_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (sub_agent_id) REFERENCES sub_agents(id) ON DELETE SET NULL
);

-- Indexes for common queries
CREATE INDEX idx_sessions_updated ON sessions(updated_at DESC);
CREATE INDEX idx_sessions_title ON sessions(title);
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_sub_agents_session ON sub_agents(session_id);
```

### Compact Support

The existing `/compact` command and auto-compact feature must work with SQLite:

**Current behavior**:
- Auto-compact triggers at `max_context_tokens` (default 128k) in agent loop
- `/compact` command truncates to 64k tokens
- Compaction happens in-memory in `ConversationManager`, not persisted

**SQLite design**:
```sql
-- Sessions table with compaction metadata
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    is_compacted BOOLEAN DEFAULT FALSE,
    original_token_count INTEGER,  -- Tokens before compaction
    max_tokens_before_compact INTEGER DEFAULT 128000  -- Threshold used
);

-- Messages table with soft-delete for compaction
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    sub_agent_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,  -- Soft-delete for compacted messages
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (sub_agent_id) REFERENCES sub_agents(id) ON DELETE SET NULL
);
```

**Implementation**:
```python
class SessionManager:
    def compact(self, session_id: str, max_tokens: int = 64000) -> dict:
        """Compact a session by removing oldest messages.
        
        Strategy (mirrors current in-memory logic):
        1. Prune old tool outputs (truncate to _MAX_TOOL_OUTPUT_CHARS)
        2. Remove oldest user/assistant message pairs
        3. Never remove system prompt
        
        Mark session as compacted, store original token count.
        """
        
    def auto_compact(self, session_id: str, threshold: int | None = None) -> bool:
        """Auto-compact if token_count exceeds threshold.
        
        Called from agent loop. Uses config.max_context_tokens by default.
        Returns True if compaction was performed.
        """
        
    def load(self, session_id: str, include_compacted: bool = False) -> dict | None:
        """Load session. By default, exclude soft-deleted messages.
        
        Set include_compacted=True to get full history (for debugging).
        """
```

### File Location

```
~/.coding-agent/
  config.yaml
  sessions.db        # SQLite database (WAL mode ON)
  sessions/          # OLD: Keep for migration, eventually remove
```

### API Changes

```python
class SessionManager:
    def __init__(self, db_path: Path | None = None):
        # db_path defaults to ~/.coding-agent/sessions.db
    
    def create_session(self, first_message: str, model: str, messages: list[dict]) -> dict:
        # Returns session with messages embedded
    
    def save(self, session: dict[str, Any]) -> None:
        # Saves session + messages atomically
    
    def load(self, session_id: str) -> dict | None:
        # Returns session with messages
    
    def list(self) -> list[dict]:
        # Lists sessions (can add filters)
    
    def delete(self, session_id: str) -> bool:
        # Deletes session and all messages
    
    # New query methods
    def search(self, query: str) -> list[dict]:
        # Full-text search on titles
    
    def list_by_model(self, model: str) -> list[dict]:
        # Filter by model
```

### Backward Compatibility

```python
class SessionManager:
    def __init__(self, sessions_dir: Path | None = None, db_path: Path | None = None):
        # If sessions_dir provided, use legacy JSON mode
        # If db_path provided, use SQLite mode
        # If neither, default to SQLite at ~/.coding-agent/sessions.db
        # If SQLite file doesn't exist but sessions/ does, migrate on first load
```

---

## Implementation Plan

### Phase 1: Core SQLite Support

1. **Database Initialization**
   - Create `src/coding_agent/db.py` with SQLite connection handling
   - Schema migrations table for future upgrades
   - Connection pooling (single connection is fine for this use case)

2. **SessionManager Refactor**
   - Keep existing interface compatible
   - Add `db_path` parameter
   - Implement SQLite-backed methods
   - Add migration from JSON if old data exists

3. **Migration Logic**
   - On first run, detect old `sessions/` directory
   - Import all sessions to SQLite
   - Keep original files as backup
   - Log migration summary

### Phase 2: Enhanced Features

1. **Real Token Tracking**
   - Store actual token counts from LLM responses
   - Update on each message add

2. **Query Methods**
   - `search(query: str)` - full-text search
   - `list_by_model(model: str)` - filter by model
   - `list_by_date_range(start, end)` - time-based filtering

3. **Statistics**
   - Total sessions, messages, tokens
   - Usage by model

4. **Compact Command Support**
   - Implement `compact()` method with token threshold
   - Add `is_compacted` flag to sessions
   - Soft-delete messages during compaction
   - Migrate existing compact logic from `conversation.py`

5. **Auto-Compact**
   - Background compaction when threshold exceeded
   - Configurable threshold (default 100k tokens)

### Phase 3: Cleanup

1. Remove JSON file support after migration period
2. Document migration process for users
3. Add export/import utilities if needed

---

## Migration Path

### For Users

1. First run with new version auto-migrates:
   ```
   Found 15 sessions in JSON format. Migrating to SQLite...
   Migration complete: 15 sessions, 247 messages imported.
   ```

2. Old `sessions/` directory renamed to `sessions.backup/`

### For Developers

```python
# New default (SQLite)
manager = SessionManager()

# Explicit path
manager = SessionManager(db_path=Path("~/.coding-agent/sessions.db"))

# Legacy mode (if needed)
manager = SessionManager(sessions_dir=Path("~/.coding-agent/sessions"))
```

---

## Multi-Sub-Agent Support (Future)

The schema includes a `sub_agents` table to support multiple agents per session:

```python
# Future API for multi-agent sessions
class SessionManager:
    def add_sub_agent(self, session_id: str, name: str, role: str) -> dict:
        """Add a sub-agent to a session."""
    
    def get_sub_agents(self, session_id: str) -> list[dict]:
        """Get all sub-agents for a session."""
    
    def get_messages(self, session_id: str, sub_agent_id: str | None = None) -> list[dict]:
        """Get messages, optionally filtered by sub-agent."""
```

**Design notes**:
- Each sub-agent has its own message thread within the session
- Sub-agents can share context but maintain separate conversation history
- Queries can filter messages by `sub_agent_id`
- **Naming**: Auto-generate if missing; user can override

---

## Comparison

| Aspect | JSON Files | SQLite |
|--------|-----------|--------|
| Storage | One file per session | Single file |
| Read sessions | O(n) files | O(1) query |
| Write safety | Atomic rename | ACID transactions |
| Search | No | Full-text |
| Concurrent | Risky | Safe |
| Token count | Estimated | Stored |
| Backup | Multiple files | Single file |
| Size (15 sessions) | ~50KB | ~30KB |
| Multi-agent | No | Yes (schema ready) |
| Compaction | File-based | In-place with flags |

---

## Open Questions

1. ~~**Migration timing**: When to remove JSON fallback? (v1.0?)~~ - TBD during cleanup phase
2. ~~**Database path**: Keep `sessions.db` or use `coding-agent.db`?~~ - **sessions.db**
3. ~~**WAL mode**: Enable WAL for better concurrent read performance?~~ - **ON by default**
4. ~~**Compression**: Use `PRAGMA compression` for older sessions?~~ - OFF by default, add manual VACUUM later
5. ~~**Export**: Need JSON export for backup/compatibility?~~ - Add in Phase 5

---

## Next Steps

1. Review this proposal
2. Approve schema design
3. Implement `db.py` with migrations
4. Refactor `SessionManager` to use SQLite
5. Add migration from JSON
6. Test with existing sessions
