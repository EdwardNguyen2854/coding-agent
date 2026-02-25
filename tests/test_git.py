"""Tests for git_status, git_diff, git_commit."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from coding_agent.tools.git_commit import GitCommitTool
from coding_agent.tools.git_diff import GitDiffTool
from coding_agent.tools.git_status import GitStatusTool

from conftest import assert_fail, assert_ok


def _proc(stdout="", stderr="", returncode=0):
    return MagicMock(stdout=stdout, stderr=stderr, returncode=returncode)


# ══════════════════════════════════════════════════════════════════════════════
# git_status
# ══════════════════════════════════════════════════════════════════════════════

PORCELAIN_OUTPUT = """\
# branch.oid abc1234
# branch.head main
# branch.upstream origin/main
# branch.ab +2 -1
1 M. N... 100644 100644 100644 aaa bbb staged_file.py
1 .M N... 100644 100644 100644 ccc ddd unstaged_file.py
? untracked.txt
"""


class TestGitStatus:
    @pytest.fixture
    def tool(self, workspace):
        return GitStatusTool(str(workspace))

    def test_returns_branch(self, tool):
        with patch("subprocess.run") as mock:
            mock.side_effect = [
                _proc(stdout="main\n"),           # rev-parse branch
                _proc(stdout="origin/main\n"),    # upstream
                _proc(stdout="1\t2\n"),           # ahead/behind
                _proc(stdout=PORCELAIN_OUTPUT),   # status
                _proc(stdout="/workspace\n"),     # repo root
            ]
            r = tool.run({})
        assert_ok(r)
        assert r.data["branch"] == "main"

    def test_returns_upstream(self, tool):
        with patch("subprocess.run") as mock:
            mock.side_effect = [
                _proc(stdout="main\n"),
                _proc(stdout="origin/main\n"),
                _proc(stdout="0\t0\n"),
                _proc(stdout=PORCELAIN_OUTPUT),
                _proc(stdout="/workspace\n"),
            ]
            r = tool.run({})
        assert r.data["upstream"] == "origin/main"

    def test_staged_files(self, tool):
        with patch("subprocess.run") as mock:
            mock.side_effect = [
                _proc(stdout="main\n"),
                _proc(stdout="origin/main\n"),
                _proc(stdout="0\t0\n"),
                _proc(stdout=PORCELAIN_OUTPUT),
                _proc(stdout="/workspace\n"),
            ]
            r = tool.run({})
        assert "staged_file.py" in r.data["staged"]

    def test_unstaged_files(self, tool):
        with patch("subprocess.run") as mock:
            mock.side_effect = [
                _proc(stdout="main\n"),
                _proc(stdout="origin/main\n"),
                _proc(stdout="0\t0\n"),
                _proc(stdout=PORCELAIN_OUTPUT),
                _proc(stdout="/workspace\n"),
            ]
            r = tool.run({})
        assert "unstaged_file.py" in r.data["unstaged"]

    def test_untracked_files(self, tool):
        with patch("subprocess.run") as mock:
            mock.side_effect = [
                _proc(stdout="main\n"),
                _proc(stdout="origin/main\n"),
                _proc(stdout="0\t0\n"),
                _proc(stdout=PORCELAIN_OUTPUT),
                _proc(stdout="/workspace\n"),
            ]
            r = tool.run({})
        assert "untracked.txt" in r.data["untracked"]

    def test_not_a_repo(self, tool):
        with patch("subprocess.run", return_value=_proc(returncode=128, stderr="not a git repo")):
            r = tool.run({})
        assert_fail(r, "NOT_A_REPO")


# ══════════════════════════════════════════════════════════════════════════════
# git_diff
# ══════════════════════════════════════════════════════════════════════════════

SAMPLE_DIFF = """\
diff --git a/src/foo.py b/src/foo.py
index abc..def 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,3 +1,3 @@
 line1
-old
+new
 line3
"""


class TestGitDiff:
    @pytest.fixture
    def tool(self, workspace):
        return GitDiffTool(str(workspace))

    def test_returns_diff_text(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=SAMPLE_DIFF)):
            r = tool.run({})
        assert_ok(r)
        assert "diff --git" in r.data["diff_text"]

    def test_files_changed_populated(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=SAMPLE_DIFF)):
            r = tool.run({})
        assert len(r.data["files_changed"]) == 1
        assert r.data["files_changed"][0]["path"] == "src/foo.py"

    def test_additions_deletions(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout=SAMPLE_DIFF)):
            r = tool.run({})
        fc = r.data["files_changed"][0]
        assert fc["additions"] >= 1
        assert fc["deletions"] >= 1

    def test_staged_flag_passed(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout="")) as mock:
            tool.run({"staged": True})
        cmd = mock.call_args.args[0]
        assert "--cached" in cmd

    def test_ref_to_ref_diff(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout="")) as mock:
            tool.run({"base_ref": "main", "target_ref": "HEAD"})
        cmd = mock.call_args.args[0]
        assert any("main...HEAD" in str(a) for a in cmd)

    def test_empty_diff_no_files_changed(self, tool):
        with patch("subprocess.run", return_value=_proc(stdout="")):
            r = tool.run({})
        assert_ok(r)
        assert r.data["files_changed"] == []

    def test_git_error(self, tool):
        with patch("subprocess.run", return_value=_proc(returncode=2, stderr="fatal")):
            r = tool.run({})
        assert_fail(r, "GIT_ERROR")


# ══════════════════════════════════════════════════════════════════════════════
# git_commit
# ══════════════════════════════════════════════════════════════════════════════

class TestGitCommit:
    @pytest.fixture
    def tool(self, workspace):
        return GitCommitTool(str(workspace))

    def test_confirmation_required(self, tool):
        r = tool.run({"message": "test", "confirmed": False})
        assert_fail(r, "CONFIRMATION_REQUIRED")

    def test_confirmation_missing_defaults_to_false(self, tool):
        r = tool.run({"message": "test"})
        assert_fail(r, "CONFIRMATION_REQUIRED")

    def test_nothing_staged_blocked(self, tool):
        with patch("subprocess.run") as mock:
            mock.side_effect = [
                _proc(stdout=""),   # git add (skipped, no paths)
                _proc(stdout=""),   # git diff --cached --name-only (nothing staged)
            ]
            r = tool.run({"message": "msg", "confirmed": True})
        assert_fail(r, "NOTHING_TO_COMMIT")

    def test_successful_commit(self, tool):
        with patch("subprocess.run") as mock:
            mock.side_effect = [
                _proc(stdout=""),              # git diff --cached (staged files check)
                _proc(stdout="src/foo.py\n"),  # git diff --cached --name-only
                _proc(stdout=""),              # git commit
                _proc(stdout="abc1234\n"),     # git rev-parse HEAD
            ]
            # Simulate staging already done
            mock.side_effect = [
                _proc(stdout="src/foo.py\n"),  # diff --cached --name-only
                _proc(returncode=0),           # commit
                _proc(stdout="abc1234\n"),     # rev-parse
            ]
            r = tool.run({"message": "my commit", "confirmed": True})
        assert_ok(r)
        assert r.data["committed"] is True
        assert r.data["commit_hash"] == "abc1234"
        assert "src/foo.py" in r.data["files_committed"]

    def test_paths_triggers_git_add(self, tool):
        with patch("subprocess.run") as mock:
            mock.side_effect = [
                _proc(returncode=0),           # git add
                _proc(stdout="f.py\n"),        # diff --cached --name-only
                _proc(returncode=0),           # commit
                _proc(stdout="deadbeef\n"),    # rev-parse
            ]
            r = tool.run({"message": "msg", "confirmed": True, "paths": ["f.py"]})
        # First call should be git add
        first_cmd = mock.call_args_list[0].args[0]
        assert "add" in first_cmd

    def test_git_add_failure(self, tool):
        with patch("subprocess.run", return_value=_proc(returncode=1, stderr="error")):
            r = tool.run({"message": "msg", "confirmed": True, "paths": ["f.py"]})
        assert_fail(r, "GIT_ADD_FAILED")

    def test_signoff_flag_passed(self, tool):
        with patch("subprocess.run") as mock:
            mock.side_effect = [
                _proc(stdout="f.py\n"),
                _proc(returncode=0),
                _proc(stdout="abc\n"),
            ]
            tool.run({"message": "msg", "confirmed": True, "signoff": True})
        commit_call = mock.call_args_list[1].args[0]
        assert "--signoff" in commit_call

    def test_commit_message_in_result(self, tool):
        with patch("subprocess.run") as mock:
            mock.side_effect = [
                _proc(stdout="f.py\n"),
                _proc(returncode=0),
                _proc(stdout="abc1234\n"),
            ]
            r = tool.run({"message": "my message", "confirmed": True})
        assert r.data["message"] == "my message"
