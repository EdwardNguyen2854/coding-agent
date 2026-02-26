"""Coding-Agent - Self-hosted, model-agnostic AI coding agent."""

from importlib.metadata import version

__version__ = version("coding-agent")

from coding_agent.config import AgentConfig, load_config, ConfigError
from coding_agent.core.agent import Agent
from coding_agent.core.conversation import ConversationManager
from coding_agent.core.llm import LLMClient
from coding_agent.core.permissions import PermissionSystem
from coding_agent.core.tool_result import ToolResult
from coding_agent.state.session import SessionManager
from coding_agent.state.todo import TodoItem, TodoList
from coding_agent.state.workflow_impl import WorkflowManager, WorkflowState
from coding_agent.ui.cli import main
from coding_agent.ui.renderer import Renderer
