"""Tests for todo enhancements: block(), get_blocked(), markdown round-trip, and toolbar."""

from unittest.mock import MagicMock

import pytest

from coding_agent.state.todo import TaskStatus, TodoItem, TodoList
from coding_agent.state.workflow_impl import Workflow, WorkflowState
from coding_agent.ui.sidebar import make_toolbar


# ---------------------------------------------------------------------------
# TodoList: block() and get_blocked()
# ---------------------------------------------------------------------------

class TestTodoBlock:
    def setup_method(self):
        self.todos = TodoList()
        self.todos.add("Task A")
        self.todos.add("Task B")
        self.todos.add("Task C")

    def test_block_sets_status(self):
        assert self.todos.block("task-2")
        assert self.todos.items[1].status == TaskStatus.BLOCKED

    def test_block_returns_false_for_unknown_id(self):
        assert not self.todos.block("task-99")

    def test_get_blocked_returns_only_blocked(self):
        self.todos.block("task-1")
        blocked = self.todos.get_blocked()
        assert len(blocked) == 1
        assert blocked[0].id == "task-1"

    def test_get_blocked_empty_when_none(self):
        assert self.todos.get_blocked() == []

    def test_blocked_not_in_pending(self):
        self.todos.block("task-1")
        pending_ids = {i.id for i in self.todos.get_pending()}
        assert "task-1" not in pending_ids


# ---------------------------------------------------------------------------
# TodoList: to_markdown / from_markdown round-trip for BLOCKED
# ---------------------------------------------------------------------------

class TestTodoMarkdownBlocked:
    def test_blocked_serializes_as_bang(self):
        todos = TodoList()
        todos.add("First")
        todos.block("task-1")
        md = todos.to_markdown()
        assert "[!]" in md

    def test_blocked_round_trips(self):
        todos = TodoList()
        todos.add("Alpha")
        todos.add("Beta")
        todos.add("Gamma")
        todos.block("task-2")
        todos.complete("task-3")

        restored = TodoList.from_markdown(todos.to_markdown())
        statuses = {item.description: item.status for item in restored.items}
        assert statuses["Alpha"] == TaskStatus.PENDING
        assert statuses["Beta"] == TaskStatus.BLOCKED
        assert statuses["Gamma"] == TaskStatus.COMPLETED

    def test_all_statuses_in_markdown(self):
        todos = TodoList()
        todos.add("pending")
        todos.add("in_progress")
        todos.start("task-2")
        todos.add("blocked")
        todos.block("task-3")
        todos.add("done")
        todos.complete("task-4")

        md = todos.to_markdown()
        assert "[ ]" in md
        assert "[>]" in md
        assert "[!]" in md
        assert "[x]" in md


# ---------------------------------------------------------------------------
# Workflow: block_task(), to_dict(), restore_from_dict()
# ---------------------------------------------------------------------------

class TestWorkflowPersistence:
    def test_block_task_delegates_to_todo_list(self):
        wf = Workflow()
        wf.todo_list.add("Do something")
        assert wf.block_task("task-1")
        assert wf.todo_list.items[0].status == TaskStatus.BLOCKED

    def test_to_dict_includes_state_and_todos(self):
        wf = Workflow()
        wf.state = WorkflowState.EXECUTING
        wf.todo_list.add("Step 1")
        wf.todo_list.start("task-1")

        d = wf.to_dict()
        assert d["state"] == "executing"
        assert len(d["todo_list"]["items"]) == 1
        assert d["todo_list"]["items"][0]["status"] == "in_progress"

    def test_restore_from_dict_reconstructs_state(self):
        wf_original = Workflow()
        wf_original.state = WorkflowState.EXECUTING
        wf_original.todo_list.add("Task X")
        wf_original.todo_list.add("Task Y")
        wf_original.todo_list.complete("task-1")
        wf_original.todo_list.block("task-2")

        data = wf_original.to_dict()

        wf_restored = Workflow()
        Workflow.restore_from_dict(wf_restored, data)

        assert wf_restored.state == WorkflowState.EXECUTING
        assert wf_restored.todo_list.total == 2
        assert wf_restored.todo_list.completed_count == 1
        assert wf_restored.todo_list.get_blocked()[0].description == "Task Y"

    def test_restore_from_empty_dict_stays_idle(self):
        wf = Workflow()
        Workflow.restore_from_dict(wf, {})
        assert wf.state == WorkflowState.IDLE
        assert wf.todo_list.total == 0


# ---------------------------------------------------------------------------
# Toolbar: blocked count display
# ---------------------------------------------------------------------------

def _text(parts):
    return "".join(t for _, t in parts)


class TestToolbarBlockedDisplay:
    @pytest.fixture
    def mock_conversation(self):
        conv = MagicMock()
        conv.token_count = 1000
        return conv

    def test_blocked_count_shown_in_toolbar(self, mock_conversation):
        wf = MagicMock()
        wf.state = WorkflowState.IDLE
        wf.todo_list.total = 3
        wf.todo_list.completed_count = 1
        wf.todo_list.get_blocked.return_value = [MagicMock(), MagicMock()]
        wf.todo_list.items = []  # no in-progress task

        toolbar = make_toolbar(mock_conversation, wf, branch="main")
        text = _text(toolbar())

        assert "✗2" in text

    def test_no_blocked_indicator_when_zero(self, mock_conversation):
        wf = MagicMock()
        wf.state = WorkflowState.IDLE
        wf.todo_list.total = 2
        wf.todo_list.completed_count = 0
        wf.todo_list.get_blocked.return_value = []
        wf.todo_list.items = []

        toolbar = make_toolbar(mock_conversation, wf, branch="main")
        text = _text(toolbar())

        assert "✗" not in text
