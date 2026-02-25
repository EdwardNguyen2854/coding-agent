# Coding Agent Tools

This document lists all built-in tools. Every tool uses a common `ToolResult` envelope and passes through `ToolGuard` before execution.

## Tool Result Schema

Every tool returns:

```python
ToolResult(
    ok: bool,
    error_code: str | None,   # set when ok=False
    message: str,             # human-readable summary
    data: dict,               # structured output (see per-tool docs below)
    warnings: list[str],      # non-fatal notices
    artifacts: list[dict],    # [{type, path, description}]
)
```

---

## File System

### `file_read`
Read file contents with optional line range control.

| Arg | Type | Required | Default |
|-----|------|----------|---------|
| `path` | string | ✅ | — |
| `offset` | integer | | 0 |
| `limit` | integer | | (whole file) |

**Returns:** `{ path, content, total_lines, returned_lines, offset }`

---

### `file_write`
Create or overwrite a file. Intermediate directories are created automatically.

| Arg | Type | Required | Default |
|-----|------|----------|---------|
| `path` | string | ✅ | — |
| `content` | string | ✅ | — |
| `overwrite` | boolean | | `true` |

**Returns:** `{ path, bytes_written, created, overwritten }`

---

### `file_edit`
Replace an exact substring in a file. The match must occur exactly once.

| Arg | Type | Required |
|-----|------|----------|
| `path` | string | ✅ |
| `old_str` | string | ✅ |
| `new_str` | string | ✅ |

**Returns:** `{ path, old_lines, new_lines, net_line_change }`

**Error codes:** `MATCH_NOT_FOUND`, `AMBIGUOUS_MATCH`

---

### `file_patch` ⭐ preferred for edits
Apply a unified diff or structured hunks to one or more files. See `docs/agent/PATCH-VS-WRITE.md`.

| Arg | Type | Notes |
|-----|------|-------|
| `diff_text` | string | Unified diff. Mutually exclusive with `patches`. |
| `patches` | array | Structured `[{path, hunks: [{start, end, replace_with}]}]`. |
| `file_hash` | string | Optional SHA-256 guard — rejects if file changed. |

**Returns:** `{ applied, files_changed, rejected_hunks }`

---

### `file_list`
Return a directory tree as structured JSON.

| Arg | Type | Default |
|-----|------|---------|
| `path` | string | workspace root |
| `depth` | integer | 2 |
| `include_hidden` | boolean | `false` |
| `include_files` | boolean | `true` |
| `include_dirs` | boolean | `true` |

**Returns:** `{ tree: { name, type, path, children?, size? } }`

---

### `file_move`
Move or rename a file or directory within the workspace.

| Arg | Type | Required | Default |
|-----|------|----------|---------|
| `src` | string | ✅ | — |
| `dst` | string | ✅ | — |
| `overwrite` | boolean | | `false` |

**Returns:** `{ moved_from, moved_to, dirs_created }`

---

### `file_delete`
Delete a file or directory. Directories require `recursive=true`.

| Arg | Type | Required | Default |
|-----|------|----------|---------|
| `path` | string | ✅ | — |
| `recursive` | boolean | | `false` |

**Returns:** `{ deleted, was_directory }`

**Error codes:** `RECURSIVE_REQUIRED` (directory without `recursive=true`)

---

## Search

### `glob`
Find files matching a glob pattern.

| Arg | Type | Default |
|-----|------|---------|
| `pattern` | string ✅ | — |
| `base_path` | string | workspace root |
| `include_hidden` | boolean | `false` |
| `max_results` | integer | 500 |

**Returns:** `{ pattern, base_path, matches, count, truncated }`

---

### `grep`
Search file contents with regex. Uses ripgrep when available, falls back to Python.

| Arg | Type | Default |
|-----|------|---------|
| `pattern` | string ✅ | — |
| `path` | string | workspace root |
| `glob` | string | (all files) |
| `case_sensitive` | boolean | `true` |
| `max_results` | integer | 200 |
| `context_lines` | integer | 0 |

**Returns:** `{ pattern, matches, match_count, files_matched, parser_used }`

---

## Shell

### `safe_shell` ⭐ preferred
Run a shell command after pattern-based allow/denylist checks. Returns a structured `blocked` response with a `suggested_safe_alternative` when denied.

| Arg | Type | Default |
|-----|------|---------|
| `command` | string ✅ | — |
| `cwd` | string | workspace root |
| `timeout_sec` | integer | 60 |

**Allowed (example patterns):** `ls`, `cat`, `pytest`, `git status/diff/log`, `ruff check`, `mypy`, `npm test`, `python`, `pip install`, `cargo test`, `go test`

**Blocked (example patterns):** `rm -rf`, `curl ... | bash`, `shutdown`, `reboot`, `mkfs`, writes to `/etc/` `/bin/` `/usr/`

**Returns (allowed):** `{ blocked: false, stdout, stderr, exit_code }`
**Returns (blocked):** `{ blocked: true, reason, matched_pattern, suggested_safe_alternative }`

---

### `shell`
Execute any shell command without pattern checks. Use `safe_shell` by default; reach for this only when you need a command not covered by the allowlist.

| Arg | Type | Default |
|-----|------|---------|
| `command` | string ✅ | — |
| `cwd` | string | workspace root |
| `timeout_sec` | integer | 60 |

**Returns:** `{ command, exit_code, stdout, stderr, success }`

---

## Workspace

### `workspace_info`
Detect installed runtimes and CLI tools. Result is cached after first call.

| Arg | Type | Default |
|-----|------|---------|
| `refresh` | boolean | `false` |

**Returns:** `{ workspace_root, os, platform, runtimes: {python,node,java,go}, git_present, git_repo_root, tools: {git,pytest,npm,ruff,eslint,mypy,pyright,tsc,...} }`

---

## Git

### `git_status`
Return structured branch, tracking, and file-state information.

**Returns:** `{ branch, upstream, ahead, behind, staged, unstaged, untracked, repo_root }`

---

### `git_diff`
Return a structured diff (per-file additions/deletions + raw diff text).

| Arg | Type | Default |
|-----|------|---------|
| `staged` | boolean | `false` |
| `pathspec` | array | (all) |
| `base_ref` | string | — |
| `target_ref` | string | — |

**Returns:** `{ diff_text, files_changed: [{path, additions, deletions, diff}] }`

---

### `git_commit`
Stage and commit files. **Requires `confirmed=true`.**

| Arg | Type | Required | Default |
|-----|------|----------|---------|
| `message` | string | ✅ | — |
| `confirmed` | boolean | ✅ | — |
| `paths` | array | | (already-staged) |
| `signoff` | boolean | | `false` |

**Returns:** `{ committed, commit_hash, files_committed, message }`

**Error codes:** `CONFIRMATION_REQUIRED`, `NOTHING_TO_COMMIT`

---

## Quality Loop

### `run_tests`
Run the test suite and return structured pass/fail results. Auto-detects pytest or npm test.

| Arg | Type | Default |
|-----|------|---------|
| `command` | string | (auto-detected) |
| `focus` | array | (all tests) |
| `timeout_sec` | integer | 60 |

**Returns:** `{ passed, total, passed_count, failed_count, summary, failures: [{file, test, reason, snippet}], raw_output }`

> ⚠️ Add a **max-iterations guard** in your agent scaffolding before deploying `run_tests` in an agentic loop. A model in a failing loop will call `run_tests` indefinitely without one.

---

### `run_lint`
Run the linter and return structured issues. Auto-detects ruff or eslint.

| Arg | Type | Default |
|-----|------|---------|
| `command` | string | (auto-detected) |
| `paths` | array | (whole workspace) |

**Returns:** `{ clean, issue_count, issues: [{file, line, col, rule, message, severity}], raw_output, parser_used }`

---

### `typecheck`
Run the type checker and return structured issues. Auto-detects mypy, pyright, or tsc.

| Arg | Type | Default |
|-----|------|---------|
| `command` | string | (auto-detected) |
| `paths` | array | (whole workspace) |

**Returns:** `{ clean, issue_count, issues: [{file, line, col, rule, message, severity}], raw_output, parser_used }`

---

## Project Intelligence

### `dependencies_read`
Parse dependency files in the workspace and return structured dependency lists. Supports `pyproject.toml`, `requirements.txt`, and `package.json`. When given a directory, auto-detects the first supported file found.

| Arg | Type | Default |
|-----|------|---------|
| `path` | string | workspace root |

**Returns:** `{ format, file, dependencies, dev_dependencies, total_count }`

Each dependency entry: `{ name, version, dev }`

**Error codes:** `NO_DEPENDENCY_FILE`, `READ_ERROR`, `UNSUPPORTED_FORMAT`

---

### `symbols_index`
Search for symbols (functions, classes, variables) by name across the workspace. Uses ripgrep for fast file pre-filtering combined with AST analysis for Python and regex for TypeScript/JS. Returns results within 2 seconds on repos up to 100k lines.

| Arg | Type | Required | Default |
|-----|------|----------|---------|
| `query` | string | ✅ | — |
| `lang` | string | | (all languages) |
| `exact` | boolean | | `false` |
| `max_results` | integer | | 50 |

`lang` accepts `python` or `typescript`. `exact=true` requires exact name match.

**Returns:** `{ query, results: [{symbol, file, line, kind, confidence}], result_count }`

`kind` is one of `function`, `class`, `variable`. `confidence` is `0.0–1.0`.

---

## Session State

### `state_set`
Store a JSON-serializable value under a key for the current session. State is in-memory only and not persisted across restarts. Use sparingly — prefer scaffolding-level state when available.

| Arg | Type | Required |
|-----|------|----------|
| `key` | string | ✅ |
| `value` | any JSON-serializable | ✅ |

**Returns:** `{ key, stored }`

**Error codes:** `INVALID_KEY`, `NOT_SERIALIZABLE`

---

### `state_get`
Retrieve a value previously stored with `state_set`. Returns `found=false` (not an error) when the key is missing.

| Arg | Type | Required |
|-----|------|----------|
| `key` | string | ✅ |

**Returns:** `{ key, value, found }`

---

## How tools are selected

The agent chooses tools automatically. Some hints:

- Exploring structure → `file_list` or `glob`
- Finding a symbol definition → `symbols_index`
- Finding symbol usages → `grep`
- Checking project dependencies → `dependencies_read`
- Making a surgical code change → `file_patch`
- Creating a new file → `file_write`
- Reviewing what changed → `git_diff`
- Running tests → `run_tests`
- Fixing lint issues → `run_lint` → `file_patch` → `run_lint` (loop)
- Committing → `git_status` → `git_diff` → `git_commit`
- Tracking intermediate results across tool calls → `state_set` / `state_get`

For CLI usage and slash commands, see `docs/user/CLI-REFERENCE.md`.
