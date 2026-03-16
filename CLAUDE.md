# CLAUDE.md — AI Assistant Guide for coding-agent

This document provides context, conventions, and workflows for AI assistants working in this repository.

---

## Project Overview

**coding-agent** is a local AI coding assistant CLI built in Python. It implements a ReAct (Reason + Act) agent loop backed by any OpenAI-compatible LLM endpoint (via litellm), with a rich terminal UI, persistent sessions, 26 built-in tools, a workflow engine, and a multi-agent system.

- **Version:** see `pyproject.toml`
- **License:** MIT
- **Entry point:** `coding-agent` CLI command
- **Python requirement:** 3.10+

---

## Repository Structure

```
coding-agent/
├── src/coding_agent/          # All source code
│   ├── core/                  # Agent loop, LLM client, conversation, permissions, tools
│   ├── tools/                 # 26 tool implementations
│   ├── ui/                    # CLI, terminal UI, slash commands, rendering, sidebar/toolbar
│   ├── config/                # Configuration, skills, project instructions, personas
│   ├── state/                 # Session manager, todo/workflow state, SQLite persistence
│   ├── checkpoint/            # Conversation checkpoint save/restore
│   ├── workflow/              # YAML-based workflow execution engine
│   └── docs/                  # Embedded documentation (served to the agent at runtime)
├── tests/                     # Test suite (39 files, 719+ tests)
├── docs/                      # User-facing documentation
│   ├── user/                  # CLI reference, installation, skills, workflows
│   └── agent/                 # Tool reference, patch-vs-write guidance
├── workflows/                 # Example workflow YAML definitions
├── pyproject.toml             # Project metadata and dependencies
└── README.md                  # Primary user documentation
```

### Key Source Files

| File | Purpose |
|---|---|
| `src/coding_agent/ui/cli.py` | Main CLI entry point (Click) |
| `src/coding_agent/core/agent.py` | ReAct agent loop |
| `src/coding_agent/core/llm.py` | LLM client (litellm wrapper) |
| `src/coding_agent/core/conversation.py` | Message history + token counting |
| `src/coding_agent/core/permissions.py` | Tool execution gate/approval flow |
| `src/coding_agent/tools/__init__.py` | Tool registry (`build_tools()` factory) |
| `src/coding_agent/state/session.py` | SQLite-backed session persistence |
| `src/coding_agent/config/config.py` | Config loading (YAML + CLI overrides) |
| `src/coding_agent/ui/slash_commands.py` | Slash command registry and handlers |
| `src/coding_agent/workflow/engine.py` | YAML workflow executor |

---

## Development Setup

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run the CLI
coding-agent

# Use with a local Ollama model
coding-agent --ollama llama3

# Resume the last session
coding-agent --resume

# Resume a specific session by ID
coding-agent --session <session-id>
```

---

## Running Tests

```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_agent.py

# Run a specific test by name
pytest tests/test_agent.py::test_function_name

# Skip slow tests (if marked)
pytest -m "not slow"

# Verbose output
pytest -v
```

Test configuration lives in `pytest.ini` (verbose, short traceback). Fixtures are in `tests/conftest.py` (provides `workspace` and `guard` fixtures used across many tests).

There is no CI/CD pipeline — tests must be run manually before committing.

---

## Configuration

User config is stored at `~/.coding-agent/config.yaml`. Runtime data (sessions, checkpoints) is stored in `~/.coding-agent/` and `.coding-agent/` (gitignored) in the project root.

```yaml
# ~/.coding-agent/config.yaml example
model: litellm/gpt-4o              # LLM model identifier
api_base: http://localhost:4000    # API endpoint (OpenAI-compatible)
api_key: null                       # Optional API key
temperature: 0.0
max_output_tokens: 4096
max_context_tokens: 128000
auto_allow: false                  # Auto-approve tool execution
```

**Config precedence (highest to lowest):**
1. CLI flags
2. `~/.coding-agent/config.yaml`
3. Built-in defaults

---

## Architecture and Key Patterns

### Agent Loop (ReAct)

`Agent.run()` in `core/agent.py` implements a ReAct loop:
1. Send conversation to LLM via `LLMClient`
2. Parse tool calls from response
3. Execute tools through `ToolGuard` (permission checks)
4. Append tool results to conversation
5. Repeat until no more tool calls

### Tool System

All tools follow this pattern:
- Inherit from a base class
- Expose `name`, `schema()` (JSON schema for LLM), and `run()` methods
- Return a `ToolResult` dataclass with fields: `ok`, `error_code`, `message`, `data`, `warnings`, `artifacts`
- Registered via `build_tools()` factory in `tools/__init__.py`

**Tool categories:**
- **File tools:** read, write, edit, patch, glob, diff
- **Git tools:** status, diff, commit, branch operations
- **Shell tools:** run commands with optional approval
- **Search tools:** grep (via ripgrep), glob pattern matching
- **Quality tools:** run_lint, run_tests, typecheck
- **State tools:** todo management, workflow state, session control

### Permissions

`ToolGuard` in `core/permissions.py` gates every tool execution. When `auto_allow: false`, destructive or shell-executing tools prompt the user for approval. The guard supports an allowlist of pre-approved patterns.

### Session Persistence

`SessionManager` in `state/session.py` uses SQLite at `~/.coding-agent/sessions.db`. Sessions are auto-saved after each tool execution. Schema: `sessions` table with `id`, `title`, `created_at`, `updated_at`, `data` (JSON blob).

### Slash Commands

`SlashCommandHandler` dataclass in `ui/slash_commands.py`. Commands use prefixes `/`, `@`, `#`, `!` (configurable). Each handler has `name`, `handler` callback, `help` text, and `arg_required` flag.

### Workflow Engine

Workflows are defined in YAML files (see `workflows/` for examples). The engine in `workflow/engine.py` parses and executes multi-step workflows, with support for checkpoints (save/resume mid-workflow).

### UI / Rendering

- **Rich** library for markdown, tables, panels, syntax highlighting, and progress bars
- `StreamingDisplay` for incremental LLM output with lazy markdown rebuilding
- **prompt-toolkit** for interactive input with tab completion and keybindings
- Sidebar/toolbar for agent status, token counts, and sub-agent progress

### Multi-Agent

Sub-agents can be spawned from the main agent session. The toolbar shows sub-agent progress. A team/solo mode toggle controls whether sub-agents share context.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `litellm` | ≥1.81 | LLM API abstraction (OpenAI-compatible) |
| `rich` | ≥14.0 | Terminal rendering |
| `click` | ≥8.0 | CLI framework |
| `prompt-toolkit` | ≥3.0 | Interactive terminal input |
| `pydantic` | ≥2.0 | Data validation and config models |
| `pyyaml` | ≥6.0 | YAML config and workflow parsing |
| `truststore` | ≥0.9 | System SSL certificate injection |
| `pytest` | ≥9.0 | (dev) Test framework |

External runtime dependency: **ripgrep** (`rg`) must be on `PATH` for the grep tool to work.

---

## Code Conventions

- **Python 3.10+** — use match/case, `X | Y` union types where appropriate
- **Pydantic v2** for all config and data models (not dataclasses with `@validator`)
- **No linting config present** — follow PEP 8; match the style of surrounding code
- **No type annotations required** on existing code, but new code should include them
- **Dataclasses** are used alongside Pydantic; prefer Pydantic for validated config, dataclasses for internal data transfer
- **ToolResult** is the standard return type for all tool `run()` methods — always populate `ok` and `message`
- Tests use the `workspace` fixture (a temp dir) and `guard` fixture — do not write to real filesystem in tests

---

## Adding a New Tool

1. Create `src/coding_agent/tools/my_tool.py` with a class implementing `name`, `schema()`, and `run()`
2. Return a `ToolResult` from `run()`
3. Register the tool in `src/coding_agent/tools/__init__.py` inside `build_tools()`
4. Add tests in `tests/test_my_tool.py` using the `workspace` fixture
5. Document the tool in `docs/agent/TOOLS.md`

---

## File Editing Guidance

See `docs/agent/PATCH-VS-WRITE.md` for details, but the core rule is:
- **Patch/edit** for modifying existing files (preserves context, less token usage)
- **Write** only for creating new files or complete rewrites

---

## Documentation

| Path | Content |
|---|---|
| `README.md` | User-facing overview and quick start |
| `docs/user/CLI-REFERENCE.md` | All CLI flags and slash commands |
| `docs/user/INSTALLATION.md` | Installation and setup |
| `docs/user/SKILL-USAGE.md` | Custom skills system |
| `docs/user/WORKFLOW-USAGE.md` | YAML workflow authoring |
| `docs/agent/TOOLS.md` | Tool reference for the agent |
| `docs/agent/PATCH-VS-WRITE.md` | File editing strategy |

---

## Git Workflow

- Default development branch: `master` / `main`
- Feature branches follow the pattern: `claude/<description>-<id>`
- Commit messages are descriptive and prefixed with conventional types: `feat:`, `fix:`, `test:`, `chore:`, `docs:`
- No pre-commit hooks are configured
- Run `pytest` before committing to verify nothing is broken

---

## Known External Dependencies at Runtime

- **OpenAI-compatible LLM endpoint** — required for agent operation
- **ripgrep (`rg`)** — required for the grep/search tool
- **Git** — required for git tools (must be on `PATH`)
- **Ollama** (optional) — for local model inference at `http://localhost:11434`
