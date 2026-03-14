# Skill Usage

Skills let you add reusable, instruction-driven slash commands to `coding-agent`.

## Skill loading order

The agent loads skills from four locations (highest priority wins):

1. `<git-root>/SKILL.md` — legacy single-file project skill
2. `<cwd>/.coding-agent/skills/<skill-name>/SKILL.md` — subdirectory-local (monorepo)
3. `<git-root>/.coding-agent/skills/<skill-name>/SKILL.md` — project-level
4. `~/.coding-agent/skills/<skill-name>/SKILL.md` — global (lowest priority)

If names collide, the higher-priority location wins.

## SKILL.md format

Every skill is a `SKILL.md` file with an optional YAML frontmatter block followed by Markdown instructions:

```markdown
---
description: What this skill does and when to use it
argument-hint: [issue-number]
disable-model-invocation: false
user-invocable: true
allowed-tools: Read, Grep
model: litellm/gpt-4o
context: fork
agent: Explore
---

Skill instructions here.
```

### Frontmatter fields

| Field | Type | Default | Description |
|---|---|---|---|
| `description` | string | — | Help text and agent discoverability hint |
| `argument-hint` | string | — | Shown in autocomplete: e.g. `[issue-number]` |
| `disable-model-invocation` | bool | `false` | If `true`, agent never auto-invokes this skill |
| `user-invocable` | bool | `true` | If `false`, hidden from `/` menu (reference-only) |
| `allowed-tools` | list | `[]` | Tools that run without approval when skill is active |
| `model` | string | — | Override model for this skill's execution |
| `context` | string | — | Set to `fork` to run in isolated sub-agent |
| `agent` | string | — | Sub-agent type when `context: fork` (e.g. `Explore`) |

## Argument substitution

Pass arguments to skills and reference them with placeholders:

| Placeholder | Replaced with |
|---|---|
| `$ARGUMENTS` | All user-supplied arguments as a single string |
| `$ARGUMENTS[N]` or `$N` | Positional argument at index N (0-based) |
| `${CLAUDE_SKILL_DIR}` | Absolute path to the directory containing SKILL.md |
| `${CLAUDE_SESSION_ID}` | Current session ID |

If a skill has no `$ARGUMENTS` placeholder but the user provides arguments, they are appended as `Additional context: <args>`.

**Example:**

```markdown
---
description: Fix a GitHub issue
argument-hint: [issue-number]
---

Fix GitHub issue #$ARGUMENTS following project conventions.
```

Usage: `/fix-issue 42`

## Dynamic context injection

Use `` !`command` `` in skill content to run shell commands before the skill is sent to the agent. The output replaces the placeholder:

```markdown
---
description: Summarise the current pull request
allowed-tools: Bash
---

## PR diff
!`gh pr diff`

## PR description
!`gh pr view --json title,body`

Summarise the above PR in 3–5 sentences.
```

## Invocation controls

**`user-invocable: false`** — skill is reference-only context, not a slash command:

```markdown
---
description: API design conventions for this project
user-invocable: false
---

Always use kebab-case URL paths and return `{ error, code }` on failure.
```

The agent loads the description as context and applies the instructions automatically, but `/api-conventions` won't appear in the `/` menu.

**`disable-model-invocation: true`** — only you can invoke this skill; the agent never auto-triggers it:

```markdown
---
description: Deploy to production
disable-model-invocation: true
argument-hint: [environment]
---

Deploy the service to $ARGUMENTS environment following the runbook.
```

## Allowed tools

Grant approval-free tool access for the duration of a skill:

```markdown
---
description: Deep codebase search
allowed-tools: Read, Grep, Glob
---

Search the codebase for $ARGUMENTS and explain what you find.
```

Tools in `allowed-tools` bypass the normal approval prompt only while this skill is running. This also applies when the skill is referenced via the `skill:` field in a workflow step.

## Model override

Run a skill with a different model than the session default:

```markdown
---
description: Quick summary (uses a fast model)
model: ollama_chat/llama3.2
---

Summarise the conversation so far in two sentences.
```

## Global skill example

Create `~/.coding-agent/skills/code-review/SKILL.md`:

```markdown
---
description: Review code changes for bugs, risk, and maintainability.
---

You are a pragmatic code review specialist.

When invoked:
1. Identify correctness, security, and reliability issues first.
2. Highlight maintainability and readability concerns.
3. Provide concrete fixes with minimal patch suggestions.
4. End with a short risk summary.
```

Then in chat:

```text
/code-review
/code-review focus on data races and retry logic
```

## Project skill example

Create `<repo-root>/.coding-agent/skills/standards/SKILL.md`:

```markdown
---
description: Apply project-specific engineering standards.
---

Use this repository's coding conventions and release checklist.
Always include:
1. test impact,
2. migration impact,
3. rollback notes.
```

## Managing built-in skills

The CLI also supports toggling packaged skills from config:

```bash
coding-agent /skills
```

These settings are stored in `~/.coding-agent/config.yaml` under `skills`.

## Tips

- Keep skills single-purpose.
- Put stable cross-project workflows in global skills.
- Put repo conventions in project `.coding-agent/skills/`.
- Use `argument-hint` so users know what to pass.
- Use `disable-model-invocation: true` for side-effect operations (deploy, send message).
- Use `user-invocable: false` for conventions the agent should follow automatically.
- Use `allowed-tools` instead of `auto_allow` for fine-grained per-skill permissions.

## Related docs

- Installation and environment setup: `docs/user/INSTALLATION.md`
- Runtime flags and slash commands: `docs/user/CLI-REFERENCE.md`
- Workflow authoring: `docs/user/WORKFLOW-USAGE.md`
- Project motivation and roadmap context: `README.md`
