"""Tests for file_patch — unified diff and structured hunk modes."""

from __future__ import annotations

import hashlib

import pytest

from coding_agent.tools.file_patch import FilePatchTool

from conftest import assert_fail, assert_ok, make_file

ORIGINAL = "line1\nline2\nline3\nline4\nline5\n"

UNIFIED_DIFF = """\
--- a/target.txt
+++ b/target.txt
@@ -2,2 +2,2 @@
-line2
-line3
+LINE_TWO
+LINE_THREE
"""


@pytest.fixture
def tool(workspace):
    return FilePatchTool(str(workspace))


# ── Unified diff mode ──────────────────────────────────────────────────────

class TestUnifiedDiff:
    def test_applies_diff(self, tool, workspace):
        make_file(workspace, "target.txt", ORIGINAL)
        r = tool.run({"diff_text": UNIFIED_DIFF})
        assert_ok(r)
        assert "target.txt" in r.data["files_changed"]

    def test_file_content_updated(self, tool, workspace):
        make_file(workspace, "target.txt", ORIGINAL)
        tool.run({"diff_text": UNIFIED_DIFF})
        content = (workspace / "target.txt").read_text()
        assert "LINE_TWO" in content
        assert "line2" not in content

    def test_applied_true(self, tool, workspace):
        make_file(workspace, "target.txt", ORIGINAL)
        r = tool.run({"diff_text": UNIFIED_DIFF})
        assert r.data["applied"] is True

    def test_rejected_hunks_empty_on_success(self, tool, workspace):
        make_file(workspace, "target.txt", ORIGINAL)
        r = tool.run({"diff_text": UNIFIED_DIFF})
        assert r.data["rejected_hunks"] == []

    def test_missing_both_inputs(self, tool):
        r = tool.run({})
        assert_fail(r, "MISSING_INPUT")

    def test_both_inputs_rejected(self, tool, workspace):
        make_file(workspace, "target.txt", ORIGINAL)
        r = tool.run({"diff_text": UNIFIED_DIFF, "patches": []})
        assert_fail(r, "AMBIGUOUS_INPUT")


# ── Structured hunk mode ───────────────────────────────────────────────────

class TestStructuredHunks:
    def test_applies_hunk(self, tool, workspace):
        make_file(workspace, "src/foo.py", "a\nb\nc\nd\n")
        r = tool.run({
            "patches": [{
                "path": "src/foo.py",
                "hunks": [{"start": 2, "end": 3, "replace_with": "B\nC\n"}],
            }]
        })
        assert_ok(r)
        assert (workspace / "src" / "foo.py").read_text() == "a\nB\nC\nd\n"

    def test_files_changed_populated(self, tool, workspace):
        make_file(workspace, "src/foo.py", "a\nb\n")
        r = tool.run({
            "patches": [{"path": "src/foo.py", "hunks": [{"start": 1, "end": 1, "replace_with": "A\n"}]}]
        })
        assert "src/foo.py" in r.data["files_changed"]

    def test_multiple_hunks_applied_in_reverse(self, tool, workspace):
        # Two non-overlapping hunks; applying in reverse keeps line numbers valid
        make_file(workspace, "f.py", "a\nb\nc\nd\n")
        r = tool.run({
            "patches": [{
                "path": "f.py",
                "hunks": [
                    {"start": 1, "end": 1, "replace_with": "A\n"},
                    {"start": 3, "end": 3, "replace_with": "C\n"},
                ],
            }]
        })
        assert_ok(r)
        assert (workspace / "f.py").read_text() == "A\nb\nC\nd\n"

    def test_out_of_bounds_hunk_rejected(self, tool, workspace):
        make_file(workspace, "f.py", "a\nb\n")
        r = tool.run({
            "patches": [{"path": "f.py", "hunks": [{"start": 10, "end": 20, "replace_with": "x\n"}]}]
        })
        assert_ok(r)  # overall ok=True (partial success is still returned)
        assert len(r.data["rejected_hunks"]) == 1

    def test_file_not_found_rejected(self, tool):
        r = tool.run({
            "patches": [{"path": "ghost.py", "hunks": [{"start": 1, "end": 1, "replace_with": "x\n"}]}]
        })
        assert_ok(r)
        assert len(r.data["rejected_hunks"]) == 1

    def test_missing_path_in_patch_rejected(self, tool):
        r = tool.run({"patches": [{"hunks": [{"start": 1, "end": 1, "replace_with": "x\n"}]}]})
        assert r.data["rejected_hunks"]

    def test_warning_emitted_on_rejected_hunk(self, tool, workspace):
        make_file(workspace, "f.py", "a\n")
        r = tool.run({
            "patches": [{"path": "f.py", "hunks": [{"start": 99, "end": 99, "replace_with": "x\n"}]}]
        })
        assert len(r.warnings) > 0


# ── file_hash guard ────────────────────────────────────────────────────────

class TestFileHash:
    def test_correct_hash_allows_patch(self, tool, workspace):
        p = make_file(workspace, "f.py", "a\nb\n")
        correct_hash = hashlib.sha256(p.read_bytes()).hexdigest()
        r = tool.run({
            "patches": [{"path": "f.py", "hunks": [{"start": 1, "end": 1, "replace_with": "A\n"}]}],
            "file_hash": correct_hash,
        })
        assert_ok(r)

    def test_wrong_hash_blocks_patch(self, tool, workspace):
        make_file(workspace, "f.py", "a\nb\n")
        r = tool.run({
            "patches": [{"path": "f.py", "hunks": [{"start": 1, "end": 1, "replace_with": "A\n"}]}],
            "file_hash": "0" * 64,
        })
        assert_fail(r, "HASH_MISMATCH")
