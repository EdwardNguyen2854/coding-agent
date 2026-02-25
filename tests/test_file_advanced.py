"""Tests for file_list, file_move, file_delete."""

from __future__ import annotations

import pytest

from coding_agent.tools.file_delete import FileDeleteTool
from coding_agent.tools.file_list import FileListTool
from coding_agent.tools.file_move import FileMoveTool

from conftest import assert_fail, assert_ok, make_file


# ══════════════════════════════════════════════════════════════════════════════
# file_list
# ══════════════════════════════════════════════════════════════════════════════

class TestFileList:
    @pytest.fixture
    def tool(self, workspace):
        return FileListTool(str(workspace))

    def test_returns_tree(self, tool, workspace):
        make_file(workspace, "src/main.py", "")
        r = tool.run({})
        assert_ok(r)
        assert "tree" in r.data
        assert r.data["tree"]["type"] == "dir"

    def test_file_appears_in_tree(self, tool, workspace):
        make_file(workspace, "hello.py", "")
        r = tool.run({"depth": 1})
        names = [c["name"] for c in r.data["tree"].get("children", [])]
        assert "hello.py" in names

    def test_nested_file_at_depth_2(self, tool, workspace):
        make_file(workspace, "src/util.py", "")
        r = tool.run({"depth": 2})

        def find(node, name):
            if node["name"] == name:
                return True
            for child in node.get("children", []):
                if find(child, name):
                    return True
            return False

        assert find(r.data["tree"], "util.py")

    def test_depth_0_no_children(self, tool, workspace):
        make_file(workspace, "f.py", "")
        r = tool.run({"depth": 0})
        assert r.data["tree"].get("children") is None or r.data["tree"].get("children") == []

    def test_hidden_excluded_by_default(self, tool, workspace):
        make_file(workspace, ".hidden", "")
        r = tool.run({"depth": 1})
        names = [c["name"] for c in r.data["tree"].get("children", [])]
        assert ".hidden" not in names

    def test_hidden_included_when_requested(self, tool, workspace):
        make_file(workspace, ".hidden", "")
        r = tool.run({"depth": 1, "include_hidden": True})
        names = [c["name"] for c in r.data["tree"].get("children", [])]
        assert ".hidden" in names

    def test_file_node_has_size(self, tool, workspace):
        make_file(workspace, "f.txt", "abc")
        r = tool.run({"depth": 1})
        file_nodes = [c for c in r.data["tree"].get("children", []) if c["name"] == "f.txt"]
        assert file_nodes[0]["size"] == 3

    def test_path_not_found(self, tool):
        r = tool.run({"path": "nonexistent"})
        assert_fail(r, "DIR_NOT_FOUND")


# ══════════════════════════════════════════════════════════════════════════════
# file_move
# ══════════════════════════════════════════════════════════════════════════════

class TestFileMove:
    @pytest.fixture
    def tool(self, workspace):
        return FileMoveTool(str(workspace))

    def test_moves_file(self, tool, workspace):
        make_file(workspace, "a.txt", "hi")
        r = tool.run({"src": "a.txt", "dst": "b.txt"})
        assert_ok(r)
        assert (workspace / "b.txt").exists()
        assert not (workspace / "a.txt").exists()

    def test_reports_moved_paths(self, tool, workspace):
        make_file(workspace, "a.txt", "")
        r = tool.run({"src": "a.txt", "dst": "b.txt"})
        assert r.data["moved_from"] == "a.txt"
        assert r.data["moved_to"] == "b.txt"

    def test_creates_intermediate_dirs(self, tool, workspace):
        make_file(workspace, "a.txt", "")
        r = tool.run({"src": "a.txt", "dst": "sub/dir/a.txt"})
        assert_ok(r)
        assert (workspace / "sub" / "dir" / "a.txt").exists()
        assert len(r.data["dirs_created"]) > 0

    def test_overwrite_false_blocks(self, tool, workspace):
        make_file(workspace, "a.txt", "src")
        make_file(workspace, "b.txt", "dst")
        r = tool.run({"src": "a.txt", "dst": "b.txt", "overwrite": False})
        assert_fail(r, "DST_EXISTS")

    def test_overwrite_true_replaces(self, tool, workspace):
        make_file(workspace, "a.txt", "new")
        make_file(workspace, "b.txt", "old")
        r = tool.run({"src": "a.txt", "dst": "b.txt", "overwrite": True})
        assert_ok(r)
        assert (workspace / "b.txt").read_text() == "new"

    def test_src_not_found(self, tool):
        r = tool.run({"src": "ghost.txt", "dst": "dest.txt"})
        assert_fail(r, "SRC_NOT_FOUND")

    def test_dst_outside_workspace_blocked(self, tool, workspace):
        make_file(workspace, "a.txt", "")
        r = tool.run({"src": "a.txt", "dst": "/tmp/evil.txt"})
        assert_fail(r, "PATH_OUTSIDE_WORKSPACE")

    def test_moves_directory(self, tool, workspace):
        make_file(workspace, "mydir/file.txt", "x")
        r = tool.run({"src": "mydir", "dst": "newdir"})
        assert_ok(r)
        assert (workspace / "newdir" / "file.txt").exists()


# ══════════════════════════════════════════════════════════════════════════════
# file_delete
# ══════════════════════════════════════════════════════════════════════════════

class TestFileDelete:
    @pytest.fixture
    def tool(self, workspace):
        return FileDeleteTool(str(workspace))

    def test_deletes_file(self, tool, workspace):
        make_file(workspace, "f.txt", "")
        r = tool.run({"path": "f.txt"})
        assert_ok(r)
        assert not (workspace / "f.txt").exists()

    def test_reports_was_directory_false(self, tool, workspace):
        make_file(workspace, "f.txt", "")
        r = tool.run({"path": "f.txt"})
        assert r.data["was_directory"] is False

    def test_directory_without_recursive_blocked(self, tool, workspace):
        make_file(workspace, "mydir/file.txt", "")
        r = tool.run({"path": "mydir"})
        assert_fail(r, "RECURSIVE_REQUIRED")
        assert (workspace / "mydir").exists()  # not deleted

    def test_directory_with_recursive_deleted(self, tool, workspace):
        make_file(workspace, "mydir/file.txt", "")
        r = tool.run({"path": "mydir", "recursive": True})
        assert_ok(r)
        assert not (workspace / "mydir").exists()

    def test_reports_was_directory_true(self, tool, workspace):
        make_file(workspace, "mydir/file.txt", "")
        r = tool.run({"path": "mydir", "recursive": True})
        assert r.data["was_directory"] is True

    def test_not_found(self, tool):
        r = tool.run({"path": "ghost.txt"})
        assert_fail(r, "NOT_FOUND")

    def test_path_traversal_blocked(self, tool):
        r = tool.run({"path": "../../etc/passwd"})
        assert_fail(r, "PATH_OUTSIDE_WORKSPACE")
