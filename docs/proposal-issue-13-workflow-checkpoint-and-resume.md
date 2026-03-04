# Workflow Checkpoint and Resume - Proposal

## Overview

Implement a checkpoint and resume system that allows users to save the state of their coding session at any point and resume it later, enabling recovery from interruptions, sharing session state with team members, and working on complex multi-step tasks incrementally.

## Motivation

Users face challenges with:

- **Interrupted workflows** - Long-running tasks or meetings cause loss of progress
- **No recovery mechanism** - Crashes or closures result in lost work
- **Session sharing** - Cannot share current work state with teammates
- **Checkpointing** - No way to mark and return to specific points in a workflow
- **Large context loss** - LLM context window limits cause loss of conversation history

## Proposed Solution

### 1. Checkpoint System

**Checkpoint Data Structure**
```python
class Checkpoint:
    id: str                          # Unique checkpoint ID
    name: str                        # User-provided name
    timestamp: datetime              # When checkpoint was created
    session_state: SessionState      # Current session state
    message_history: List[Message]   # Conversation history
    workspace_state: WorkspaceState  # File changes, git status
    tool_invocations: List[ToolCall] # Tool execution history
    metadata: Dict[str, Any]         # Additional metadata
```

**Session State Contents**
```python
class SessionState:
    project_path: str                # Current working directory
    git_branch: str                  # Current branch
    modified_files: List[str]        # Changed files (staged/unstaged)
    uncommitted_changes: Dict[str, str]  # File content diffs
    agent_context: Dict[str, Any]    # Agent memory/state
    user_preferences: Dict[str, Any] # Session preferences
```

### 2. Checkpoint Operations

**Create Checkpoint**
```
/checkpoint save [name]              # Save with optional name
/checkpoint save "Before refactor"  # Save with descriptive name
```

**List Checkpoints**
```
/checkpoint list                     # Show all checkpoints
/checkpoint list --short            # Compact view
```

**Restore Checkpoint**
```
/checkpoint restore <id>            # Restore by ID
/checkpoint restore latest          # Restore most recent
/checkpoint restore --merge         # Merge with current state
```

**Delete Checkpoint**
```
/checkpoint delete <id>             # Delete specific checkpoint
/checkpoint delete old              # Delete all but latest
```

### 3. Automatic Checkpoints

| Event | Auto-save | Config |
|-------|-----------|--------|
| Tool execution | Every N tools | `checkpoint.autoSave.interval` |
| Time-based | Every N minutes | `checkpoint.autoSave.intervalMinutes` |
| Before risky operations | Always | Built-in |
| Session close | Always | Built-in |

**Configuration Options**
```yaml
checkpoint:
  autoSave:
    enabled: true
    interval: 10        # Every 10 tool invocations
    intervalMinutes: 5  # Every 5 minutes
  storage:
    location: "~/.coding-agent/checkpoints"
    maxCount: 50        # Maximum checkpoints to keep
    maxAge: 7d          # Maximum age before cleanup
  compression: true     # Compress checkpoint data
```

### 4. Resume Behavior

**Full Resume**
- Restore complete session state
- Replay message history to rebuild context
- Restore file changes
- Resume from exact point

**Partial Resume**
- Restore only selected components
- Choose which files to restore
- Merge with current workspace state

**Resume Confirmation**
```
┌─────────────────────────────────────────────────────────┐
│ Resume Checkpoint #23 "Before refactor"?                │
├─────────────────────────────────────────────────────────┤
│ Created: 2024-01-15 14:32:00                            │
│ Files: 3 modified                                       │
│ Messages: 12 in history                                 │
├─────────────────────────────────────────────────────────┤
│ [R] Resume (replace current)                            │
│ [M] Resume (merge with current)                         │
│ [P] Preview changes only                               │
│ [C] Cancel                                              │
└─────────────────────────────────────────────────────────┘
```

### 5. Checkpoint Storage

**Local Storage**
```
~/.coding-agent/checkpoints/
├── checkpoint_001.json
├── checkpoint_002.json
└── metadata.json
```

**Remote Storage (Future)**
- Share checkpoints with team
- Store in cloud storage
- Version control checkpoints

### 6. Integration Points

**With Session Management**
- Checkpoints tied to session ID
- Associate with project/workspace
- Cross-session restoration

**With Git**
- Store git state (branch, stash)
- Detect conflicting changes
- Offer merge strategies

**With Multi-Agent**
- Share checkpoints between agents
- Agent-specific checkpointing
- Coordinator checkpoints

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `checkpoint.enabled` | `true` | Enable checkpoint system |
| `checkpoint.autoSave.enabled` | `true` | Auto-save checkpoints |
| `checkpoint.autoSave.interval` | `10` | Tools between auto-saves |
| `checkpoint.autoSave.intervalMinutes` | `5` | Minutes between auto-saves |
| `checkpoint.storage.location` | `~/.coding-agent/checkpoints` | Storage directory |
| `checkpoint.storage.maxCount` | `50` | Maximum checkpoints |
| `checkpoint.storage.maxAge` | `7d` | Maximum age |
| `checkpoint.compression` | `true` | Compress checkpoint data |

## Implementation

### Core API

```python
class CheckpointManager:
    def __init__(self, config: CheckpointConfig, storage: CheckpointStorage):
        self.config = config
        self.storage = storage
    
    def create(self, name: Optional[str] = None) -> Checkpoint:
        """Create a new checkpoint from current state."""
    
    def restore(self, checkpoint_id: str, mode: RestoreMode = RestoreMode.FULL) -> SessionState:
        """Restore session from checkpoint."""
    
    def list(self) -> List[CheckpointSummary]:
        """List all checkpoints."""
    
    def delete(self, checkpoint_id: str) -> None:
        """Delete a checkpoint."""
    
    def auto_save(self) -> None:
        """Trigger auto-save if conditions met."""


class CheckpointStorage:
    def save(self, checkpoint: Checkpoint) -> None:
        """Persist checkpoint to storage."""
    
    def load(self, checkpoint_id: str) -> Checkpoint:
        """Load checkpoint from storage."""
    
    def list(self) -> List[CheckpointSummary]:
        """List all stored checkpoints."""
    
    def delete(self, checkpoint_id: str) -> None:
        """Delete checkpoint from storage."""
```

### Events System

```python
class CheckpointEventHandler:
    def on_tool_executed(self, tool: ToolCall) -> None:
        """Check if auto-save needed after tool execution."""
    
    def on_timer_tick(self) -> None:
        """Check if time-based auto-save needed."""
    
    def on_session_close(self) -> None:
        """Save checkpoint before session closes."""
    
    def on_risky_operation(self, operation: str) -> None:
        """Save checkpoint before risky operations."""
```

### UI Commands

```
/checkpoint              # Show checkpoint help
/checkpoint save        # Save current state
/checkpoint save "name" # Save with name
/checkpoint list        # List all checkpoints
/checkpoint restore #id # Restore checkpoint
/checkpoint delete #id  # Delete checkpoint
/checkpoint diff #id    # Show changes since checkpoint
```

## Alternatives Considered

1. **Git-based versioning** - Use git commits for state, but adds git dependency
2. **Full session recording** - Record all actions for replay, complex to implement
3. **Cloud-based state** - Requires network and authentication
4. **Manual save/load** - User-managed state files, error-prone

## Compatibility

- Backward compatible: can disable checkpoints
- Non-destructive: original files preserved
- Git-friendly: works with existing git workflows
- Cross-platform: storage format is portable
