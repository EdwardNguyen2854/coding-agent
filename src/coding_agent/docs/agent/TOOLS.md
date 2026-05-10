# Tools Reference

All tools return `ToolResult(ok, error_code, message, data, warnings, artifacts)`.

## File System

| Tool | Args | Returns |
|------|------|---------|
| `file_read` | `path` ✅, `offset`, `limit` | `{path, content, total_lines}` |
| `file_write` | `path` ✅, `content` ✅, `overwrite` | `{path, bytes_written, created}` |
| `file_edit` | `path` ✅, `old_str` ✅, `new_str` ✅ | `{path, net_line_change}`. Errors: `MATCH_NOT_FOUND`, `AMBIGUOUS_MATCH` |
| `file_patch` ⭐ | `diff_text` or `patches`=[`{path, hunks:[{start,end,replace_with}]}`], optional `file_hash` | `{applied, files_changed, rejected_hunks}`. `start`/`end` 1-based inclusive, hunks applied high→low line. Use `file_hash` to guard against stale files. |
| `file_list` | `path`, `depth=2`, `include_hidden` | `{tree: {name, type, path, children?}}` |
| `file_move` | `src` ✅, `dst` ✅, `overwrite` | `{moved_from, moved_to}` |
| `file_delete` | `path` ✅, `recursive` | Dir requires `recursive=true`. Error: `RECURSIVE_REQUIRED` |

**When to use `file_patch` vs `file_write`:** New file or full replacement → `file_write`. Editing existing → `file_patch`.

## Search

| Tool | Args | Notes |
|------|------|-------|
| `glob` | `pattern` ✅, `base_path`, `max_results=500` | |
| `grep` | `pattern` ✅, `path`, `glob`, `case_sensitive=true`, `max_results=200` | Uses ripgrep when available |

## Shell

| Tool | Notes |
|------|-------|
| `safe_shell` ⭐ | Pattern-allowlisted. Blocked → `{blocked:true, reason, suggested_safe_alternative}`. Allowed: `ls`, `cat`, `pytest`, `git status/diff/log`, `ruff`, `mypy`, `npm test`, `python`, `pip install`. Blocked: `rm -rf`, `curl..|bash`, `shutdown`, writes to `/etc/` `/bin/` |
| `shell` | Unrestricted. Use `safe_shell` by default. |

Args: `command` ✅, `cwd`, `timeout_sec=60`

## Git

- `git_status` → `{branch, upstream, staged, unstaged, untracked}`
- `git_diff` → `{diff_text, files_changed: [{path, additions, deletions}]}`
- `git_commit` → requires `confirmed=true`. Errors: `CONFIRMATION_REQUIRED`, `NOTHING_TO_COMMIT`

## Quality Loop

| Tool | Auto-detects | Returns |
|------|-------------|---------|
| `run_tests` | pytest, npm test | `{passed, total, passed_count, failed_count, failures:[{file,test,reason}]}` |
| `run_lint` | ruff, eslint | `{clean, issue_count, issues:[{file,line,col,rule,message}]}` |
| `typecheck` | mypy, pyright, tsc | `{clean, issue_count, issues:[{file,line,col,rule,message}]}` |

> ⚠️ Add max-iterations guard before using `run_tests` in agentic loops.

## Project Intelligence

- `dependencies_read` → parses `pyproject.toml`, `requirements.txt`, `package.json`. Returns `{format, dependencies, total_count}`. Errors: `NO_DEPENDENCY_FILE`, `UNSUPPORTED_FORMAT`
- `symbols_index` → fast symbol search via ripgrep+AST. `lang`=`python`|`typescript`, `exact`. Returns `{results:[{symbol,file,line,kind,confidence}]}`, `kind`∈`function|class|variable`

## Session State

- `state_set` → `key` ✅, `value` ✅ (JSON, in-memory)
- `state_get` → `key` ✅. Returns `{found:false}` when missing.

## Quick Reference

```
New file / full replacement         → file_write
Edit existing file                  → file_patch (structured hunks or unified diff)
Exact substring replacement         → file_edit
Explore structure                  → file_list, glob
Find symbol definition             → symbols_index
Find symbol usages                 → grep
Check dependencies                 → dependencies_read
Run tests / lint / typecheck       → run_tests, run_lint, typecheck
Track cross-call state             → state_set / state_get
Commit                             → git_status → git_diff → git_commit
```