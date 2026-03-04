# CLI Reference

This page documents the runtime flags and interactive slash commands.

This is a personal portfolio project focused on practical, local-first AI developer tooling.

## Command

```bash
coding-agent [OPTIONS]
```

## Options

| Option | Type | Description |
|---|---|---|
| `--model` | text | Override configured model |
| `--api-base` | text | Override configured API base URL |
| `--temperature` | float | Override sampling temperature (`0.0-2.0`) |
| `--max-output-tokens` | int | Override max generated tokens |
| `--top-p` | float | Override nucleus sampling (`0.0-1.0`) |
| `--resume` | flag | Resume most recent session |
| `--session` | text | Resume specific session by ID |
| `--ollama` | text | Shorthand for local Ollama model |

## Examples

```bash
coding-agent
coding-agent --resume
coding-agent --session 123e4567-e89b-12d3-a456-426614174000
coding-agent --model litellm/gpt-4o-mini --api-base http://localhost:4000
coding-agent --ollama qwen2.5-coder:7b
```

## Slash commands

| Command | Description |
|---|---|
| `/help` | Show available slash commands |
| `/clear` | Clear current conversation |
| `/compact [session-id]` | Trigger conversation truncation (optionally for specific session) |
| `/sessions` | List saved sessions |
| `/model <name>` | Switch model in-session |
| `/model-info` | Show current model capabilities |
| `/temp [value]` | Set or show temperature (0.0-2.0) |
| `/top-p [value]` | Set or show top_p (0.0-1.0) |
| `/api-key <key>` | Set API key at runtime |
| `/config` | Show current runtime configuration |
| `/config-set <key> <value>` | Set a runtime config option |
| `/init` | Create an `AGENTS.md` template |
| `/skills` | Open skill configuration flow |
| `/todo` | Show or manage todo list |
| `/todo clear` | Clear completed tasks |
| `/todo next` | Show next pending task |
| `/todo done:<task>` | Mark a task as completed |
| `/plan <prompt>` | Ask agent to draft an implementation plan |
| `/approve` | Approve current plan and begin execution |
| `/reject` | Reject current plan |
| `/checkpoint` | Manage checkpoints (save, list, restore, delete, diff) |
| `/auto-allow on/off` | Toggle tool approval bypass |
| `/workflow list` | List available YAML workflows |
| `/workflow run <name>` | Run a workflow by name |
| `/workflow status` | Show incomplete workflows |
| `/filter [args]` | Filter tool output (e.g., /filter tool:grep error) |
| `/expand <id>` | Expand truncated tool output |
| `/output` | Show tool output history |
| `/exit` | Exit the session |

## Checkpoint commands

The `/checkpoint` command manages conversation checkpoints for saving and restoring state:

| Subcommand | Description |
|---|---|
| `/checkpoint save [name]` | Save current state with optional name |
| `/checkpoint list` | List all checkpoints |
| `/checkpoint restore <id> [--merge]` | Restore a checkpoint (--merge to combine with current) |
| `/checkpoint delete <id>` | Delete a checkpoint |
| `/checkpoint diff <id>` | Show changes since checkpoint |

Examples:
```bash
/checkpoint save "Before refactor"
/checkpoint list
/checkpoint restore abc123
/checkpoint diff abc123
```

## Quick access commands (@)

Run workflows directly with shorter commands:

| Command | Description |
|---|---|
| `@default` | Run the default workflow |
| `@code <task>` | Run quick-dev workflow for coding tasks |
| `@review [path]` | Run code-review workflow |
| `@analyze [path]` | Run analyze-codebase workflow |

## Lookup commands (#)

Search for symbols and files in your codebase:

| Command | Description |
|---|---|
| `#symbol <name>` | Search for a symbol (function, class) |
| `#file <filename>` | Search for a file |

## Shell commands (!)

Quick shell command shortcuts:

| Command | Description |
|---|---|
| `!run <command>` | Run a shell command |
| `!test` | Run tests |
| `!lint` | Run linter |
| `!tidy` | Run code formatter

## Workflow commands

Run YAML-defined workflows for automated multi-step tasks:

```bash
# List all available workflows
coding-agent workflow list

# Run a workflow (will prompt for variables)
coding-agent workflow run <name>

# Resume an interrupted workflow
coding-agent workflow run <name> --resume

# Skip confirmation prompts
coding-agent workflow run <name> --yolo

# Check status of incomplete workflows
coding-agent workflow status
```

See `docs/user/WORKFLOW-USAGE.md` for creating custom workflows.

## Session storage

Session files are written to:

`~/.coding-agent/sessions/*.json`

Each session stores message history, model, timestamps, and token estimate.

## Notes

- Interactive slash commands can evolve between releases; use `/help` in-session for current command help text.
- The project is MIT licensed. See `LICENSE`.

## Related docs

- Setup and troubleshooting: `docs/user/INSTALLATION.md`
- Skills usage: `docs/user/SKILL-USAGE.md`
- Workflow usage: `docs/user/WORKFLOW-USAGE.md`
- Project motivation and architecture: `README.md`
