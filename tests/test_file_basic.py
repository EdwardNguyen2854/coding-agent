"""Tests for file_read, file_write, file_edit."""

from __future__ import annotations

import pytest

from coding_agent.tools.file_edit import FileEditTool
from coding_agent.tools.file_read import FileReadTool
from coding_agent.tools.file_write import FileWriteTool

from conftest import assert_fail, assert_ok, make_file


# ══════════════════════════════════════════════════════════════════════════════
# file_read
# ══════════════════════════════════════════════════════════════════════════════

class TestFileRead:
    @pytest.fixture
    def tool(self, workspace):
        return FileReadTool(str(workspace))

    def test_reads_file(self, tool, workspace):
        make_file(workspace, "hello.txt", "line1\nline2\nline3\n")
        r = tool.run({"path": "hello.txt"})
        assert_ok(r)
        assert r.data["content"] == "line1\nline2\nline3\n"

    def test_returns_total_lines(self, tool, workspace):
        make_file(workspace, "f.txt", "a\nb\nc\n")
        r = tool.run({"path": "f.txt"})
        assert r.data["total_lines"] == 3

    def test_offset(self, tool, workspace):
        make_file(workspace, "f.txt", "a\nb\nc\n")
        r = tool.run({"path": "f.txt", "offset": 1})
        assert_ok(r)
        assert r.data["content"] == "b\nc\n"

    def test_limit(self, tool, workspace):
        make_file(workspace, "f.txt", "a\nb\nc\n")
        r = tool.run({"path": "f.txt", "limit": 2})
        assert_ok(r)
        assert r.data["returned_lines"] == 2

    def test_offset_and_limit(self, tool, workspace):
        make_file(workspace, "f.txt", "a\nb\nc\nd\n")
        r = tool.run({"path": "f.txt", "offset": 1, "limit": 2})
        assert r.data["content"] == "b\nc\n"

    def test_file_not_found(self, tool):
        r = tool.run({"path": "missing.txt"})
        assert_fail(r, "FILE_NOT_FOUND")

    def test_path_traversal_blocked(self, tool):
        r = tool.run({"path": "../../etc/passwd"})
        assert_fail(r, "PATH_OUTSIDE_WORKSPACE")

    def test_absolute_path_inside_workspace(self, tool, workspace):
        p = make_file(workspace, "abs.txt", "hi\n")
        r = tool.run({"path": str(p)})
        assert_ok(r)

    def test_missing_path_arg(self, tool):
        r = tool.run({})
        assert_fail(r, "INVALID_ARGS")


# ══════════════════════════════════════════════════════════════════════════════
# file_write
# ══════════════════════════════════════════════════════════════════════════════

class TestFileWrite:
    @pytest.fixture
    def tool(self, workspace):
        return FileWriteTool(str(workspace))

    def test_creates_file(self, tool, workspace):
        r = tool.run({"path": "new.txt", "content": "hello"})
        assert_ok(r)
        assert (workspace / "new.txt").read_text() == "hello"

    def test_reports_created_true(self, tool):
        r = tool.run({"path": "new.txt", "content": ""})
        assert r.data["created"] is True
        assert r.data["overwritten"] is False

    def test_overwrites_by_default(self, tool, workspace):
        make_file(workspace, "f.txt", "old")
        r = tool.run({"path": "f.txt", "content": "new"})
        assert_ok(r)
        assert (workspace / "f.txt").read_text() == "new"
        assert r.data["overwritten"] is True

    def test_overwrite_false_blocks(self, tool, workspace):
        make_file(workspace, "f.txt", "old")
        r = tool.run({"path": "f.txt", "content": "new", "overwrite": False})
        assert_fail(r, "FILE_EXISTS")
        assert (workspace / "f.txt").read_text() == "old"

    def test_creates_intermediate_dirs(self, tool, workspace):
        r = tool.run({"path": "a/b/c/file.txt", "content": "x"})
        assert_ok(r)
        assert (workspace / "a" / "b" / "c" / "file.txt").exists()

    def test_reports_bytes_written(self, tool):
        r = tool.run({"path": "f.txt", "content": "abc"})
        assert r.data["bytes_written"] == 3

    def test_path_traversal_blocked(self, tool):
        r = tool.run({"path": "../../evil.txt", "content": "x"})
        assert_fail(r, "PATH_OUTSIDE_WORKSPACE")


# ══════════════════════════════════════════════════════════════════════════════
# file_edit
# ══════════════════════════════════════════════════════════════════════════════

class TestFileEdit:
    @pytest.fixture
    def tool(self, workspace):
        return FileEditTool(str(workspace))

    def test_replaces_string(self, tool, workspace):
        make_file(workspace, "f.txt", "foo bar baz")
        r = tool.run({"path": "f.txt", "old_str": "bar", "new_str": "QUX"})
        assert_ok(r)
        assert (workspace / "f.txt").read_text() == "foo QUX baz"

    def test_match_not_found(self, tool, workspace):
        make_file(workspace, "f.txt", "hello world")
        r = tool.run({"path": "f.txt", "old_str": "missing", "new_str": "x"})
        assert_fail(r, "MATCH_NOT_FOUND")

    def test_ambiguous_match(self, tool, workspace):
        make_file(workspace, "f.txt", "aaa aaa")
        r = tool.run({"path": "f.txt", "old_str": "aaa", "new_str": "bbb"})
        assert_fail(r, "AMBIGUOUS_MATCH")

    def test_file_not_found(self, tool):
        r = tool.run({"path": "ghost.txt", "old_str": "x", "new_str": "y"})
        assert_fail(r, "FILE_NOT_FOUND")

    def test_multiline_replacement(self, tool, workspace):
        make_file(workspace, "f.txt", "line1\nline2\nline3\n")
        r = tool.run({"path": "f.txt", "old_str": "line1\nline2\n", "new_str": "replaced\n"})
        assert_ok(r)
        assert (workspace / "f.txt").read_text() == "replaced\nline3\n"

    def test_reports_line_change(self, tool, workspace):
        make_file(workspace, "f.txt", "a\nb\nc\n")
        r = tool.run({"path": "f.txt", "old_str": "a\nb\n", "new_str": "x\ny\nz\n"})
        assert r.data["net_line_change"] == 1  # 3 new - 2 old

    def test_path_traversal_blocked(self, tool):
        r = tool.run({"path": "../../etc/hosts", "old_str": "a", "new_str": "b"})
        assert_fail(r, "PATH_OUTSIDE_WORKSPACE")
