"""Tests for run_tests, run_lint, typecheck."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from coding_agent.tools.run_lint import RunLintTool
from coding_agent.tools.run_tests import RunTestsTool
from coding_agent.tools.typecheck import TypecheckTool

from conftest import assert_fail, assert_ok


def _proc(stdout="", stderr="", returncode=0):
    return MagicMock(stdout=stdout, stderr=stderr, returncode=returncode)


# ══════════════════════════════════════════════════════════════════════════════
# run_tests
# ══════════════════════════════════════════════════════════════════════════════

PYTEST_PASS_OUTPUT = """\
collected 3 items

tests/test_foo.py ...                                               [100%]

==================== 3 passed in 0.12s ====================
"""

PYTEST_FAIL_OUTPUT = """\
collected 3 items

tests/test_foo.py .F.                                               [ 66%]

======================== FAILURES ========================
FAILED tests/test_foo.py::test_bar - AssertionError: 0 != 1
==================== 1 failed, 2 passed in 0.15s ====================
"""


class TestRunTests:
    @pytest.fixture
    def tool(self, workspace):
        return RunTestsTool(str(workspace))

    def test_passing_suite(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=PYTEST_PASS_OUTPUT)):
            r = tool.run({"command": "pytest"})
        assert_ok(r)
        assert r.data["passed"] is True
        assert r.data["failures"] == []

    def test_failing_suite(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=PYTEST_FAIL_OUTPUT, returncode=1)):
            r = tool.run({"command": "pytest"})
        assert_ok(r)
        assert r.data["passed"] is False
        assert len(r.data["failures"]) >= 1

    def test_failure_has_file_and_test(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=PYTEST_FAIL_OUTPUT, returncode=1)):
            r = tool.run({"command": "pytest"})
        f = r.data["failures"][0]
        assert "test_foo.py" in f["file"]
        assert "test_bar" in f["test"]

    def test_passed_count_parsed(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=PYTEST_PASS_OUTPUT)):
            r = tool.run({"command": "pytest"})
        assert r.data["passed_count"] == 3

    def test_failed_count_parsed(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=PYTEST_FAIL_OUTPUT, returncode=1)):
            r = tool.run({"command": "pytest"})
        assert r.data["failed_count"] == 1

    def test_raw_output_always_present(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=PYTEST_PASS_OUTPUT)):
            r = tool.run({"command": "pytest"})
        assert "raw_output" in r.data
        assert len(r.data["raw_output"]) > 0

    def test_focus_appended_to_command(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=PYTEST_PASS_OUTPUT)) as mock:
            tool.run({"command": "pytest", "focus": ["tests/test_foo.py::test_bar"]})
        cmd = mock.call_args.kwargs.get("args") or mock.call_args.args[0]
        assert "test_foo.py" in str(cmd)

    def test_timeout(self, tool):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pytest", 1)):
            r = tool.run({"command": "pytest", "timeout_sec": 1})
        assert_fail(r, "TIMEOUT")

    def test_auto_detect_fails_gracefully(self, tool):
        with patch("shutil.which", return_value=None):
            r = tool.run({})
        assert_fail(r, "COMMAND_REQUIRED")

    def test_warning_emitted_on_failure(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=PYTEST_FAIL_OUTPUT, returncode=1)):
            r = tool.run({"command": "pytest"})
        assert len(r.warnings) > 0


# ══════════════════════════════════════════════════════════════════════════════
# run_lint
# ══════════════════════════════════════════════════════════════════════════════

RUFF_JSON_OUTPUT = """\
[
  {
    "filename": "src/foo.py",
    "location": {"row": 10, "column": 4},
    "code": "E501",
    "message": "Line too long (92 > 88 characters)"
  }
]
"""

ESLINT_JSON_OUTPUT = """\
[
  {
    "filePath": "src/app.js",
    "messages": [
      {"line": 5, "column": 3, "ruleId": "no-console", "message": "Unexpected console statement.", "severity": 1}
    ]
  }
]
"""


class TestRunLint:
    @pytest.fixture
    def tool(self, workspace):
        return RunLintTool(str(workspace))

    def test_ruff_clean(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout="[]", returncode=0)):
            r = tool.run({"command": "ruff check --output-format json"})
        assert_ok(r)
        assert r.data["clean"] is True
        assert r.data["issue_count"] == 0

    def test_ruff_issues_parsed(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=RUFF_JSON_OUTPUT, returncode=1)):
            r = tool.run({"command": "ruff check --output-format json"})
        assert_ok(r)
        assert r.data["issue_count"] == 1
        issue = r.data["issues"][0]
        assert issue["file"] == "src/foo.py"
        assert issue["line"] == 10
        assert issue["rule"] == "E501"

    def test_eslint_issues_parsed(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=ESLINT_JSON_OUTPUT, returncode=1)):
            r = tool.run({"command": "eslint --format json"})
        assert r.data["issues"][0]["file"] == "src/app.js"
        assert r.data["issues"][0]["rule"] == "no-console"

    def test_issue_has_required_fields(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=RUFF_JSON_OUTPUT, returncode=1)):
            r = tool.run({"command": "ruff check --output-format json"})
        issue = r.data["issues"][0]
        for field in ("file", "line", "col", "rule", "message", "severity"):
            assert field in issue, f"Missing field: {field}"

    def test_raw_output_present(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=RUFF_JSON_OUTPUT, returncode=1)):
            r = tool.run({"command": "ruff check --output-format json"})
        assert "raw_output" in r.data

    def test_parser_used_reported(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout="[]")):
            r = tool.run({"command": "ruff check --output-format json"})
        assert "parser_used" in r.data

    def test_paths_appended(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout="[]")) as mock:
            tool.run({"command": "ruff check --output-format json", "paths": ["src/"]})
        cmd = mock.call_args.args[0]
        assert "src/" in str(cmd)

    def test_timeout(self, tool):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ruff", 60)):
            r = tool.run({"command": "ruff check"})
        assert_fail(r, "TIMEOUT")

    def test_no_linter_detected(self, tool):
        with patch("shutil.which", return_value=None):
            r = tool.run({})
        assert_fail(r, "COMMAND_REQUIRED")


# ══════════════════════════════════════════════════════════════════════════════
# typecheck
# ══════════════════════════════════════════════════════════════════════════════

MYPY_OUTPUT = """\
src/foo.py:12: error: Incompatible return value type (got "str", expected "int")  [return-value]
src/foo.py:20: error: Argument 1 to "bar" has incompatible type "str"; expected "int"  [arg-type]
Found 2 errors in 1 file (checked 3 source files)
"""

PYRIGHT_OUTPUT = """\
  src/foo.py:12:5: error: Return type "str" is incompatible with declared type "int" (reportReturnType)
  src/foo.py:20:10: error: Argument of type "str" cannot be assigned to parameter (reportArgumentType)
2 errors, 0 warnings, 0 informations
"""


class TestTypecheck:
    @pytest.fixture
    def tool(self, workspace):
        return TypecheckTool(str(workspace))

    def test_mypy_clean(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout="Success: no issues found", returncode=0)):
            r = tool.run({"command": "mypy"})
        assert_ok(r)
        assert r.data["clean"] is True

    def test_mypy_errors_parsed(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=MYPY_OUTPUT, returncode=1)):
            r = tool.run({"command": "mypy"})
        assert_ok(r)
        assert r.data["issue_count"] == 2
        issue = r.data["issues"][0]
        assert issue["file"] == "src/foo.py"
        assert issue["line"] == 12
        assert issue["severity"] == "error"

    def test_pyright_errors_parsed(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=PYRIGHT_OUTPUT, returncode=1)):
            r = tool.run({"command": "pyright"})
        assert r.data["issue_count"] == 2

    def test_issue_has_required_fields(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=MYPY_OUTPUT, returncode=1)):
            r = tool.run({"command": "mypy"})
        issue = r.data["issues"][0]
        for field in ("file", "line", "col", "rule", "message", "severity"):
            assert field in issue

    def test_raw_output_present(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=MYPY_OUTPUT, returncode=1)):
            r = tool.run({"command": "mypy"})
        assert "raw_output" in r.data
        assert len(r.data["raw_output"]) > 0

    def test_parser_used_reported(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout="", returncode=0)):
            r = tool.run({"command": "mypy"})
        assert "parser_used" in r.data

    def test_no_checker_detected(self, tool):
        with patch("shutil.which", return_value=None):
            r = tool.run({})
        assert_fail(r, "COMMAND_REQUIRED")

    def test_timeout(self, tool):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("mypy", 120)):
            r = tool.run({"command": "mypy"})
        assert_fail(r, "TIMEOUT")

    def test_warning_emitted_on_errors(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=MYPY_OUTPUT, returncode=1)):
            r = tool.run({"command": "mypy"})
        assert len(r.warnings) > 0
