# Coding Agent

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](#)
[![Version](https://img.shields.io/badge/version-0.9.0-2ea44f.svg)](#)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`coding-agent` is a self-hosted, model-agnostic AI coding assistant for terminal workflows.
It is designed to feel like a local pair-programmer: chat-first UX, tool calling, slash commands,
session persistence, and configurable model backends via LiteLLM/Ollama.

## TL;DR

- Works with any OpenAI-compatible/LiteLLM model endpoint.
- Supports local Ollama models with `--ollama` shorthand.
- Includes built-in tools: file read/write/edit, glob, grep, shell.
- Provides slash commands for sessions, model switching, skills, todo/plan workflow, and approvals.
- Auto-saves chat sessions to `~/.coding-agent/sessions`.

## Why this project

There are many coding-agents, but I want to create one myself as a way to understand deeply under the hood. It is also a way to practice building AI agents.

## Demo Flow

```bash
# 1) Install
pip install -e ".[dev]"

# 2) Configure (create ~/.coding-agent/config.yaml)
# 3) Start interactive mode
coding-agent

# 4) Resume last session later
coding-agent --resume
```

Inside chat:

```text
/help
/sessions
/model litellm/gpt-4o-mini
/todo
/plan build a migration script for legacy config files
```

## Key Capabilities

### 1) Interactive terminal UX

- Streaming token output with markdown rendering.
- Prompt toolkit input with slash-command autocomplete.
- Split-pane layout (when terminal is wide enough) with sidebar/toolbar status.
- Keyboard interrupt support during generation and tool execution.

### 2) Tool-based coding agent loop

Built-in tools are registered in `src/coding_agent/tools/`:

- **File system**: `file_read`, `file_write`, `file_edit`, `file_patch`, `file_list`, `file_move`, `file_delete`
- **Search**: `glob`, `grep`, `symbols_index`
- **Shell**: `safe_shell`, `shell`
- **Git**: `git_status`, `git_diff`, `git_commit`
- **Quality**: `run_tests`, `run_lint`, `typecheck`
- **Project intelligence**: `dependencies_read`, `workspace_info`
- **Session state**: `state_set`, `state_get`

Tool execution is permission-gated, with an optional auto-allow mode (`/auto-allow on`).
See `docs/agent/TOOLS.md` for the full tool reference.

### 3) Workflow and planning commands

Slash commands include:

- Core: `/help`, `/clear`, `/compact`, `/sessions`, `/model`, `/exit`
- Project setup: `/init`, `/skills`
- Workflow: `/todo`, `/plan`, `/approve`, `/reject`
- Permissions: `/auto-allow`

### 4) Session persistence

- Sessions are stored as JSON under `~/.coding-agent/sessions`.
- Use `--resume` to continue latest session.
- Use `--session <id>` to load a specific one.

### 5) Skill system

- Loads skills from `~/.coding-agent/skills/<skill>/SKILL.md`.
- Loads project skill from `<repo-root>/SKILL.md`.
- Project skill overrides global skill with same name.

## Installation

See full guide: `docs/user/INSTALLATION.md`

Quick install:

```bash
git clone <your-repo-url>
cd Coding-Agent
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
# source .venv/bin/activate

pip install -e ".[dev]"
```

## Configuration

Create `~/.coding-agent/config.yaml`:

```yaml
model: litellm/gpt-4o
api_base: http://localhost:4000
api_key: null
https_proxy: null

temperature: 0.0
max_output_tokens: 4096
top_p: 1.0

max_context_tokens: 128000
auto_allow: false
```

### Config fields

| Field | Required | Default | Notes |
|---|---|---|---|
| `model` | Yes | - | e.g. `litellm/gpt-4o`, `ollama_chat/llama3.2` |
| `api_base` | Yes* | - | Required unless model implies Ollama default |
| `api_key` | No | `null` | Provider/API key |
| `https_proxy` | No | `null` | Applied early for outbound requests |
| `temperature` | No | `0.0` | Sampling control |
| `max_output_tokens` | No | `4096` | Max assistant output |
| `top_p` | No | `1.0` | Nucleus sampling |
| `max_context_tokens` | No | `128000` | Auto-truncation threshold |
| `auto_allow` | No | `false` | Auto-approve tool executions |

## CLI Reference

```bash
coding-agent [OPTIONS]
```

Options:

- `--model TEXT`
- `--api-base TEXT`
- `--temperature FLOAT`
- `--max-output-tokens INTEGER`
- `--top-p FLOAT`
- `--resume`
- `--session TEXT`
- `--ollama MODEL`

Examples:

```bash
# Use local Ollama model quickly
coding-agent --ollama llama3.2

# Override config for one run
coding-agent --model litellm/gpt-4o-mini --api-base http://localhost:4000

# Resume specific session
coding-agent --session 123e4567-e89b-12d3-a456-426614174000
```

## Repository Structure

```text
src/coding_agent/
  agent.py            # ReAct loop + tool handling
  cli.py              # CLI entrypoint and REPL
  config.py           # YAML config + validation
  slash_commands.py   # Built-in slash commands
  session.py          # Session persistence
  skills.py           # SKILL.md loader
  workflow.py         # Todo/plan workflow state
  tools/              # Tool implementations (22 tools)

docs/
  agent/
    TOOLS.md          # Tool reference (agent-facing)
    PATCH-VS-WRITE.md # File editing guidance
  user/
    INSTALLATION.md
    CLI-REFERENCE.md
    SKILL-USAGE.md
```

## Development

```bash
pytest
```

Useful local checks:

```bash
coding-agent --help
coding-agent skills
```

## Limitations

- Requires a valid model endpoint (or local Ollama runtime).
- Shell and file tools can execute impactful operations; keep permissions enabled unless needed.
- Token estimation is heuristic-based for context accounting.

## Contributing

1. Create a feature branch.
2. Keep changes scoped and tested.
3. Open a PR with rationale and usage notes.

## Documentation

- Installation: `docs/user/INSTALLATION.md`
- CLI reference: `docs/user/CLI-REFERENCE.md`
- Skills: `docs/user/SKILL-USAGE.md`
- Tool reference: `docs/agent/TOOLS.md`
- File editing guidance: `docs/agent/PATCH-VS-WRITE.md`

## License

This project is licensed under the MIT License. See `LICENSE`.
