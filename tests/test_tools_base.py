"""Tests for tool infrastructure (base types and registry)."""

import pytest
from dataclasses import asdict

from coding_agent.tools.base import ToolDefinition, ToolResult
from coding_agent.tools import get_openai_tools, register_tool, tool_registry


class TestToolResult:
    """Test ToolResult dataclass."""

    def test_tool_result_fields(self):
        """ToolResult has output, error, is_error fields."""
        result = ToolResult(output="file content", error=None, is_error=False)
        assert result.output == "file content"
        assert result.error is None
        assert result.is_error is False

    def test_tool_result_error_case(self):
        """ToolResult with error sets is_error True."""
        result = ToolResult(output="", error="File not found", is_error=True)
        assert result.is_error is True
        assert result.error == "File not found"


class TestToolDefinition:
    """Test ToolDefinition dataclass."""

    def test_tool_definition_fields(self):
        """ToolDefinition has name, description, parameters, handler."""
        def dummy_handler(params):
            return ToolResult(output="ok", error=None, is_error=False)

        tool_def = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object"},
            handler=dummy_handler,
        )
        assert tool_def.name == "test_tool"
        assert tool_def.description == "A test tool"
        assert tool_def.parameters == {"type": "object"}
        assert tool_def.handler is dummy_handler


class TestToolRegistry:
    """Test tool registry functions."""

    def test_tool_registry_starts_empty(self):
        """Registry starts empty (or with stub tools)."""
        assert isinstance(tool_registry, dict)

    def test_get_openai_tools_returns_list(self):
        """get_openai_tools returns a list."""
        tools = get_openai_tools()
        assert isinstance(tools, list)

    def test_register_tool_adds_to_registry(self):
        """register_tool adds tool to registry."""
        initial_count = len(tool_registry)

        def dummy_handler(params):
            return ToolResult(output="ok", error=None, is_error=False)

        tool_def = ToolDefinition(
            name="test_register_tool",
            description="Test",
            parameters={"type": "object"},
            handler=dummy_handler,
        )
        register_tool(tool_def)

        assert len(tool_registry) == initial_count + 1
        assert "test_register_tool" in tool_registry

    def test_get_openai_tools_includes_registered(self):
        """Registered tools appear in get_openai_tools output."""
        def dummy_handler(params):
            return ToolResult(output="ok", error=None, is_error=False)

        tool_def = ToolDefinition(
            name="test_get_tools",
            description="Test tool",
            parameters={"type": "object", "properties": {}},
            handler=dummy_handler,
        )
        register_tool(tool_def)

        tools = get_openai_tools()
        tool_names = [t.get("function", {}).get("name") for t in tools]
        assert "test_get_tools" in tool_names
