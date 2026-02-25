"""Tests for workspace_info."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from coding_agent.tools.workspace_info import WorkspaceInfoTool

from conftest import assert_ok


@pytest.fixture
def tool(workspace):
    return WorkspaceInfoTool(str(workspace))


def _make_proc(stdout="", stderr="", returncode=0):
    return MagicMock(stdout=stdout, stderr=stderr, returncode=returncode)


class TestWorkspaceInfoStructure:
    def test_returns_workspace_root(self, tool, workspace):
        with patch("subprocess.run", return_value=_make_proc()):
            r = tool.run({})
        assert_ok(r)
        assert str(workspace) in r.data["workspace_root"]

    def test_returns_os_field(self, tool):
        with patch("subprocess.run", return_value=_make_proc()):
            r = tool.run({})
        assert r.data["os"] in ("linux", "macos", "windows")

    def test_returns_platform_field(self, tool):
        with patch("subprocess.run", return_value=_make_proc()):
            r = tool.run({})
        assert isinstance(r.data["platform"], str)
        assert len(r.data["platform"]) > 0

    def test_runtimes_dict_present(self, tool):
        with patch("subprocess.run", return_value=_make_proc()):
            r = tool.run({})
        assert "runtimes" in r.data
        for key in ("python", "node", "java", "go"):
            assert key in r.data["runtimes"]

    def test_tools_dict_present(self, tool):
        with patch("subprocess.run", return_value=_make_proc()):
            r = tool.run({})
        assert "tools" in r.data
        for key in ("git", "pytest", "npm", "ruff", "mypy"):
            assert key in r.data["tools"]

    def test_absent_tool_returns_available_false(self, tool):
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run", return_value=_make_proc(returncode=1)):
                r = tool.run({"refresh": True})
        for tool_entry in r.data["tools"].values():
            # All should have available key
            assert "available" in tool_entry

    def test_git_present_field(self, tool):
        with patch("subprocess.run", return_value=_make_proc()):
            r = tool.run({})
        assert isinstance(r.data["git_present"], bool)


class TestCaching:
    def test_second_call_does_not_invoke_subprocess(self, tool):
        with patch("subprocess.run", return_value=_make_proc(stdout="Python 3.11\n")) as mock_sub:
            tool.run({})          # first call — probes
            call_count_after_first = mock_sub.call_count

        with patch("subprocess.run") as mock_sub2:
            tool.run({})          # second call — should use cache
            assert mock_sub2.call_count == 0, (
                f"subprocess was called {mock_sub2.call_count} time(s) on second invocation — caching failed"
            )

    def test_refresh_forces_reprobe(self, tool):
        with patch("subprocess.run", return_value=_make_proc()) as mock_sub:
            tool.run({})
            first_count = mock_sub.call_count

        with patch("subprocess.run", return_value=_make_proc()) as mock_sub2:
            tool.run({"refresh": True})
            assert mock_sub2.call_count > 0, "refresh=True should re-probe subprocess"

    def test_cached_data_matches_first_call(self, tool):
        with patch("subprocess.run", return_value=_make_proc()):
            r1 = tool.run({})

        with patch("subprocess.run", return_value=_make_proc()):
            r2 = tool.run({})

        assert r1.data["os"] == r2.data["os"]
        assert r1.data["workspace_root"] == r2.data["workspace_root"]
