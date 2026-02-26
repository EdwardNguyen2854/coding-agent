"""Tests for ToolResult dataclass and factory methods."""

from __future__ import annotations

import pytest

from coding_agent.core.tool_result import ToolResult


class TestToolResultFields:
    def test_all_fields_present(self):
        r = ToolResult(
            ok=True,
            error_code=None,
            message="ok",
            data={"k": "v"},
            warnings=["w"],
            artifacts=[{"type": "file", "path": "/a"}],
        )
        assert r.ok is True
        assert r.error_code is None
        assert r.message == "ok"
        assert r.data == {"k": "v"}
        assert r.warnings == ["w"]
        assert r.artifacts == [{"type": "file", "path": "/a"}]

    def test_defaults(self):
        r = ToolResult(ok=True, error_code=None, message="")
        assert r.data == {}
        assert r.warnings == []
        assert r.artifacts == []


class TestSuccessFactory:
    def test_ok_true(self):
        r = ToolResult.success()
        assert r.ok is True

    def test_error_code_none(self):
        r = ToolResult.success()
        assert r.error_code is None

    def test_data_passed_through(self):
        r = ToolResult.success(data={"x": 1})
        assert r.data == {"x": 1}

    def test_message_passed_through(self):
        r = ToolResult.success(message="done")
        assert r.message == "done"

    def test_warnings_passed_through(self):
        r = ToolResult.success(warnings=["heads up"])
        assert r.warnings == ["heads up"]

    def test_artifacts_passed_through(self):
        art = [{"type": "file", "path": "/out"}]
        r = ToolResult.success(artifacts=art)
        assert r.artifacts == art

    def test_defaults_are_empty(self):
        r = ToolResult.success()
        assert r.data == {}
        assert r.warnings == []
        assert r.artifacts == []

    def test_data_not_shared_between_instances(self):
        a = ToolResult.success()
        b = ToolResult.success()
        a.data["x"] = 1
        assert "x" not in b.data


class TestFailureFactory:
    def test_ok_false(self):
        r = ToolResult.failure("ERR", "bad")
        assert r.ok is False

    def test_error_code_set(self):
        r = ToolResult.failure("MY_CODE", "msg")
        assert r.error_code == "MY_CODE"

    def test_message_set(self):
        r = ToolResult.failure("ERR", "something went wrong")
        assert r.message == "something went wrong"

    def test_data_passed_through(self):
        r = ToolResult.failure("ERR", "msg", data={"detail": "x"})
        assert r.data == {"detail": "x"}

    def test_warnings_passed_through(self):
        r = ToolResult.failure("ERR", "msg", warnings=["note"])
        assert r.warnings == ["note"]

    def test_defaults_are_empty(self):
        r = ToolResult.failure("ERR", "msg")
        assert r.data == {}
        assert r.warnings == []
        assert r.artifacts == []
