# Todo Display Improvements Proposal

**Date**: 2026-02-26
**Status**: Proposed

## Summary

This proposal outlines improvements to the todo system in coding-agent to:
1. Show todo status in conversation when a task completes
2. Use markdown file format for todo storage instead of JSON

## Current Implementation

### Storage
- JSON file at `{DEFAULT_DOCS_DIR}/todo-list.json`
- Managed by `TodoStore` class in `todo.py`

### Display
- `/todo` command shows Rich table with status indicators:
  - `[x] Done` - completed
  - `[>] In Progress` - in progress
  - `[ ] Pending` - pending
- Sidebar shows progress counter like `2/5`

### Problem
- No automatic notification when tasks complete
- Uses JSON format (not human-readable)
- `Workflow.complete_task()` exists but is never called in the agent loop

## Proposed Changes

### 1. Markdown Todo Storage

Replace JSON with markdown format stored in `{TEMP_DIR}/todo.md`:

```markdown
# Todos

[x] 1. Second task
[>] 2. Third task (in progress)
[ ] 3. Fourth task
```

#### Implementation

Add to `todo.py`:

```python
class TodoMarkdownStore:
    """Persists todo list to markdown file."""

    def __init__(self, base_path: Path | None = None):
        self._base_path = base_path or DEFAULT_DOCS_DIR

    def save(self, todos: TodoList, name: str = "todo") -> Path:
        """Save todo list to markdown file."""
        self._base_path.mkdir(parents=True, exist_ok=True)
        file_path = self._base_path / f"{name}.md"
        file_path.write_text(todos.to_markdown(), encoding="utf-8")
        return file_path

    def load(self, name: str = "todo") -> TodoList | None:
        """Load todo list from markdown file."""
        file_path = self._base_path / f"{name}.md"
        if not file_path.exists():
            return None
        try:
            content = file_path.read_text(encoding="utf-8")
            return TodoList.from_markdown(content)
        except Exception:
            return None
```

Add to `TodoList`:

```python
def to_markdown(self) -> str:
    """Convert todo list to markdown format."""
    lines = ["# Todos", ""]
    for i, item in enumerate(self._items, 1):
        if item.status == TaskStatus.COMPLETED:
            status = "[x]"
        elif item.status == TaskStatus.IN_PROGRESS:
            status = "[>]"
        else:
            status = "[ ]"
        lines.append(f"{status} {i}. {item.description}")
    return "\n".join(lines)

@classmethod
def from_markdown(cls, content: str) -> "TodoList":
    """Parse todo list from markdown content."""
    items = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"(\[x\]|\[>\]|\[ \])\s*(\d+\.)\s*(.+)", line)
        if match:
            status_str, _, desc = match.groups()
            if status_str == "[x]":
                status = TaskStatus.COMPLETED
            elif status_str == "[>]":
                status = TaskStatus.IN_PROGRESS
            else:
                status = TaskStatus.PENDING
            items.append(TodoItem(id=f"task-{len(items)+1}", description=desc, status=status))
    return cls(items)
```

### 2. Conversation Notification on Task Completion

When a task is marked complete, show a message in the conversation:

```
✓ Task completed: <description>
Progress: 3/5
```

#### Implementation

Add callback mechanism to `Workflow`:

```python
class Workflow:
    def __init__(self, ...):
        ...
        self._on_task_complete: Callable[[TodoItem], None] | None = None

    def set_task_complete_callback(self, callback: Callable[[TodoItem], None]) -> None:
        """Set callback to be called when a task completes."""
        self._on_task_complete = callback

    def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed."""
        result = self.todo_list.complete(task_id)
        if result and self._on_task_complete:
            completed_item = next(i for i in self.todo_list.items if i.id == task_id)
            self._on_task_complete(completed_item)
        return result
```

Integrate with agent loop in `cli.py` to register callback and display notification.

### 3. Updated `/todo` Command

Update `cmd_todo` in `slash_commands.py` to render markdown format instead of Rich table.

## Migration Path

1. Add `to_markdown()`, `from_markdown()` methods to `TodoList`
2. Add `TodoMarkdownStore` class
3. Add callback mechanism to `Workflow`
4. Update agent loop to handle task completion notifications
5. Update `/todo` command display format
6. Optionally keep `TodoStore` for backward compatibility or deprecate

## Files to Modify

- `src/coding_agent/todo.py` - Add markdown serialization
- `src/coding_agent/workflow_impl.py` - Add callback mechanism
- `src/coding_agent/slash_commands.py` - Update `/todo` display
- `src/coding_agent/cli.py` - Integrate task completion notifications
