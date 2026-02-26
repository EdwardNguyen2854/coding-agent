"""Todo list management for tracking implementation tasks."""

import json
import re
import tempfile
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from coding_agent.config.config import DEFAULT_DOCS_DIR


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class TodoItem:
    """Represents a single todo item."""

    def __init__(
        self,
        id: str,
        description: str,
        status: TaskStatus = TaskStatus.PENDING,
        created_at: str | None = None,
        completed_at: str | None = None,
    ):
        self.id = id
        self.description = description
        self.status = status
        self.created_at = created_at or datetime.now().isoformat()
        self.completed_at = completed_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TodoItem":
        return cls(
            id=data["id"],
            description=data["description"],
            status=TaskStatus(data.get("status", "pending")),
            created_at=data.get("created_at"),
            completed_at=data.get("completed_at"),
        )


class TodoList:
    """Manages a list of todo items."""

    def __init__(self, items: list[TodoItem] | None = None):
        self._items: list[TodoItem] = items or []

    def add(self, description: str) -> TodoItem:
        """Add a new todo item."""
        item = TodoItem(
            id=f"task-{len(self._items) + 1}",
            description=description,
        )
        self._items.append(item)
        return item

    def add_items(self, descriptions: list[str]) -> list[TodoItem]:
        """Add multiple todo items."""
        items = []
        for desc in descriptions:
            items.append(self.add(desc))
        return items

    def complete(self, task_id: str) -> bool:
        """Mark a task as completed."""
        for item in self._items:
            if item.id == task_id:
                item.status = TaskStatus.COMPLETED
                item.completed_at = datetime.now().isoformat()
                return True
        return False

    def start(self, task_id: str) -> bool:
        """Mark a task as in progress."""
        for item in self._items:
            if item.id == task_id:
                item.status = TaskStatus.IN_PROGRESS
                return True
        return False

    def get_pending(self) -> list[TodoItem]:
        """Get all pending/in-progress tasks."""
        return [i for i in self._items if i.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)]

    def get_completed(self) -> list[TodoItem]:
        """Get all completed tasks."""
        return [i for i in self._items if i.status == TaskStatus.COMPLETED]

    def get_next(self) -> TodoItem | None:
        """Get the next pending task."""
        pending = self.get_pending()
        return pending[0] if pending else None

    def remove(self, task_id: str) -> bool:
        """Remove a task by ID."""
        for i, item in enumerate(self._items):
            if item.id == task_id:
                self._items.pop(i)
                return True
        return False

    def clear_completed(self) -> None:
        """Remove all completed tasks."""
        self._items = [i for i in self._items if i.status != TaskStatus.COMPLETED]

    @property
    def items(self) -> list[TodoItem]:
        return self._items

    @property
    def total(self) -> int:
        return len(self._items)

    @property
    def completed_count(self) -> int:
        return len(self.get_completed())

    def to_dict(self) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in self._items]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TodoList":
        items = [TodoItem.from_dict(d) for d in data.get("items", [])]
        return cls(items)

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

    def __repr__(self) -> str:
        return f"TodoList({self.completed_count}/{self.total} completed)"


class TodoMarkdownStore:
    """Persists todo list to markdown file."""

    def __init__(self, base_path: Path | None = None):
        self._base_path = base_path or Path(tempfile.gettempdir()) / ".coding-agent"

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
