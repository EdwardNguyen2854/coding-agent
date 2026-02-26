"""State subpackage - persistence and workflow state."""

from coding_agent.state.db import Database
from coding_agent.state.schema import (
    CREATE_MESSAGES_TABLE,
    CREATE_SCHEMA_MIGRATIONS,
    CREATE_SESSIONS_TABLE,
)
from coding_agent.state.session import (
    DEFAULT_DB_PATH,
    DEFAULT_SESSIONS_DIR,
    DEFAULT_SESSION_CAP,
    SessionManager,
)
from coding_agent.state.todo import TaskStatus, TodoItem, TodoList
from coding_agent.state.workflow_impl import (
    Plan,
    WorkflowManager,
    WorkflowState,
)
