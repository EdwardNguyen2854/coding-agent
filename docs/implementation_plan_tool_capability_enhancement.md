# Implementation Plan: Tool Capability Enhancement

> **For Claude Code:** Execute this plan phase by phase. Do not start the next phase until all gate criteria for the current phase are satisfied. Run the verification steps explicitly and report results before proceeding.

---

## How to Execute This Plan

1. Read the entire plan before starting
2. Work through phases in order: 0 → 1 → 2 → 3 → 4 → 5 → 6
3. At the end of each phase, run the **Verification Steps**
4. Check off every **Phase Gate** item — if any fail, fix and re-verify before advancing
5. Do not skip or reorder phases

---

## Phase 0 — Baseline Prep

**Goal:** Standardize ToolResult schema and create the central safety guard layer before any new tools are built.

### Tasks

#### 0.1 — Create `tool_result.py`

Create a shared ToolResult dataclass/builder with these fields on every response:

```python
@dataclass
class ToolResult:
    ok: bool
    error_code: str | None
    message: str
    data: dict
    warnings: list[str]
    artifacts: list[dict]  # [{type, path, description}]
```

- Add a factory method `ToolResult.success(data, message, warnings=[])` 
- Add a factory method `ToolResult.failure(error_code, message, warnings=[])`
- All existing tools must be updated to return this schema

#### 0.2 — Create `tool_guard.py`

Create a middleware class `ToolGuard` that wraps every tool call:

```python
class ToolGuard:
    def __init__(self, workspace_root: str, policy: dict): ...
    def check(self, tool_name: str, args: dict) -> ToolResult | None:
        # Returns None if allowed, ToolResult(ok=False) if blocked
        ...
```

Responsibilities:
- Validate argument types and required fields against tool schema
- Enforce workspace sandbox — reject any path resolving outside `workspace_root`
- Apply configurable allow/deny rules from `policy` dict
- Log every tool call to append-only log file for replay/debug

#### 0.3 — Update Existing Tools

Wrap all existing tool handlers to:
1. Call `ToolGuard.check()` first — return its result immediately if blocked
2. Return `ToolResult` envelope instead of raw dict/string

#### 0.4 — Write Tests

Create `tests/test_tool_guard.py`:
- `test_valid_call_passes` — normal args, normal path
- `test_invalid_args_blocked` — missing required field
- `test_path_traversal_blocked` — path like `../../etc/passwd`
- `test_deny_listed_action_blocked` — action on deny list

Create `tests/test_tool_result.py`:
- `test_success_factory`
- `test_failure_factory`
- `test_all_fields_present`

### Verification Steps

```bash
# Run all tests
pytest tests/test_tool_guard.py tests/test_tool_result.py -v

# Manually verify path traversal is blocked
python -c "
from tool_guard import ToolGuard
guard = ToolGuard(workspace_root='/workspace', policy={})
result = guard.check('file_read', {'path': '/workspace/../../etc/passwd'})
assert result is not None and not result.ok, 'Path traversal must be blocked'
print('PASS: path traversal blocked')
"
```

### Phase Gate — Must pass before Phase 1

- [ ] All existing tools return `ToolResult` schema
- [ ] `ToolGuard` blocks paths outside workspace root
- [ ] `ToolGuard` blocks deny-listed actions
- [ ] Unit tests pass: valid call, invalid args, path traversal, denied action
- [ ] `ToolResult` builder is the only place tools construct responses (no raw dicts)

---

## Phase 1 — File System Upgrades

**Goal:** Implement the four file system tools. Do `file_patch` first — it is the highest-priority tool in this entire plan.

> **Note to Claude Code:** Implement tools in the order listed below. Do not move on to `file_list` until `file_patch` is tested and passing.

### Tasks

#### 1.1 — `file_patch` (implement first)

**Do not write a custom hunk applicator.** Use an existing library:
- Python: `pip install whatthepatch` or use stdlib `difflib`
- Fallback: shell out to `patch` binary if available

Accept two input modes:

```python
# Mode A: unified diff string
{
  "diff_text": "--- a/foo.py\n+++ b/foo.py\n@@..."
}

# Mode B: structured patch
{
  "patches": [
    {
      "path": "src/foo.py",
      "hunks": [
        {"start": 10, "end": 14, "replace_with": "new content here\n"}
      ]
    }
  ]
}
```

Output:

```python
ToolResult(ok=True, data={
    "applied": True,
    "files_changed": ["src/foo.py"],
    "rejected_hunks": []  # list if any hunks failed
})
```

Additional requirements:
- Optional `file_hash` arg — reject if file has changed since hash was computed
- Conflict detection — populate `rejected_hunks`, do not silently drop failures
- Create `docs/patch_vs_write.md` explaining when to use `file_patch` vs direct file write

#### 1.2 — `file_list`

```python
# Args
{
  "path": str,           # required
  "depth": int,          # default 2
  "include_hidden": bool, # default False
  "include_files": bool,  # default True
  "include_dirs": bool    # default True
}

# Output data
{
  "tree": {
    "name": "src",
    "type": "dir",
    "children": [
      {"name": "main.py", "type": "file", "size": 1240},
      ...
    ]
  }
}
```

#### 1.3 — `file_move`

```python
# Args
{
  "src": str,           # required
  "dst": str,           # required
  "overwrite": bool     # default False
}

# Output data
{
  "moved_from": str,
  "moved_to": str,
  "dirs_created": [str]  # intermediate dirs that were created
}
```

Guard: reject move if `dst` resolves outside workspace root.

#### 1.4 — `file_delete`

```python
# Args
{
  "path": str,          # required
  "recursive": bool     # default False — REQUIRED True for directories
}

# Output data
{
  "deleted": str,
  "was_directory": bool
}
```

Guard: return `ToolResult.failure("RECURSIVE_REQUIRED", ...)` if path is a directory and `recursive=False`.

### Verification Steps

```bash
# Unit tests
pytest tests/test_file_patch.py tests/test_file_list.py \
       tests/test_file_move.py tests/test_file_delete.py -v

# Integration scenario — run this exact sequence
python tests/integration/test_phase1_scenario.py
```

`test_phase1_scenario.py` must cover:
1. Create a temp file with known content
2. Apply a patch using `file_patch` (unified diff mode)
3. Apply another patch using structured hunk mode
4. Verify rejected_hunks is populated when a hunk conflicts
5. Use `file_list` to confirm file exists in tree
6. Use `file_move` to relocate the file
7. Use `file_delete` to remove it
8. Verify `file_delete` on a directory without `recursive=True` returns failure

### Phase Gate — Must pass before Phase 2

- [ ] `file_patch` applies unified diffs correctly
- [ ] `file_patch` applies structured patch hunks correctly
- [ ] `file_patch` populates `rejected_hunks` on conflict — no silent failures
- [ ] `file_list` returns structured tree (not flat list)
- [ ] `file_move` enforces workspace boundary via ToolGuard
- [ ] `file_delete` requires `recursive=True` for directories
- [ ] All four tools return `ToolResult` envelope
- [ ] `docs/patch_vs_write.md` exists in repo

---

## Phase 2 — Workspace Introspection

**Goal:** Implement `workspace_info` so later tools can detect runtimes and available CLI tools without shelling out repeatedly.

### Tasks

#### 2.1 — `workspace_info`

```python
# No required args

# Output data
{
  "workspace_root": str,
  "os": str,              # "linux" | "macos" | "windows"
  "platform": str,        # full platform string
  "runtimes": {
    "python": {"available": True, "version": "3.11.4", "path": "/usr/bin/python3"},
    "node":   {"available": True, "version": "20.5.0", "path": "/usr/bin/node"},
    "java":   {"available": False},
    "go":     {"available": False}
  },
  "git_present": True,
  "git_repo_root": "/workspace",
  "tools": {
    "git":    {"available": True},
    "pytest": {"available": True},
    "npm":    {"available": True},
    "ruff":   {"available": True},
    "eslint": {"available": False},
    "mypy":   {"available": True},
    "pyright":{"available": False}
  }
}
```

Caching requirement:
- Cache result in memory after first call
- Add `refresh: bool` arg (default `False`) to force re-probe
- Do not shell out again on subsequent calls unless `refresh=True`

### Verification Steps

```bash
pytest tests/test_workspace_info.py -v

# Verify caching — second call must not spawn subprocesses
python -c "
from unittest.mock import patch
from workspace_info import WorkspaceInfoTool
tool = WorkspaceInfoTool()
tool.run({})  # first call
with patch('subprocess.run') as mock_sub:
    tool.run({})  # second call — must not call subprocess
    assert mock_sub.call_count == 0, 'Caching failed: subprocess called on second invocation'
    print('PASS: caching works')
"
```

### Phase Gate — Must pass before Phase 3

- [ ] `workspace_info` returns correct runtime versions for installed tools
- [ ] Absent tools return `{"available": False}`, not an error
- [ ] Second call does not re-probe (subprocess not called)
- [ ] `refresh=True` forces re-probe
- [ ] Output is fully structured — no raw shell text

---

## Phase 3 — Git Wrappers

**Goal:** Expose git operations as structured JSON tools. Raw git text output is expensive to parse and varies across git versions.

### Tasks

#### 3.1 — `git_status`

```python
# No required args

# Output data
{
  "branch": "main",
  "upstream": "origin/main",
  "ahead": 0,
  "behind": 0,
  "staged": ["src/foo.py"],
  "unstaged": ["src/bar.py"],
  "untracked": ["scratch.txt"],
  "repo_root": "/workspace"
}
```

#### 3.2 — `git_diff`

```python
# Args
{
  "staged": bool,          # default False
  "pathspec": [str],       # optional — filter to specific files
  "base_ref": str,         # optional — e.g. "main"
  "target_ref": str        # optional — e.g. "HEAD"
}

# Output data
{
  "diff_text": str,        # full unified diff
  "files_changed": [
    {
      "path": str,
      "additions": int,
      "deletions": int,
      "diff": str          # per-file diff chunk
    }
  ]
}
```

#### 3.3 — `git_commit`

```python
# Args
{
  "message": str,          # required
  "paths": [str],          # optional — files to auto-stage before commit
  "signoff": bool,         # default False
  "confirmed": bool        # MUST be True — see warning below
}
```

> **Warning:** `confirmed=True` is a soft gate only — it signals intent but does not substitute for real human review. If your agent framework supports a human-approval step or one-time confirmation token, implement that instead. The `confirmed` flag alone must not be treated as sufficient authorization for destructive or irreversible operations.

Guard rules:
- Block if `confirmed` is not `True` — return `ToolResult.failure("CONFIRMATION_REQUIRED", ...)`
- Block if nothing is staged and `paths` is empty — return `ToolResult.failure("NOTHING_TO_COMMIT", ...)`
- If `paths` is provided, auto-stage those files before committing

```python
# Output data
{
  "committed": True,
  "commit_hash": "abc1234",
  "files_committed": [str],
  "message": str
}
```

### Verification Steps

```bash
# Requires a git repo fixture — create one in tests/fixtures/sample_repo/
pytest tests/test_git_status.py tests/test_git_diff.py tests/test_git_commit.py -v

# Verify commit is blocked without confirmation
python -c "
from git_commit import GitCommitTool
tool = GitCommitTool(workspace_root='/workspace')
result = tool.run({'message': 'test', 'confirmed': False})
assert not result.ok and result.error_code == 'CONFIRMATION_REQUIRED'
print('PASS: commit blocked without confirmation')
"
```

### Phase Gate — Must pass before Phase 4

- [ ] `git_status` returns correct arrays for staged, unstaged, and untracked files
- [ ] `git_diff` works for staged, unstaged, and ref-to-ref comparisons
- [ ] `git_commit` is blocked when `confirmed` is not `True`
- [ ] `git_commit` is blocked when nothing staged and no `paths` provided
- [ ] All three tools tested against `tests/fixtures/sample_repo/` fixture
- [ ] No tool returns raw git text as primary output

---

## Phase 4 — Structured Quality Loop

**Goal:** Replace raw shell output from tests, lint, and typecheck with structured JSON that models can act on directly.

> **Note to Claude Code:** Add a max-iterations guard in the agent scaffolding before deploying `run_tests`. A model in a failing loop will call `run_tests` indefinitely without it.

### Tasks

#### 4.1 — `run_tests`

```python
# Args
{
  "command": str,         # optional — auto-detected via workspace_info if omitted
  "focus": [str],         # optional — specific test files or test names
  "timeout_sec": int      # default 60
}

# Output data
{
  "passed": bool,
  "total": int,
  "passed_count": int,
  "failed_count": int,
  "summary": str,
  "failures": [
    {
      "file": str,
      "test": str,
      "reason": str,
      "snippet": str      # relevant lines from output
    }
  ],
  "raw_output": str       # always include for debugging
}
```

Auto-detection logic (use `workspace_info`):
- Python + pytest available → `pytest`
- Node + package.json with test script → `npm test`
- Otherwise → return `ToolResult.failure("COMMAND_REQUIRED", "Could not auto-detect test runner")`

#### 4.2 — `run_lint`

```python
# Args
{
  "command": str,         # optional — auto-detected if omitted
  "paths": [str]          # optional — limit to specific files
}

# Output data
{
  "clean": bool,
  "issue_count": int,
  "issues": [
    {
      "file": str,
      "line": int,
      "col": int,
      "rule": str,
      "message": str,
      "severity": str     # "error" | "warning"
    }
  ],
  "raw_output": str,
  "parser_used": str      # e.g. "ruff" | "eslint" | "fallback"
}
```

Required parsers: `ruff`, `eslint`. Fallback mode: if parser fails, return `raw_output` + best-effort extraction with `"parser_used": "fallback"`.

#### 4.3 — `typecheck`

Same issue schema as `run_lint`. Required parsers: `mypy`, `pyright`, `tsc`.

```python
# Output data
{
  "clean": bool,
  "issue_count": int,
  "issues": [
    {
      "file": str,
      "line": int,
      "col": int,
      "rule": str,
      "message": str,
      "severity": str
    }
  ],
  "raw_output": str,
  "parser_used": str
}
```

### Verification Steps

```bash
pytest tests/test_run_tests.py tests/test_run_lint.py tests/test_typecheck.py -v

# Quality loop integration scenario
python tests/integration/test_phase4_quality_loop.py
```

`test_phase4_quality_loop.py` must:
1. Introduce a known lint error into a temp file
2. Run `run_lint` — verify structured issue is returned
3. Apply `file_patch` to fix the error
4. Run `run_lint` again — verify `clean: True`
5. Repeat with a type error and `typecheck`

### Phase Gate — Must pass before Phase 5

- [ ] `run_tests` returns structured `failures` array, not raw log text
- [ ] `run_lint` parses `ruff` output into structured issues
- [ ] `run_lint` parses `eslint` output into structured issues
- [ ] `typecheck` parses `mypy` or `pyright` output into structured issues
- [ ] Fallback mode returns `raw_output` + best-effort when parser fails
- [ ] Quality loop integration scenario passes end to end
- [ ] Max-iterations guard documented or implemented in agent scaffolding

---

## Phase 5 — Safe Shell

**Goal:** Introduce `safe_shell` as the default shell tool. Keep raw `shell` available — do not remove it.

### Tasks

#### 5.1 — `safe_shell`

```python
# Args
{
  "command": str,          # required
  "cwd": str               # optional — default workspace root
}

# Output data (allowed)
{
  "blocked": False,
  "stdout": str,
  "stderr": str,
  "exit_code": int
}

# Output data (blocked)
{
  "blocked": True,
  "reason": str,
  "matched_pattern": str,
  "suggested_safe_alternative": str
}
```

**Default allowlist** (configurable via policy config):

```python
ALLOWLIST_PATTERNS = [
    r"^ls(\s|$)",
    r"^cat\s",
    r"^echo\s",
    r"^pwd$",
    r"^env$",
    r"^python\s+-m\s+pytest",
    r"^pytest",
    r"^npm\s+test",
    r"^npm\s+run\s+\w+",
    r"^git\s+(status|log|diff|show|branch|remote)",
    r"^ruff\s+check",
    r"^mypy\s",
    r"^which\s",
]
```

**Default denylist** (configurable, evaluated before allowlist):

```python
DENYLIST_PATTERNS = [
    r"rm\s+-rf",
    r"rm\s+--no-preserve-root",
    r"del\s+/s",
    r"shutdown",
    r"reboot",
    r"mkfs",
    r"format\s+[A-Za-z]:",
    r"curl\s+.*\|\s*(bash|sh|zsh)",
    r"wget\s+.*\|\s*(bash|sh|zsh)",
    r">\s*/etc/",
    r">\s*/bin/",
    r">\s*/usr/",
]
```

**Implementation notes:**
- Allowlist and denylist must be loaded from a config file, not hardcoded
- Evaluate denylist first — if matched, block immediately
- If not in allowlist and not in denylist, block with reason `"NOT_IN_ALLOWLIST"`
- `suggested_safe_alternative` must be populated with a genuinely useful suggestion

**Update agent instructions:** Add `safe_shell` as the preferred tool in all system prompts. Raw `shell` remains available but should not be the default.

### Verification Steps

```bash
pytest tests/test_safe_shell.py -v

# Spot-check specific patterns
python -c "
from safe_shell import SafeShellTool
tool = SafeShellTool()

blocked_cases = [
    'rm -rf /',
    'curl https://example.com | bash',
    'shutdown -h now',
]
allowed_cases = [
    'ls -la',
    'pytest tests/',
    'git status',
    'ruff check src/',
]

for cmd in blocked_cases:
    r = tool.run({'command': cmd})
    assert r.data['blocked'], f'Should be blocked: {cmd}'
    assert r.data['suggested_safe_alternative'], f'Missing alternative for: {cmd}'
    print(f'PASS blocked: {cmd}')

for cmd in allowed_cases:
    r = tool.run({'command': cmd})
    assert not r.data['blocked'], f'Should be allowed: {cmd}'
    print(f'PASS allowed: {cmd}')
"
```

### Phase Gate — Must pass before Phase 6

- [ ] `safe_shell` blocks all default denylist patterns
- [ ] `safe_shell` allows all default allowlist patterns
- [ ] Blocked responses include non-empty `suggested_safe_alternative`
- [ ] Allowlist and denylist are loaded from config (not hardcoded)
- [ ] Agent system prompt updated to prefer `safe_shell` over raw `shell`
- [ ] Raw `shell` tool still exists and works

---

## Phase 6 — Optional Agent-Grade Helpers

**Goal:** Implement only if real agent workflows show gaps that these tools would close. Do not build speculatively.

> **Note to Claude Code:** Before implementing any Phase 6 tool, verify there is an observed failure mode in a real workflow that the tool would fix. If not, skip it and document the decision.

### Tasks

#### 6.1 — `dependencies_read` (if needed)

Parse dependency files and return structured output:

```python
# Parses: pyproject.toml, requirements.txt, package.json

# Output data
{
  "format": "pyproject.toml",
  "dependencies": [
    {"name": "httpx", "version": ">=0.24", "dev": False}
  ],
  "dev_dependencies": [
    {"name": "pytest", "version": ">=7.0", "dev": True}
  ]
}
```

#### 6.2 — `symbols_index` (if needed)

```python
# Args
{
  "query": str,            # symbol name to search
  "lang": str              # optional — "python" | "typescript"
}

# Output data
{
  "results": [
    {
      "symbol": str,
      "file": str,
      "line": int,
      "kind": str,         # "function" | "class" | "variable"
      "confidence": float  # 0.0 to 1.0
    }
  ]
}
```

Implementation: ripgrep for fast full-repo search + simple AST traversal for Python/TypeScript. Must return results within 2 seconds on a 100k-line repo.

#### 6.3 — `state_get` / `state_set` (if needed)

> **Warning:** State in a tool creates subtle bugs when conversations are replayed or forked. Prefer scaffolding-level state if your framework supports it. Only implement these if scaffolding-level state is unavailable.

```python
# state_set args
{"key": str, "value": any}  # value must be JSON-serializable

# state_get args
{"key": str}

# state_get output data
{"key": str, "value": any, "found": bool}  # found=False (not error) if key missing
```

State must be scoped per session. Different sessions must not share state.

### Phase Gate

- [ ] Each Phase 6 tool built only if an observed failure mode justifies it
- [ ] `symbols_index` returns results within 2 seconds on 100k-line repo (if built)
- [ ] `state_get` returns `found: False` for missing keys, not an error (if built)
- [ ] Session isolation verified for state tools (if built)

---

## Final Acceptance

Run both scenarios against the live agent before closing this plan.

### Scenario A — Full Refactor Workflow

The agent must complete this sequence without human intervention after the initial prompt:

1. Use `file_list` to navigate repo and identify target file
2. Use `file_patch` to rename a symbol and update its references
3. Use `run_tests` to verify nothing broke
4. Use `git_diff` to review changes
5. Use `git_commit` with `confirmed: true` to finalize

### Scenario B — Quality Loop

The agent must complete this sequence without human intervention:

1. Use `run_lint` to identify issues in a file with known errors
2. Use `file_patch` to fix each structured issue
3. Use `run_lint` again to verify `clean: true`
4. Repeat with `typecheck` if applicable

### Final Gate

- [ ] Scenario A completes without agent getting stuck or falling back to raw shell unnecessarily
- [ ] Scenario B produces clean lint output after patching
- [ ] No tool returns unstructured raw text as its primary output field
- [ ] ToolGuard blocks are observable in the log file
- [ ] `safe_shell` is the default in agent instructions, not raw `shell`

---

*Implementation plan for tool capability enhancement — phase-gated edition. Advance only after each gate is fully satisfied.*
