"""Tests for Phase 6 tools: dependencies_read, symbols_index, state_get/state_set."""

from __future__ import annotations

import json
import time

import pytest

from coding_agent.tools.dependencies_read import DependenciesReadTool
from coding_agent.tools.state_store import StateGetTool, StateSetTool
from coding_agent.tools.symbols_index import SymbolsIndexTool

from conftest import assert_fail, assert_ok, make_file


# ══════════════════════════════════════════════════════════════════════════════
# dependencies_read
# ══════════════════════════════════════════════════════════════════════════════

PYPROJECT_PEP517 = """\
[project]
name = "myapp"
dependencies = [
    "httpx>=0.24",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "ruff"]
"""

PYPROJECT_POETRY = """\
[tool.poetry]
name = "myapp"

[tool.poetry.dependencies]
python = "^3.10"
httpx = ">=0.24"

[tool.poetry.dev-dependencies]
pytest = ">=7.0"
"""

REQUIREMENTS_TXT = """\
# Runtime deps
httpx>=0.24
pydantic>=2.0
# with inline comment
requests==2.31.0  # pinned for stability

-r other-requirements.txt
--index-url https://pypi.org/simple
"""

PACKAGE_JSON = json.dumps({
    "name": "myapp",
    "dependencies": {"react": "^18.0.0", "axios": "^1.0.0"},
    "devDependencies": {"jest": "^29.0.0", "typescript": "^5.0.0"},
})


@pytest.fixture
def dep_tool(workspace):
    return DependenciesReadTool(str(workspace))


class TestDependenciesReadPyprojectPEP517:
    def test_ok(self, dep_tool, workspace):
        make_file(workspace, "pyproject.toml", PYPROJECT_PEP517)
        r = dep_tool.run({})
        assert_ok(r)

    def test_format_is_pyproject(self, dep_tool, workspace):
        make_file(workspace, "pyproject.toml", PYPROJECT_PEP517)
        r = dep_tool.run({})
        assert r.data["format"] == "pyproject.toml"

    def test_runtime_deps_parsed(self, dep_tool, workspace):
        make_file(workspace, "pyproject.toml", PYPROJECT_PEP517)
        r = dep_tool.run({})
        names = [d["name"] for d in r.data["dependencies"]]
        assert "httpx" in names
        assert "pydantic" in names

    def test_dev_deps_parsed(self, dep_tool, workspace):
        make_file(workspace, "pyproject.toml", PYPROJECT_PEP517)
        r = dep_tool.run({})
        names = [d["name"] for d in r.data["dev_dependencies"]]
        assert "pytest" in names

    def test_version_present(self, dep_tool, workspace):
        make_file(workspace, "pyproject.toml", PYPROJECT_PEP517)
        r = dep_tool.run({})
        dep = next(d for d in r.data["dependencies"] if d["name"] == "httpx")
        assert "0.24" in dep["version"]

    def test_dev_flag_true(self, dep_tool, workspace):
        make_file(workspace, "pyproject.toml", PYPROJECT_PEP517)
        r = dep_tool.run({})
        for d in r.data["dev_dependencies"]:
            assert d["dev"] is True

    def test_runtime_flag_false(self, dep_tool, workspace):
        make_file(workspace, "pyproject.toml", PYPROJECT_PEP517)
        r = dep_tool.run({})
        for d in r.data["dependencies"]:
            assert d["dev"] is False


class TestDependenciesReadRequirementsTxt:
    def test_ok(self, dep_tool, workspace):
        make_file(workspace, "requirements.txt", REQUIREMENTS_TXT)
        r = dep_tool.run({})
        assert_ok(r)

    def test_format(self, dep_tool, workspace):
        make_file(workspace, "requirements.txt", REQUIREMENTS_TXT)
        r = dep_tool.run({})
        assert r.data["format"] == "requirements.txt"

    def test_parses_packages(self, dep_tool, workspace):
        make_file(workspace, "requirements.txt", REQUIREMENTS_TXT)
        r = dep_tool.run({})
        names = [d["name"] for d in r.data["dependencies"]]
        assert "httpx" in names
        assert "pydantic" in names
        assert "requests" in names

    def test_skips_comments_and_flags(self, dep_tool, workspace):
        make_file(workspace, "requirements.txt", REQUIREMENTS_TXT)
        r = dep_tool.run({})
        names = [d["name"] for d in r.data["dependencies"]]
        # -r and --index-url should not appear as packages
        assert all(not n.startswith("-") for n in names)

    def test_inline_comment_stripped(self, dep_tool, workspace):
        make_file(workspace, "requirements.txt", REQUIREMENTS_TXT)
        r = dep_tool.run({})
        dep = next(d for d in r.data["dependencies"] if d["name"] == "requests")
        assert "#" not in dep["version"]


class TestDependenciesReadPackageJson:
    def test_ok(self, dep_tool, workspace):
        make_file(workspace, "package.json", PACKAGE_JSON)
        r = dep_tool.run({})
        assert_ok(r)

    def test_format(self, dep_tool, workspace):
        make_file(workspace, "package.json", PACKAGE_JSON)
        r = dep_tool.run({})
        assert r.data["format"] == "package.json"

    def test_runtime_deps(self, dep_tool, workspace):
        make_file(workspace, "package.json", PACKAGE_JSON)
        r = dep_tool.run({})
        names = [d["name"] for d in r.data["dependencies"]]
        assert "react" in names and "axios" in names

    def test_dev_deps(self, dep_tool, workspace):
        make_file(workspace, "package.json", PACKAGE_JSON)
        r = dep_tool.run({})
        names = [d["name"] for d in r.data["dev_dependencies"]]
        assert "jest" in names and "typescript" in names


class TestDependenciesReadEdgeCases:
    def test_no_file_returns_failure(self, dep_tool):
        r = dep_tool.run({})
        assert_fail(r, "NO_DEPENDENCY_FILE")

    def test_explicit_path_to_file(self, dep_tool, workspace):
        make_file(workspace, "requirements.txt", "requests==2.31.0\n")
        r = dep_tool.run({"path": str(workspace / "requirements.txt")})
        assert_ok(r)

    def test_total_count(self, dep_tool, workspace):
        make_file(workspace, "package.json", PACKAGE_JSON)
        r = dep_tool.run({})
        assert r.data["total_count"] == len(r.data["dependencies"]) + len(r.data["dev_dependencies"])


# ══════════════════════════════════════════════════════════════════════════════
# symbols_index
# ══════════════════════════════════════════════════════════════════════════════

PY_SOURCE = """\
class MyClass:
    def my_method(self):
        pass

def standalone_func():
    pass

async def async_handler():
    pass

MY_CONSTANT = 42
"""

TS_SOURCE = """\
export class AppService {
    constructor() {}
}

export function computeTotal(items: any[]) {
    return items.length;
}

const MAX_RETRIES = 3;
"""


@pytest.fixture
def sym_tool(workspace):
    return SymbolsIndexTool(str(workspace))


class TestSymbolsIndexPython:
    def test_finds_class(self, sym_tool, workspace):
        make_file(workspace, "src/app.py", PY_SOURCE)
        r = sym_tool.run({"query": "MyClass"})
        assert_ok(r)
        assert any(x["symbol"] == "MyClass" and x["kind"] == "class" for x in r.data["results"])

    def test_finds_function(self, sym_tool, workspace):
        make_file(workspace, "src/app.py", PY_SOURCE)
        r = sym_tool.run({"query": "standalone_func"})
        assert_ok(r)
        assert any(x["kind"] == "function" for x in r.data["results"])

    def test_finds_async_function(self, sym_tool, workspace):
        make_file(workspace, "src/app.py", PY_SOURCE)
        r = sym_tool.run({"query": "async_handler"})
        assert_ok(r)
        assert r.data["result_count"] >= 1

    def test_partial_match(self, sym_tool, workspace):
        make_file(workspace, "src/app.py", PY_SOURCE)
        r = sym_tool.run({"query": "My"})
        assert_ok(r)
        assert r.data["result_count"] >= 1

    def test_exact_match_excludes_partials(self, sym_tool, workspace):
        make_file(workspace, "src/app.py", PY_SOURCE)
        r = sym_tool.run({"query": "My", "exact": True})
        assert_ok(r)
        assert all(x["symbol"] == "My" for x in r.data["results"])

    def test_no_match_returns_empty(self, sym_tool, workspace):
        make_file(workspace, "src/app.py", PY_SOURCE)
        r = sym_tool.run({"query": "nonexistent_xyz_abc"})
        assert_ok(r)
        assert r.data["result_count"] == 0

    def test_line_number_present(self, sym_tool, workspace):
        make_file(workspace, "src/app.py", PY_SOURCE)
        r = sym_tool.run({"query": "MyClass"})
        result = next(x for x in r.data["results"] if x["symbol"] == "MyClass")
        assert isinstance(result["line"], int) and result["line"] > 0

    def test_confidence_in_range(self, sym_tool, workspace):
        make_file(workspace, "src/app.py", PY_SOURCE)
        r = sym_tool.run({"query": "MyClass"})
        for x in r.data["results"]:
            assert 0.0 <= x["confidence"] <= 1.0

    def test_file_path_uses_forward_slashes(self, sym_tool, workspace):
        make_file(workspace, "src/app.py", PY_SOURCE)
        r = sym_tool.run({"query": "MyClass"})
        for x in r.data["results"]:
            assert "\\" not in x["file"]

    def test_lang_python_filters(self, sym_tool, workspace):
        make_file(workspace, "app.py", PY_SOURCE)
        make_file(workspace, "app.ts", TS_SOURCE)
        r = sym_tool.run({"query": "App", "lang": "python"})
        for x in r.data["results"]:
            assert x["file"].endswith(".py")

    def test_result_fields_present(self, sym_tool, workspace):
        make_file(workspace, "app.py", PY_SOURCE)
        r = sym_tool.run({"query": "MyClass"})
        for x in r.data["results"]:
            for field in ("symbol", "file", "line", "kind", "confidence"):
                assert field in x, f"Missing field: {field}"

    def test_max_results_respected(self, sym_tool, workspace):
        make_file(workspace, "app.py", PY_SOURCE)
        r = sym_tool.run({"query": "my", "max_results": 1})
        assert r.data["result_count"] <= 1

    def test_empty_query_returns_failure(self, sym_tool, workspace):
        r = sym_tool.run({"query": ""})
        assert_fail(r, "EMPTY_QUERY")


class TestSymbolsIndexTypeScript:
    def test_finds_ts_class(self, sym_tool, workspace):
        make_file(workspace, "src/app.ts", TS_SOURCE)
        r = sym_tool.run({"query": "AppService"})
        assert_ok(r)
        assert any(x["symbol"] == "AppService" for x in r.data["results"])

    def test_finds_ts_function(self, sym_tool, workspace):
        make_file(workspace, "src/app.ts", TS_SOURCE)
        r = sym_tool.run({"query": "computeTotal"})
        assert_ok(r)
        assert r.data["result_count"] >= 1

    def test_lang_typescript_filters(self, sym_tool, workspace):
        make_file(workspace, "app.py", PY_SOURCE)
        make_file(workspace, "app.ts", TS_SOURCE)
        r = sym_tool.run({"query": "App", "lang": "typescript"})
        for x in r.data["results"]:
            assert not x["file"].endswith(".py")


# ══════════════════════════════════════════════════════════════════════════════
# state_get / state_set
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def state_pair(workspace):
    store: dict = {}
    setter = StateSetTool(str(workspace), _store=store)
    getter = StateGetTool(str(workspace), _store=store)
    return setter, getter


class TestStateSet:
    def test_set_returns_ok(self, state_pair):
        setter, _ = state_pair
        r = setter.run({"key": "foo", "value": 42})
        assert_ok(r)

    def test_set_stores_string(self, state_pair):
        setter, getter = state_pair
        setter.run({"key": "msg", "value": "hello"})
        r = getter.run({"key": "msg"})
        assert r.data["value"] == "hello"

    def test_set_stores_dict(self, state_pair):
        setter, getter = state_pair
        setter.run({"key": "obj", "value": {"x": 1, "y": 2}})
        r = getter.run({"key": "obj"})
        assert r.data["value"] == {"x": 1, "y": 2}

    def test_set_stores_list(self, state_pair):
        setter, getter = state_pair
        setter.run({"key": "items", "value": [1, 2, 3]})
        r = getter.run({"key": "items"})
        assert r.data["value"] == [1, 2, 3]

    def test_set_overwrites(self, state_pair):
        setter, getter = state_pair
        setter.run({"key": "k", "value": "first"})
        setter.run({"key": "k", "value": "second"})
        r = getter.run({"key": "k"})
        assert r.data["value"] == "second"

    def test_stored_flag_true(self, state_pair):
        setter, _ = state_pair
        r = setter.run({"key": "x", "value": 1})
        assert r.data["stored"] is True


class TestStateGet:
    def test_found_true_when_key_exists(self, state_pair):
        setter, getter = state_pair
        setter.run({"key": "present", "value": True})
        r = getter.run({"key": "present"})
        assert_ok(r)
        assert r.data["found"] is True

    def test_found_false_when_key_missing(self, state_pair):
        _, getter = state_pair
        r = getter.run({"key": "absent"})
        assert_ok(r)           # NOT a failure — missing key is not an error
        assert r.data["found"] is False
        assert r.data["value"] is None

    def test_value_returned_correctly(self, state_pair):
        setter, getter = state_pair
        setter.run({"key": "num", "value": 99})
        r = getter.run({"key": "num"})
        assert r.data["value"] == 99

    def test_key_in_response(self, state_pair):
        _, getter = state_pair
        r = getter.run({"key": "anything"})
        assert r.data["key"] == "anything"

    def test_missing_key_is_not_error(self, state_pair):
        _, getter = state_pair
        r = getter.run({"key": "nope"})
        assert r.ok  # ok=True even for missing keys


class TestStateIsolation:
    def test_different_stores_are_isolated(self, workspace):
        """Two independent build_tools() calls must not share state."""
        store_a: dict = {}
        store_b: dict = {}
        setter_a = StateSetTool(str(workspace), _store=store_a)
        getter_b = StateGetTool(str(workspace), _store=store_b)

        setter_a.run({"key": "secret", "value": "session_a_only"})
        r = getter_b.run({"key": "secret"})
        assert r.data["found"] is False

    def test_multiple_keys_independent(self, state_pair):
        setter, getter = state_pair
        setter.run({"key": "a", "value": 1})
        setter.run({"key": "b", "value": 2})
        assert getter.run({"key": "a"}).data["value"] == 1
        assert getter.run({"key": "b"}).data["value"] == 2
