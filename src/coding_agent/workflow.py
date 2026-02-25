"""Workflow system for managing implementation plans and todo execution."""

import os
from enum import Enum
from pathlib import Path
from typing import Any

from coding_agent.config import DEFAULT_DOCS_DIR
from coding_agent.todo import TodoItem, TodoList


class WorkflowState(str, Enum):
    IDLE = "idle"
    AWAITING_PLAN = "awaiting_plan"
    PLAN_CREATED = "plan_created"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"


class WorkflowType(str, Enum):
    DEFAULT = "default"
    AGILE = "agile"


class Plan:
    """Represents an implementation plan."""

    def __init__(
        self,
        title: str,
        description: str,
        tasks: list[str],
        file_path: Path | None = None,
    ):
        self.title = title
        self.description = description
        self.tasks = tasks
        self.file_path = file_path

    def to_markdown(self) -> str:
        """Convert plan to markdown format."""
        md = f"# {self.title}\n\n"
        md += f"{self.description}\n\n"
        md += "## Tasks\n\n"
        for i, task in enumerate(self.tasks, 1):
            md += f"{i}. {task}\n"
        return md

    @classmethod
    def from_markdown(cls, content: str, file_path: Path | None = None) -> "Plan":
        """Parse plan from markdown content."""
        lines = content.strip().split("\n")
        title = "Implementation Plan"
        description = ""
        tasks = []
        in_tasks = False

        for line in lines:
            line = line.strip()
            if line.startswith("# ") and not title:
                title = line[2:]
            elif line.startswith("## "):
                if "task" in line.lower():
                    in_tasks = True
                else:
                    description += line[3:] + "\n"
            elif in_tasks and line and (line[0].isdigit() or line.startswith("-") or line.startswith("*")):
                task = line.lstrip("0123456789.-* ").strip()
                if task:
                    tasks.append(task)
            elif not in_tasks and line:
                description += line + "\n"

        return cls(title, description.strip(), tasks, file_path)


class Workflow:
    """Manages the default workflow: create plan -> approve -> execute todos."""

    def __init__(
        self,
        workflow_type: WorkflowType = WorkflowType.DEFAULT,
        context_limit: int = 128000,
    ):
        self.type = workflow_type
        self.state = WorkflowState.IDLE
        self.current_plan: Plan | None = None
        self.todo_list = TodoList()
        self.context_limit = context_limit
        self._docs_path = DEFAULT_DOCS_DIR
        self._docs_path.mkdir(parents=True, exist_ok=True)

    def get_context_usage(self, token_count: int) -> tuple[int, float]:
        """Get context usage percentage."""
        percentage = (token_count / self.context_limit) * 100
        return token_count, percentage

    def create_plan(self, content: str) -> Plan:
        """Create a plan from LLM output and save to docs folder."""
        self.current_plan = Plan.from_markdown(content)
        file_path = self._docs_path / "implementation-plan.md"
        file_path.write_text(self.current_plan.to_markdown(), encoding="utf-8")
        self.current_plan.file_path = file_path
        self.state = WorkflowState.PLAN_CREATED
        return self.current_plan

    def approve_plan(self) -> None:
        """Approve the current plan and convert to todo list."""
        if self.current_plan:
            self.todo_list = TodoList()
            self.todo_list.add_items(self.current_plan.tasks)
            self.state = WorkflowState.AWAITING_APPROVAL

    def reject_plan(self) -> None:
        """Reject the current plan and reset."""
        self.current_plan = None
        self.state = WorkflowState.IDLE

    def get_next_task(self) -> TodoItem | None:
        """Get the next task to execute."""
        return self.todo_list.get_next()

    def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed."""
        return self.todo_list.complete(task_id)

    def start_task(self, task_id: str) -> bool:
        """Mark a task as in progress."""
        return self.todo_list.start(task_id)

    def save_todos(self) -> Path:
        """Save the todo list to disk."""
        from coding_agent.todo import TodoStore
        store = TodoStore(self._docs_path)
        return store.save(self.todo_list)

    def load_todos(self) -> TodoList | None:
        """Load the todo list from disk."""
        from coding_agent.todo import TodoStore
        store = TodoStore(self._docs_path)
        return store.load()


class WorkflowManager:
    """Manages multiple workflow types."""

    def __init__(self, context_limit: int = 128000):
        self._workflows: dict[WorkflowType, Workflow] = {}
        self._current_type = WorkflowType.DEFAULT
        self.context_limit = context_limit

    def get_current(self) -> Workflow:
        """Get the current workflow."""
        if self._current_type not in self._workflows:
            self._workflows[self._current_type] = Workflow(
                workflow_type=self._current_type,
                context_limit=self.context_limit,
            )
        return self._workflows[self._current_type]

    def set_workflow(self, workflow_type: WorkflowType) -> None:
        """Switch to a different workflow type."""
        self._current_type = workflow_type

    def get_available_workflows(self) -> list[WorkflowType]:
        """Get list of available workflow types."""
        return list(WorkflowType)
