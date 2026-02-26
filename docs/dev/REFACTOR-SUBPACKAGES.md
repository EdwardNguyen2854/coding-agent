# Refactor: Split `src/coding_agent/` into Subpackages

## Motivation

The top-level `src/coding_agent/` package currently contains 24 Python modules in a single flat
directory. `tools/` and `workflows/` already demonstrate that subpackages work well here. The rest
of the codebase deserves the same treatment before the flat layout becomes a real navigation
problem.

---

## Target Structure

```
src/coding_agent/
  __init__.py          ← keep (add public re-exports here)
  __main__.py          ← keep (entry point, unchanged)

  config/              ← loading, validation, personas  [Phase 1]
    __init__.py
    config.py
    project_instructions.py
    skills.py
    agent_persona.py
    utils.py

  state/               ← persistence & workflow state   [Phase 2]
    __init__.py
    session.py
    db.py
    schema.py
    todo.py
    workflow_impl.py

  core/                ← agent brain & LLM plumbing     [Phase 3]
    __init__.py
    agent.py
    llm.py
    conversation.py
    system_prompt.py
    permissions.py
    tool_guard.py
    tool_result.py

  ui/                  ← everything the user sees       [Phase 4]
    __init__.py
    cli.py
    renderer.py
    sidebar.py
    interrupt.py
    slash_commands.py

  tools/               ← (already a subpackage)        [Phase 5 — import fixes only]
  workflows/           ← (already a subpackage, untouched)
```

Phases follow the dependency graph: `config` has no internal deps → `state` uses config →
`core` uses config + state + tools → `ui` uses everything. Each phase leaves `pytest` green
before the next one starts.

---

## Phase 1 — `config/`

**Files to move**

| From | To |
|---|---|
| `config.py` | `config/config.py` |
| `project_instructions.py` | `config/project_instructions.py` |
| `skills.py` | `config/skills.py` |
| `agent_persona.py` | `config/agent_persona.py` |
| `utils.py` | `config/utils.py` |

**Why first:** these modules sit at the bottom of the dependency graph. They import from stdlib
and third-party packages only. Moving them first makes all subsequent phases simpler.

**Import updates required**

- Within moved files: no internal `coding_agent.*` imports expected (verify before moving)
- Every other module that does `from coding_agent.config import ...` →
  `from coding_agent.config.config import ...`
- Every other module that does `from coding_agent.utils import ...` →
  `from coding_agent.config.utils import ...`
- Same pattern for `project_instructions`, `skills`, `agent_persona`
- All test files that import these modules

**Deliverable:** `pytest` green at 626/8 before moving to Phase 2.

---

## Phase 2 — `state/`

**Files to move**

| From | To |
|---|---|
| `session.py` | `state/session.py` |
| `db.py` | `state/db.py` |
| `schema.py` | `state/schema.py` |
| `todo.py` | `state/todo.py` |
| `workflow_impl.py` | `state/workflow_impl.py` |

**Why second:** depends only on `config/` (now settled) and stdlib. Contains no UI or agent logic.

**Import updates required**

- Within moved files: update any `from coding_agent.config import` →
  `from coding_agent.config.config import`
- Every module that imports from `session`, `db`, `schema`, `todo`, `workflow_impl` gets
  updated to the `state.*` path
- All test files that import these modules

**Deliverable:** `pytest` green at 626/8 before moving to Phase 3.

---

## Phase 3 — `core/`

**Files to move**

| From | To |
|---|---|
| `agent.py` | `core/agent.py` |
| `llm.py` | `core/llm.py` |
| `conversation.py` | `core/conversation.py` |
| `system_prompt.py` | `core/system_prompt.py` |
| `permissions.py` | `core/permissions.py` |
| `tool_guard.py` | `core/tool_guard.py` |
| `tool_result.py` | `core/tool_result.py` |

**Why third:** depends on `config/`, `state/`, and `tools/` — all stable by this point.
This is the most cross-referenced layer so doing it after `config` and `state` reduces
the number of imports to chase down.

**Import updates required**

- Within moved files: update `coding_agent.config`, `coding_agent.session`,
  `coding_agent.tool_result`, etc. to their new paths
- `ui/` modules (not yet moved but still flat) that import from core get updated here
  as a preview, since they'll be touched again in Phase 4 anyway — or defer to Phase 4
- `tools/__init__.py` and any tool file that imports `tool_result`, `permissions`, etc.
- `__main__.py` if it imports core modules
- All test files that import these modules

**Deliverable:** `pytest` green at 626/8 before moving to Phase 4.

---

## Phase 4 — `ui/`

**Files to move**

| From | To |
|---|---|
| `cli.py` | `ui/cli.py` |
| `renderer.py` | `ui/renderer.py` |
| `sidebar.py` | `ui/sidebar.py` |
| `interrupt.py` | `ui/interrupt.py` |
| `slash_commands.py` | `ui/slash_commands.py` |

**Why last:** `ui/` imports from every other layer. Moving it last means all its dependencies
already have settled paths, so import updates are straightforward.

**Import updates required**

- Within moved files: update all internal imports to their new subpackage paths
- `__main__.py` entry point: update `from coding_agent.cli import cli` →
  `from coding_agent.ui.cli import cli`
- `pyproject.toml` `[project.scripts]` entry point — verify it still resolves correctly
  (it calls the `cli` function via the installed entry point, which goes through
  `__main__.py`, so no change needed there)
- All test files that import `cli`, `renderer`, `slash_commands`, etc.

**Deliverable:** `pytest` green at 626/8 before moving to Phase 5.

---

## Phase 5 — `tools/` import fixes

**No files moved.** `tools/` is already a subpackage. This phase just sweeps for any
`from coding_agent.X import` references inside `tools/*.py` that point to modules now
living under a subpackage path, and updates them.

**Likely targets**

- `tools/__init__.py` — imports `tool_result`, `permissions`, `config` and others
- Individual tool files that import `tool_result`, `config`, `session`, etc.

**Deliverable:** `pytest` green at 626/8. Refactor complete.

---

## Phase 6 — Cleanup & docs

- Add re-exports to top-level `src/coding_agent/__init__.py` for any public names
  consumed externally:
  ```python
  from coding_agent.core.agent import Agent
  from coding_agent.ui.cli import cli
  from coding_agent.config.config import AgentConfig, load_config
  ```
- Update `CLAUDE.md` repository structure section
- Commit each phase separately for clean history and easy bisect

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Missed import → `ImportError` | `pytest` run after every phase; grep `from coding_agent\.` across all files before closing each phase |
| Circular imports | Subpackages don't change semantics; existing discipline applies. Dependency direction: `config ← state ← core ← ui` |
| `split_layout.py` absent | Already removed from filesystem — not in scope |
| External code importing `coding_agent.*` | Top-level `__init__.py` re-exports cover this |
| `pyproject.toml` entry point breaks | Entry point calls `coding_agent.__main__`, which stays at root — no change needed |

---

## Acceptance Criteria (per phase)

- [ ] All target files moved into subpackage directory
- [ ] `pytest` passes at 626 passed / 8 skipped after each phase
- [ ] No `from coding_agent.<old-flat-path>` references remain (grep check)
- [ ] After Phase 4: `coding-agent` CLI starts without error
- [ ] After Phase 6: `CLAUDE.md` updated, top-level `__init__.py` has re-exports
