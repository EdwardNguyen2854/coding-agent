"""Tests for build_tools() and ToolDefinition wiring."""

from __future__ import annotations

import pytest

from coding_agent.tools import build_tools
from coding_agent.tools.base import ToolDefinition


@pytest.fixture
def tools(workspace):
    return build_tools(str(workspace))


class TestBuildTools:
    def test_returns_list(self, tools):
        assert isinstance(tools, list)

    def test_all_items_are_tool_definitions(self, tools):
        for t in tools:
            assert isinstance(t, ToolDefinition), f"{t!r} is not a ToolDefinition"

    def test_no_duplicate_names(self, tools):
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_expected_tools_present(self, tools):
        names = {t.name for t in tools}
        expected = {
            "file_read", "file_write", "file_edit", "file_patch",
            "file_list", "file_move", "file_delete",
            "glob", "grep",
            "shell", "safe_shell",
            "workspace_info",
            "git_status", "git_diff", "git_commit",
            "run_tests", "run_lint", "typecheck",
        }
        missing = expected - names
        assert not missing, f"Missing tools: {missing}"


class TestToolDefinitionFields:
    def test_name_is_string(self, tools):
        for t in tools:
            assert isinstance(t.name, str) and t.name

    def test_description_is_string(self, tools):
        for t in tools:
            assert isinstance(t.description, str) and t.description, (
                f"{t.name} has empty description"
            )

    def test_parameters_is_dict(self, tools):
        for t in tools:
            assert isinstance(t.parameters, dict), f"{t.name}.parameters is not a dict"

    def test_handler_is_callable(self, tools):
        for t in tools:
            assert callable(t.handler), f"{t.name}.handler is not callable"

    def test_schema_is_dict(self, tools):
        for t in tools:
            assert isinstance(t.schema, dict), f"{t.name}.schema is not a dict"

    def test_schema_has_name(self, tools):
        for t in tools:
            assert t.schema.get("name") == t.name, (
                f"{t.name}: schema['name'] mismatch"
            )

    def test_schema_has_description(self, tools):
        for t in tools:
            assert "description" in t.schema, f"{t.name} schema missing 'description'"

    def test_schema_has_properties(self, tools):
        for t in tools:
            assert "properties" in t.schema, f"{t.name} schema missing 'properties'"


class TestHandlerInvocation:
    """Verify that handler is properly wired to the tool's run() method."""

    def test_file_read_handler_callable(self, tools):
        t = next(x for x in tools if x.name == "file_read")
        # Missing required arg should return a ToolResult, not raise
        result = t.handler({})
        assert hasattr(result, "ok")

    def test_safe_shell_handler_returns_tool_result(self, tools):
        t = next(x for x in tools if x.name == "safe_shell")
        result = t.handler({"command": "rm -rf /"})
        assert hasattr(result, "ok")
        assert result.data.get("blocked") is True
