# Implementation Plan - Workflow Checkpoint and Resume

## Phase 1: Core Data Structures

### 1.1 Checkpoint Models
- [ ] Create `src/coding_agent/checkpoint/models.py` - Define `Checkpoint`, `SessionState`, `CheckpointSummary` dataclasses
- [ ] Create `src/coding_agent/checkpoint/types.py` - Define `RestoreMode` enum and related types

### 1.2 Configuration
- [ ] Add checkpoint config to `src/coding_agent/config/config.py` - Add `CheckpointConfig` with enabled, autoSave, storage, compression options
- [ ] Add CLI flags: `--checkpoint/--no-checkpoint`, `--checkpoint-auto-save`, `--checkpoint-dir`

## Phase 2: Storage Layer

### 2.1 Storage Interface
- [ ] Create `src/coding_agent/checkpoint/storage.py` - Define `CheckpointStorage` abstract base class

### 2.2 Local Storage Implementation
- [ ] Implement `LocalCheckpointStorage` - File-based checkpoint storage
- [ ] Implement JSON serialization/deserialization
- [ ] Implement compression using gzip
- [ ] Add metadata management (index of all checkpoints)

### 2.3 Storage Operations
- [ ] Implement `save()`, `load()`, `list()`, `delete()` methods
- [ ] Add cleanup for old checkpoints based on maxCount/maxAge

## Phase 3: Checkpoint Manager

### 3.1 Manager Core
- [ ] Create `src/coding_agent/checkpoint/manager.py` - Implement `CheckpointManager` class
- [ ] Implement `create()` - Capture current session state
- [ ] Implement `restore()` - Restore session from checkpoint
- [ ] Implement `list()` - List all checkpoints
- [ ] Implement `delete()` - Delete a checkpoint

### 3.2 State Capture
- [ ] Capture message history from session
- [ ] Capture workspace state (modified files, git status)
- [ ] Capture tool invocation history
- [ ] Capture agent context/memory

### 3.3 State Restoration
- [ ] Implement full restore mode
- [ ] Implement merge restore mode
- [ ] Implement preview mode (show changes without applying)

## Phase 4: Auto-Save System

### 4.1 Event Handlers
- [ ] Create `src/coding_agent/checkpoint/events.py` - Event handlers for auto-save
- [ ] Implement tool execution counter
- [ ] Implement timer-based auto-save
- [ ] Implement session close handler

### 4.2 Risky Operation Detection
- [ ] Add checkpoint before destructive operations (file delete, force push, etc.)
- [ ] Add confirmation dialog for risky operations

## Phase 5: CLI Integration

### 5.1 Slash Commands
- [ ] Add `/checkpoint` command to `src/coding_agent/ui/slash_commands.py`
- [ ] Implement `/checkpoint save [name]`
- [ ] Implement `/checkpoint list`
- [ ] Implement `/checkpoint restore <id>`
- [ ] Implement `/checkpoint delete <id>`
- [ ] Implement `/checkpoint diff <id>`

### 5.2 UI Components
- [ ] Create checkpoint list UI (table format)
- [ ] Create restore confirmation dialog
- [ ] Add status indicator when auto-save occurs

### 5.3 Keyboard Shortcuts
- [ ] Add keyboard shortcut for quick checkpoint (e.g., Ctrl+S)

## Phase 6: Git Integration

### 6.1 Git State
- [ ] Capture current branch, HEAD, stash
- [ ] Detect uncommitted changes
- [ ] Store file content diffs

### 6.2 Conflict Detection
- [ ] Detect conflicts when restoring checkpoint
- [ ] Offer merge strategies (restore, keep current, manual merge)

## Phase 7: Testing & Polish

### 7.1 Unit Tests
- [ ] Test checkpoint serialization
- [ ] Test storage operations
- [ ] Test state capture/restoration
- [ ] Test auto-save triggers

### 7.2 Integration Tests
- [ ] Test full checkpoint/restore cycle
- [ ] Test merge mode
- [ ] Test with git repository

### 7.3 Edge Cases
- [ ] Handle corrupted checkpoint files
- [ ] Handle missing workspace files
- [ ] Handle checkpoint from different project
- [ ] Handle concurrent checkpoint operations

## File Structure

```
src/coding_agent/checkpoint/
├── __init__.py           # Public API exports
├── models.py             # Data models (Checkpoint, SessionState)
├── types.py              # Type definitions (RestoreMode)
├── config.py             # Configuration (derived from main config)
├── storage.py            # Storage interface and implementations
├── manager.py            # CheckpointManager implementation
├── events.py             # Auto-save event handlers
└── commands.py           # CLI command handlers

src/coding_agent/ui/slash_commands.py  # Add /checkpoint commands
```

## Usage

```python
from coding_agent.checkpoint import CheckpointManager

# Create checkpoint
checkpoint = manager.create(name="Before refactor")

# List checkpoints
checkpoints = manager.list()

# Restore checkpoint
manager.restore(checkpoint_id, mode=RestoreMode.FULL)

# Delete checkpoint
manager.delete(checkpoint_id)
```

CLI commands:
- `/checkpoint save [name]` - Save checkpoint
- `/checkpoint list` - List all checkpoints
- `/checkpoint restore <id>` - Restore checkpoint
- `/checkpoint delete <id>` - Delete checkpoint
- `/checkpoint diff <id>` - Show changes since checkpoint

Configuration:
```yaml
checkpoint:
  enabled: true
  autoSave:
    enabled: true
    interval: 10
    intervalMinutes: 5
  storage:
    location: "~/.coding-agent/checkpoints"
    maxCount: 50
    maxAge: 7d
  compression: true
```
