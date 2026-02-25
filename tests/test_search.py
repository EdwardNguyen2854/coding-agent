"""Tests for glob and grep."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from coding_agent.tools.glob import GlobTool
from coding_agent.tools.grep import GrepTool

from conftest import assert_fail, assert_ok, make_file


# ══════════════════════════════════════════════════════════════════════════════
# glob
# ══════════════════════════════════════════════════════════════════════════════

class TestGlob:
    @pytest.fixture
    def tool(self, workspace):
        return GlobTool(str(workspace))

    def test_finds_matching_files(self, tool, workspace):
        make_file(workspace, "src/foo.py", "")
        make_file(workspace, "src/bar.py", "")
        r = tool.run({"pattern": "**/*.py"})
        assert_ok(r)
        assert r.data["count"] == 2

    def test_no_matches_returns_empty(self, tool, workspace):
        r = tool.run({"pattern": "**/*.ts"})
        assert_ok(r)
        assert r.data["matches"] == []

    def test_hidden_excluded_by_default(self, tool, workspace):
        make_file(workspace, ".git/config", "")
        r = tool.run({"pattern": "**/*"})
        assert not any(".git" in m for m in r.data["matches"])

    def test_hidden_included_when_requested(self, tool, workspace):
        make_file(workspace, ".env", "")
        r = tool.run({"pattern": "**/.env", "include_hidden": True})
        assert r.data["count"] >= 1

    def test_max_results_truncates(self, tool, workspace):
        for i in range(10):
            make_file(workspace, f"file{i}.py", "")
        r = tool.run({"pattern": "*.py", "max_results": 3})
        assert r.data["count"] == 3
        assert r.data["truncated"] is True
        assert len(r.warnings) > 0

    def test_base_path_limits_search(self, tool, workspace):
        make_file(workspace, "src/a.py", "")
        make_file(workspace, "tests/b.py", "")
        r = tool.run({"pattern": "*.py", "base_path": "src"})
        assert all("tests" not in m for m in r.data["matches"])

    def test_invalid_base_path(self, tool):
        r = tool.run({"pattern": "*.py", "base_path": "nonexistent"})
        assert_fail(r, "DIR_NOT_FOUND")


# ══════════════════════════════════════════════════════════════════════════════
# grep
# ══════════════════════════════════════════════════════════════════════════════

class TestGrepPythonFallback:
    """Tests that run the pure-Python backend regardless of rg availability."""

    @pytest.fixture
    def tool(self, workspace):
        t = GrepTool(str(workspace))
        t._rg_available = False  # force Python fallback
        return t

    def test_finds_match(self, tool, workspace):
        make_file(workspace, "f.py", "def foo():\n    pass\n")
        r = tool.run({"pattern": "def foo"})
        assert_ok(r)
        assert r.data["match_count"] == 1

    def test_returns_file_and_line(self, tool, workspace):
        make_file(workspace, "f.py", "hello world\n")
        r = tool.run({"pattern": "hello"})
        assert r.data["matches"][0]["line_number"] == 1
        assert "f.py" in r.data["matches"][0]["file"]

    def test_no_match(self, tool, workspace):
        make_file(workspace, "f.py", "nothing here\n")
        r = tool.run({"pattern": "xyz123"})
        assert_ok(r)
        assert r.data["match_count"] == 0

    def test_case_insensitive(self, tool, workspace):
        make_file(workspace, "f.py", "Hello World\n")
        r = tool.run({"pattern": "hello", "case_sensitive": False})
        assert r.data["match_count"] == 1

    def test_case_sensitive_no_match(self, tool, workspace):
        make_file(workspace, "f.py", "Hello World\n")
        r = tool.run({"pattern": "hello", "case_sensitive": True})
        assert r.data["match_count"] == 0

    def test_glob_filter(self, tool, workspace):
        make_file(workspace, "a.py", "match this\n")
        make_file(workspace, "b.txt", "match this\n")
        r = tool.run({"pattern": "match", "glob": "*.py"})
        assert all(m["file"].endswith(".py") for m in r.data["matches"])

    def test_max_results_truncates(self, tool, workspace):
        make_file(workspace, "f.py", "x\n" * 20)
        r = tool.run({"pattern": "x", "max_results": 5})
        assert r.data["match_count"] == 5
        assert r.data["truncated"] is True

    def test_invalid_regex(self, tool, workspace):
        make_file(workspace, "f.py", "hello\n")
        r = tool.run({"pattern": "[invalid"})
        assert_fail(r, "INVALID_REGEX")

    def test_files_matched_populated(self, tool, workspace):
        make_file(workspace, "a.py", "foo\n")
        make_file(workspace, "b.py", "foo\n")
        r = tool.run({"pattern": "foo"})
        assert len(r.data["files_matched"]) == 2

    def test_parser_used_python_re(self, tool, workspace):
        make_file(workspace, "f.py", "x\n")
        r = tool.run({"pattern": "x"})
        assert r.data["parser_used"] == "python_re"


class TestGrepRipgrep:
    """Smoke-test the rg path using a mock subprocess."""

    @pytest.fixture
    def tool(self, workspace):
        t = GrepTool(str(workspace))
        t._rg_available = True
        return t

    def test_rg_called(self, tool, workspace):
        make_file(workspace, "f.py", "hello\n")
        rg_output = (
            '{"type":"match","data":{"path":{"text":"f.py"},'
            '"line_number":1,"lines":{"text":"hello\\n"},'
            '"submatches":[{"start":0,"end":5,"match":{"text":"hello"}}]}}\n'
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=rg_output, stderr=""
            )
            r = tool.run({"pattern": "hello", "path": str(workspace)})
        assert_ok(r)
        assert r.data["parser_used"] == "ripgrep"
        assert r.data["match_count"] == 1
