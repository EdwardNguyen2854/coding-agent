# Todo System Improvements - Implementation Plan

**Date**: 2026-02-26
**Based on**: TODO-IMPROVEMENTS.md

## Overview

This document outlines the phased implementation plan to improve the todo system in coding-agent. The improvements focus on:
1. Converting todo storage from JSON to markdown format
2. Adding conversation notifications when tasks complete
3. Updating the `/todo` command display

---

## Phase 1: Markdown Storage Implementation

### Goal
Replace JSON-based todo storage with human-readable markdown format.

### Tasks

#### 1.1 Add `to_markdown()` method to `TodoList`
- **File**: `src/coding_agent/todo.py`
- **Description**: Add method to serialize `TodoList` to markdown format
- **Format**:
  ```markdown
  # Todos

  [x] 1. Second task
  [>] 2. Third task (in progress)
  [ ] 3. Fourth task
  ```
- **Status**: Pending

#### 1.2 Add `from_markdown()` class method to `TodoList`
- **File**: `src/coding_agent/todo.py`
- **Description**: Add class method to parse markdown content back to `TodoList`
- **Regex pattern**: `(\[x\]|\[>\]|\[ \])\s*(\d+\.)\s*(.+)`
- **Status**: Pending

#### 1.3 Create `TodoMarkdownStore` class
- **File**: `src/coding_agent/todo.py`
- **Description**: New class to handle markdown file persistence
- **Location**: `{TEMP_DIR}/todo.md`
- **Methods**:
  - `save(todos, name)` - Save todo list to markdown file
  - `load(name)` - Load todo list from markdown file
- **Status**: Pending

#### 1.4 Update storage path constants
- **File**: `src/coding_agent/todo.py`
- **Description**: Change default storage path from `{DEFAULT_DOCS_DIR}/todo-list.json` to `{TEMP_DIR}/todo.md`
- **Status**: Pending

### Dependencies
- None (this phase is self-contained)

### Estimated Effort
1-2 hours

---

## Phase 2: Task Completion Notifications

### Goal
Show notifications in the conversation when a task is marked complete.

### Tasks

#### 2.1 Add callback mechanism to `Workflow`
- **File**: `src/coding_agent/workflow.py` (or `workflow_impl.py`)
- **Description**: Add `set_task_complete_callback()` method
- **Callback signature**: `Callable[[TodoItem], None]`
- **Status**: Pending

#### 2.2 Update `complete_task()` to trigger callback
- **File**: `src/coding_agent/workflow.py`
- **Description**: Call the registered callback when a task is completed
- **Status**: Pending

#### 2.3 Register callback in agent loop
- **File**: `src/coding_agent/cli.py`
- **Description**: Register callback during workflow initialization
- **Status**: Pending

#### 2.4 Display notification message
- **File**: `src/coding_agent/cli.py`
- **Description**: Show message in conversation when task completes
- **Format**:
  ```
  ✓ Task completed: <description>
  Progress: 3/5
  ```
- **Status**: Pending

### Dependencies
- Phase 1 (requires `TodoList.to_markdown()` for progress tracking)

### Estimated Effort
2-3 hours

---

## Phase 3: Updated `/todo` Command

### Goal
Update the `/todo` slash command to display markdown format instead of Rich table.

### Tasks

#### 3.1 Update `cmd_todo` in slash_commands.py
- **File**: `src/coding_agent/slash_commands.py`
- **Description**: Render markdown format instead of Rich table
- **Status**: Pending

#### 3.2 Preserve progress counter in sidebar
- **File**: `src/coding_agent/sidebar.py`
- **Description**: Ensure sidebar still shows `2/5` progress
- **Status**: Pending

### Dependencies
- Phase 1 (requires markdown storage to be functional)

### Estimated Effort
1 hour

---

## Phase 4: Integration & Testing

### Tasks

#### 4.1 Integration testing
- **Description**: Test full flow from task completion to notification
- **Status**: Pending

#### 4.2 Backward compatibility
- **Description**: Optionally keep `TodoStore` for legacy support or deprecate gracefully
- **Status**: Pending

#### 4.3 Update documentation
- **Files**: 
  - `docs/agent/TOOLS.md` - If tool documentation needs updates
  - `docs/user/CLI-REFERENCE.md` - If `/todo` command behavior changes
- **Status**: Pending

---

## Implementation Order

```
Phase 1 (Foundation)
├── 1.1 to_markdown() method
├── 1.2 from_markdown() method
├── 1.3 TodoMarkdownStore class
└── 1.4 Update storage paths

Phase 2 (Notifications)
├── 2.1 Add callback to Workflow
├── 2.2 Update complete_task()
├── 2.3 Register callback in CLI
└── 2.4 Display notifications

Phase 3 (/todo command)
├── 3.1 Update cmd_todo display
└── 3.2 Preserve sidebar counter

Phase 4 (Integration)
├── 4.1 Integration testing
├── 4.2 Backward compatibility
└── 4.3 Update docs
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/coding_agent/todo.py` | Add markdown serialization + new store class |
| `src/coding_agent/workflow.py` | Add callback mechanism |
| `src/coding_agent/slash_commands.py` | Update `/todo` display |
| `src/coding_agent/cli.py` | Integrate task completion notifications |

---

## Success Criteria

- [ ] Todo list saved/loaded in markdown format
- [ ] Conversation shows notification when task completes
- [ ] `/todo` command displays markdown format
- [ ] Sidebar shows progress counter
- [ ] No regression in existing functionality
