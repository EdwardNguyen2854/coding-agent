"""Tests for ToolGuard middleware."""

from __future__ import annotations

import json

import pytest

from coding_agent.core.tool_guard import ToolGuard
from coding_agent.core.tool_result import ToolResult


@pytest.fixture
def guard(tmp_path):
    return ToolGuard(workspace_root=str(tmp_path), policy={})


@pytest.fixture
def guard_with_policy(tmp_path):
    policy = {
        "deny_tools": ["shell"],
        "deny_actions": {"file_delete": True},
    }
    return ToolGuard(workspace_root=str(tmp_path), policy=policy)


SIMPLE_SCHEMA = {
    "properties": {
        "path": {"type": "string"},
        "count": {"type": "integer"},
    },
    "required": ["path"],
}


class TestValidCall:
    def test_returns_none_when_allowed(self, guard, tmp_path):
        result = guard.check("file_read", {"path": str(tmp_path)})
        assert result is None

    def test_valid_args_pass_schema(self, guard, tmp_path):
        result = guard.check("file_read", {"path": str(tmp_path), "count": 5}, schema=SIMPLE_SCHEMA)
        assert result is None


class TestInvalidArgs:
    def test_missing_required_field(self, guard):
        result = guard.check("file_read", {}, schema=SIMPLE_SCHEMA)
        assert result is not None
        assert not result.ok
        assert result.error_code == "INVALID_ARGS"
        assert "path" in result.message

    def test_wrong_type(self, guard, tmp_path):
        result = guard.check(
            "file_read",
            {"path": str(tmp_path), "count": "not-an-int"},
            schema=SIMPLE_SCHEMA,
        )
        assert result is not None
        assert result.error_code == "INVALID_ARGS"
        assert "count" in result.message

    def test_extra_fields_are_allowed(self, guard, tmp_path):
        # Unknown fields should not cause a failure
        result = guard.check(
            "file_read",
            {"path": str(tmp_path), "unknown_extra": True},
            schema=SIMPLE_SCHEMA,
        )
        assert result is None


class TestPathTraversal:
    def test_absolute_traversal_blocked(self, guard):
        result = guard.check("file_read", {"path": "/etc/passwd"})
        assert result is not None
        assert not result.ok
        assert result.error_code == "PATH_OUTSIDE_WORKSPACE"

    def test_relative_traversal_blocked(self, guard, tmp_path):
        evil = str(tmp_path / "../../etc/passwd")
        result = guard.check("file_read", {"path": evil})
        assert result is not None
        assert result.error_code == "PATH_OUTSIDE_WORKSPACE"

    def test_path_inside_workspace_allowed(self, guard, tmp_path):
        safe = str(tmp_path / "subdir" / "file.txt")
        result = guard.check("file_read", {"path": safe})
        assert result is None

    def test_workspace_root_itself_allowed(self, guard, tmp_path):
        result = guard.check("file_read", {"path": str(tmp_path)})
        assert result is None

    def test_multiline_value_not_treated_as_path(self, guard):
        # diff_text contains newlines and should not be path-checked
        result = guard.check("file_patch", {"diff_text": "--- a/foo\n+++ b/foo\n"})
        assert result is None


class TestDenyList:
    def test_denied_tool_blocked(self, guard_with_policy):
        result = guard_with_policy.check("shell", {"command": "ls"})
        assert result is not None
        assert not result.ok
        assert result.error_code == "DENIED_BY_POLICY"
        assert "shell" in result.message

    def test_denied_action_blocked(self, guard_with_policy):
        result = guard_with_policy.check("file_delete", {"path": "/tmp/x"})
        assert result is not None
        assert result.error_code == "DENIED_BY_POLICY"

    def test_allowed_tool_not_blocked(self, guard_with_policy, tmp_path):
        result = guard_with_policy.check("file_read", {"path": str(tmp_path)})
        assert result is None


class TestLogging:
    def test_log_file_created(self, tmp_path):
        log_path = str(tmp_path / "tool_calls.log")
        guard = ToolGuard(workspace_root=str(tmp_path), policy={}, log_path=log_path)
        guard.check("file_read", {"path": str(tmp_path)})

        import os
        assert os.path.exists(log_path)

    def test_allowed_call_logged(self, tmp_path):
        log_path = str(tmp_path / "tool_calls.log")
        guard = ToolGuard(workspace_root=str(tmp_path), policy={}, log_path=log_path)
        guard.check("file_read", {"path": str(tmp_path)})

        entries = [json.loads(l) for l in open(log_path)]
        assert len(entries) == 1
        assert entries[0]["tool_name"] == "file_read"
        assert entries[0]["denied"] is False

    def test_blocked_call_logged(self, tmp_path):
        log_path = str(tmp_path / "tool_calls.log")
        guard = ToolGuard(
            workspace_root=str(tmp_path),
            policy={"deny_tools": ["shell"]},
            log_path=log_path,
        )
        guard.check("shell", {"command": "ls"})

        entries = [json.loads(l) for l in open(log_path)]
        assert entries[0]["denied"] is True
        assert entries[0]["error_code"] == "DENIED_BY_POLICY"

    def test_log_is_append_only(self, tmp_path):
        log_path = str(tmp_path / "tool_calls.log")
        guard = ToolGuard(workspace_root=str(tmp_path), policy={}, log_path=log_path)
        guard.check("file_read", {"path": str(tmp_path)})
        guard.check("file_read", {"path": str(tmp_path)})

        entries = [json.loads(l) for l in open(log_path)]
        assert len(entries) == 2
