"""Shared pytest fixtures and helpers for coding_agent tool tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from coding_agent.core.tool_guard import ToolGuard
from coding_agent.core.tool_result import ToolResult


@pytest.fixture
def workspace(tmp_path):
    """A temporary directory that acts as the workspace root."""
    return tmp_path


@pytest.fixture
def guard(workspace):
    return ToolGuard(workspace_root=str(workspace), policy={})


# ── Plain helper functions ─────────────────────────────────────────────────
# Each test file imports these directly:
#   from conftest import assert_ok, assert_fail, make_file

def make_file(workspace: Path, relative_path: str, content: str = "hello\n") -> Path:
    p = workspace / relative_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def assert_ok(result: ToolResult) -> None:
    assert result.ok, f"Expected ok=True but got error: {result.error_code} — {result.message}"


def assert_fail(result: ToolResult, error_code: str | None = None) -> None:
    assert not result.ok, f"Expected ok=False but result succeeded: {result.message}"
    if error_code:
        assert result.error_code == error_code, (
            f"Expected error_code={error_code!r}, got {result.error_code!r}"
        )
