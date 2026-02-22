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
| `/compact` | Trigger conversation truncation |
| `/sessions` | List saved sessions |
| `/model <name>` | Switch model in-session |
| `/init` | Create an `AGENTS.md` template |
| `/skills` | Open skill configuration flow |
| `/todo` | Show or manage todo list |
| `/plan <prompt>` | Ask agent to draft an implementation plan |
| `/approve` | Approve current plan and begin execution |
| `/reject` | Reject current plan |
| `/auto-allow on/off` | Toggle tool approval bypass |
| `/exit` | Exit the session |

## Session storage

Session files are written to:

`~/.coding-agent/sessions/*.json`

Each session stores message history, model, timestamps, and token estimate.

## Notes

- Interactive slash commands can evolve between releases; use `/help` in-session for current command help text.
- The project is MIT licensed. See `LICENSE`.

## Related docs

- Setup and troubleshooting: `docs/INSTALLATION.md`
- Skills usage: `docs/SKILL-USAGE.md`
- Project motivation and architecture: `README.md`
