#!/usr/bin/env python3
"""
Create GitHub issues for the coding-agent codebase improvement suggestions.
Usage: GITHUB_TOKEN=<token> python3 create_github_issues.py
"""

import os
import json
import urllib.request
import urllib.error
import time

REPO = "EdwardNguyen2854/coding-agent"
API_URL = f"https://api.github.com/repos/{REPO}/issues"

ISSUES = [
    # ── CRITICAL ──────────────────────────────────────────────────────────────
    {
        "title": "[Critical] SQLite thread safety: check_same_thread=False risks data corruption",
        "body": """## Priority: Critical

**File:** `src/coding_agent/state/db.py:32`

## Problem
`check_same_thread=False` disables SQLite's built-in thread safety checks. Any concurrent or async access to the same connection risks data corruption or silent data loss.

## Impact
- Data corruption in concurrent scenarios (e.g., sub-agent sessions writing simultaneously)
- Silent failures with no error raised

## Suggested Fix
- Use a connection-per-thread model or a connection pool
- Add explicit locking around all DB operations
- Or migrate to a thread-safe SQLite wrapper

## Steps to Reproduce
1. Spawn multiple sub-agents that write to the session DB simultaneously
2. Observe potential race conditions or corrupted session data
""",
        "labels": ["bug", "priority: critical", "database"],
    },
    {
        "title": "[Critical] Fragile retry logic in agent loop uses brittle string matching",
        "body": """## Priority: Critical

**File:** `src/coding_agent/core/agent.py:77-93`

## Problem
The simplified-history retry fallback detects model rejection via `"rejected the request"` string match on the exception message. This is brittle:
- Different LLM implementations may phrase the error differently
- Could produce false positives (triggering unnecessary fallback)
- Could produce false negatives (missing the signal and not retrying)

## Impact
- Silent failures in the fallback logic
- Potential infinite loops or unnecessary history simplification

## Suggested Fix
```python
# Instead of:
if "rejected the request" in str(e):
    ...

# Use a specific exception type or error code:
if isinstance(e, ModelRejectionError) or getattr(e, 'status_code', None) == 400:
    ...
```

## References
- `agent.py:77-93` — retry with simplified history
""",
        "labels": ["bug", "priority: critical", "agent-loop"],
    },
    {
        "title": "[Critical] Permission approval caching is overly coarse-grained",
        "body": """## Priority: Critical

**File:** `src/coding_agent/core/permissions.py:160-182`

## Problem
Approval keys are too broad:
- `shell:{command_first_word}` — approves **all** commands starting with the same word after a single user approval (e.g., approving `rm foo` also pre-approves `rm -rf /`)
- `file_edit:{parent_dir}` — approves all file edits in a directory after one approval

## Impact
- Security regression: one approval grants much broader permissions than the user intended
- Users cannot make fine-grained trust decisions

## Suggested Fix
- Include a hash of the full command/path in the approval key
- Or use exact-match keys and let users add explicit wildcard patterns
- Add a clear UI indication of what scope each approval covers

## References
- `permissions.py:160-182` — approval key generation
""",
        "labels": ["security", "priority: critical", "permissions"],
    },
    # ── HIGH ──────────────────────────────────────────────────────────────────
    {
        "title": "[High] Global state anti-pattern in spawn_sub_agent makes testing and threading unsafe",
        "body": """## Priority: High

**File:** `src/coding_agent/tools/spawn_sub_agent.py:38-46`

## Problem
Eight module-level globals (`_llm_client`, `_session_manager`, `_config`, etc.) are used for dependency injection:
```python
_llm_client = None
_session_manager = None
_session_data: dict[str, Any] | None = None
_config = None
_workspace_root: str | None = None
_renderer = None
_team_mode: bool = False
_active_sub_agent_name: str | None = None
```

Issues:
- Thread-unsafe (no locking around global mutations)
- Makes unit testing require careful setup/teardown
- Initialization order is implicit and fragile
- Violates dependency injection principles

## Suggested Fix
Inject dependencies via constructor or pass a context object to `run()` instead of using module globals.

## References
- `spawn_sub_agent.py:38-46`
- Similar pattern in `config/config.py:12,22,50-51`
""",
        "labels": ["refactoring", "priority: high", "architecture"],
    },
    {
        "title": "[High] Overly broad exception handling masks root causes",
        "body": """## Priority: High

**Files:**
- `src/coding_agent/core/llm.py:149, 186, 241`
- `src/coding_agent/core/conversation.py:200`
- `src/coding_agent/state/db.py:112`

## Problem
Multiple bare `except Exception as e` blocks with minimal context logging. This:
- Makes debugging difficult (no distinction between recoverable and fatal errors)
- Allows silent failures to propagate
- Makes it impossible to write reliable tests for error paths

## Suggested Fix
```python
# Instead of:
except Exception as e:
    logger.debug(f"Error: {e}")

# Be specific:
except (ConnectionError, TimeoutError) as e:
    logger.warning(f"Network error during LLM call: {e}", exc_info=True)
    raise
except ValueError as e:
    logger.error(f"Invalid response format: {e}", exc_info=True)
    raise ToolError(f"LLM returned invalid data: {e}") from e
```

## References
- `llm.py:149, 186, 241`
- `conversation.py:200`
- `db.py:112`
""",
        "labels": ["bug", "priority: high", "error-handling"],
    },
    {
        "title": "[High] Missing integration tests for critical paths",
        "body": """## Priority: High

**Files:** `tests/`

## Problem
No integration tests exist for:
- Full session create → save → load → resume cycle
- Concurrent access patterns
- LLM connection failures and recovery
- Large conversation context handling

Unit test coverage gaps:
- Agent loop retry logic with simplified history (`agent.py:77-93`)
- Context truncation strategy with real token counts (`conversation.py:126-148`)
- SQLite transaction rollback and recovery (`db.py:112`)
- Sub-agent error handling and cleanup (`spawn_sub_agent.py:145-154`)
- Permission approval caching edge cases (`permissions.py:160-182`)

## Suggested Fix
Add a `tests/integration/` directory with:
1. `test_session_lifecycle.py` — full create/save/load/resume cycle
2. `test_concurrent_access.py` — threading safety for DB operations
3. `test_llm_failures.py` — connection/timeout error recovery
4. `test_large_context.py` — context truncation and token counting accuracy

## References
- `tests/conftest.py` — existing fixtures
""",
        "labels": ["testing", "priority: high"],
    },
    # ── MEDIUM ────────────────────────────────────────────────────────────────
    {
        "title": "[Medium] Token estimation uses inaccurate magic number heuristic",
        "body": """## Priority: Medium

**Files:**
- `src/coding_agent/core/conversation.py:13, 200-203`
- `src/coding_agent/state/session.py:572`

## Problem
Token counting falls back to `len(content) // 4`, a rough approximation that:
- Is highly inaccurate for non-ASCII text (CJK, emoji, etc.)
- Is duplicated in two separate files with no shared constant
- Has no per-message caching, causing redundant recalculation
- May cause premature context pruning or unexpected overflow

## Suggested Fix
1. Use `tiktoken` or the model's actual tokenizer for accurate counting
2. Extract the magic number to a named constant: `_CHARS_PER_TOKEN = 4`
3. Add a per-message token cache keyed by message hash

## References
- `conversation.py:13` — `_TOOL_CALL_TOKEN_OVERHEAD = 50` (also arbitrary)
- `session.py:572` — duplicate heuristic
""",
        "labels": ["enhancement", "priority: medium", "performance"],
    },
    {
        "title": "[Medium] Hardcoded constants scattered across codebase with no central config",
        "body": """## Priority: Medium

**Files:** Multiple

## Problem
Behavioral tuning constants are spread across files with no way to configure them:

| Constant | Value | File |
|---|---|---|
| `max_iterations` | 40 | `agent.py:110` |
| `max_repeated` | 4 | `agent.py:113` |
| `_MAX_TOOL_OUTPUT_CHARS` | 1000 | `conversation.py:11` |
| `_TOOL_CALL_TOKEN_OVERHEAD` | 50 | `conversation.py:13` |
| `DEFAULT_SESSION_CAP` | 50 | `session.py:19` |
| `_MAX_TITLE_LEN` | 80 | `session.py:20` |
| `_MAX_PARAM_DISPLAY` | 120 | `permissions.py:6` |

## Suggested Fix
Add these to `AgentConfig` (or a dedicated `BehaviorConfig`) with appropriate defaults, validation, and CLI override support.

## References
- `src/coding_agent/config/config.py` — existing config model
""",
        "labels": ["enhancement", "priority: medium", "configuration"],
    },
    {
        "title": "[Medium] Dual tool registration systems create maintenance burden",
        "body": """## Priority: Medium

**File:** `src/coding_agent/tools/__init__.py:104-162`

## Problem
Two parallel tool registration systems coexist:
1. New `ToolDefinition`-based system via `build_tools()`
2. Legacy registry-based system (`tool_registry`, `execute_tool()`)
3. Special-case `spawn_sub_agent` carve-out

This creates:
- Confusion about which system is authoritative
- Risk of tools being registered in one but not the other
- Extra maintenance burden when adding new tools

## Suggested Fix
Migrate fully to the `ToolDefinition`-based system and deprecate the legacy registry. Remove `execute_tool()` and the old registry once all call sites are updated.

## References
- `tools/__init__.py:104-162`
""",
        "labels": ["refactoring", "priority: medium", "technical-debt"],
    },
    {
        "title": "[Medium] AgentConfig missing input validation for numeric fields",
        "body": """## Priority: Medium

**File:** `src/coding_agent/config/config.py:164-166`

## Problem
No bounds validation on config fields:
- `temperature` should be in `[0.0, 2.0]`
- `top_p` should be in `[0.0, 1.0]`
- `max_output_tokens` must be `> 0`
- `max_context_tokens` must be `> 0`

Invalid values will be silently passed to the LLM and may cause API errors at runtime.

## Suggested Fix
Add Pydantic v2 `field_validator` decorators:
```python
@field_validator('temperature')
@classmethod
def validate_temperature(cls, v):
    if not 0.0 <= v <= 2.0:
        raise ValueError(f'temperature must be in [0, 2], got {v}')
    return v
```

## References
- `config/config.py:164-166`
""",
        "labels": ["bug", "priority: medium", "validation"],
    },
    {
        "title": "[Medium] Legacy JSON session mode adds maintenance burden without benefit",
        "body": """## Priority: Medium

**File:** `src/coding_agent/state/session.py:39-54`

## Problem
Dual code paths for JSON and SQLite session storage:
- `_load_json()`, `_list_json()` duplicate SQLite logic
- JSON mode doesn't support sub-agents (`session.py:635`)
- Migration code (`lines 80-160`) adds complexity
- Migration doesn't use a transaction — interrupted migration leaves DB in inconsistent state (`session.py:112-142`)

## Suggested Fix
1. Mark JSON mode as deprecated in v0.12
2. Remove in v1.0 after a migration grace period
3. Add transaction safety to the migration path immediately

## References
- `session.py:39-54, 80-160, 112-142, 635`
""",
        "labels": ["technical-debt", "priority: medium", "database"],
    },
    # ── LOW ───────────────────────────────────────────────────────────────────
    {
        "title": "[Low] Inconsistent and incomplete type annotations across core modules",
        "body": """## Priority: Low

**Files:** `src/coding_agent/core/`

## Problem
Several parameters lack type annotations, reducing IDE support and making refactoring riskier:
- `Agent.__init__()` — `renderer` parameter untyped (`agent.py:21`)
- `ToolGuard.__init__()` — `renderer`, `callback` untyped (`permissions.py:39, 49`)
- `tool_call: Any` should use a typed dataclass (`agent.py:182`)
- Repeated `Optional[dict[str, Any]]` for `policy` should be a `Policy` TypedDict

## Suggested Fix
Add type annotations incrementally. Define a `Policy` TypedDict in `core/permissions.py` and use it consistently across all tool constructors.

## References
- `agent.py:21, 182`
- `permissions.py:39, 49`
- `tools/__init__.py:62`
""",
        "labels": ["enhancement", "priority: low", "type-safety"],
    },
    {
        "title": "[Low] Destructive shell command detection patterns are fragile",
        "body": """## Priority: Low

**File:** `src/coding_agent/core/permissions.py:20-31`

## Problem
Regex patterns for detecting dangerous commands have gaps:
- No anchors — `rm -rf` pattern matches anywhere in a command
- Pattern `r\">\\s*/dev/\"` misses single `>` redirections (`> /dev/null`)
- Windows patterns don't account for different flag orderings (`del /q /s` vs `del /s /q`)
- Case-insensitive matching may miss variants like `RM -RF`

## Suggested Fix
1. Add word boundaries and anchors to patterns
2. Test against a comprehensive set of dangerous commands
3. Consider using a whitelist approach (allow-list safe commands) rather than blocklist

## References
- `permissions.py:20-31`
""",
        "labels": ["security", "priority: low", "permissions"],
    },
    {
        "title": "[Low] Tool output truncation too aggressive for structured JSON responses",
        "body": """## Priority: Low

**File:** `src/coding_agent/core/conversation.py:159`

## Problem
`_prune_oldest_tool_output()` truncates tool outputs to 1000 characters. For structured JSON tool outputs, truncation mid-value produces malformed JSON that models may misinterpret.

## Suggested Fix
1. Truncate at a JSON-aware boundary (e.g., truncate array items rather than mid-string)
2. Or increase the threshold and add a separate limit for very large outputs
3. Add a `[truncated]` marker to signal the model that output was cut

## References
- `conversation.py:159`
- `conversation.py:11` — `_MAX_TOOL_OUTPUT_CHARS = 1000`
""",
        "labels": ["bug", "priority: low", "context-management"],
    },
    {
        "title": "[Low] Missing docstrings on key public methods",
        "body": """## Priority: Low

**Files:** Multiple

## Problem
Several important methods lack docstrings, making onboarding and maintenance harder:
- `Agent.__init__()` — no description of `renderer` parameter type or purpose
- `ConversationManager._estimate_tokens_heuristic()` — no explanation of the 4-char heuristic
- `ToolGuard._validate()` — minimal schema validation documentation
- `SpawnSubAgentTool.run()` — no error recovery strategy documented

## Suggested Fix
Add concise docstrings explaining:
1. The purpose and parameters of each method
2. The rationale behind non-obvious implementation choices
3. Error conditions and return values

## References
- `core/agent.py` — `Agent.__init__()`
- `core/conversation.py` — `_estimate_tokens_heuristic()`
- `core/permissions.py` — `ToolGuard._validate()`
- `tools/spawn_sub_agent.py` — `SpawnSubAgentTool.run()`
""",
        "labels": ["documentation", "priority: low"],
    },
]


def create_issue(token: str, issue: dict) -> dict:
    data = json.dumps({"title": issue["title"], "body": issue["body"], "labels": issue.get("labels", [])}).encode()
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "coding-agent-issue-creator",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN environment variable not set")
        print("Usage: GITHUB_TOKEN=ghp_... python3 create_github_issues.py")
        return 1

    print(f"Creating {len(ISSUES)} issues in {REPO}...")
    created = []
    for i, issue in enumerate(ISSUES, 1):
        try:
            result = create_issue(token, issue)
            url = result.get("html_url", "?")
            print(f"  [{i}/{len(ISSUES)}] Created #{result['number']}: {issue['title'][:60]}...")
            print(f"    {url}")
            created.append({"number": result["number"], "url": url, "title": issue["title"]})
            if i < len(ISSUES):
                time.sleep(0.5)  # Avoid rate limiting
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"  [{i}/{len(ISSUES)}] FAILED: {issue['title'][:60]}")
            print(f"    HTTP {e.code}: {body[:200]}")

    print(f"\nDone. Created {len(created)}/{len(ISSUES)} issues.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
