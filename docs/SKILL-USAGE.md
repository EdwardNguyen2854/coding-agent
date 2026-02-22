# Skill Usage

Skills let you add reusable, instruction-driven slash commands to `coding-agent`.

This project is maintained as a portfolio project, so skills are a key extension point used to demonstrate custom agent behavior.

## Skill loading order

The agent loads skills from two locations:

1. Global skills folder: `~/.coding-agent/skills/<skill-name>/SKILL.md`
2. Project skill file: `<repo-root>/SKILL.md`

If names collide, project skill wins.

## Important behavior

- A skill command name comes from the skill folder name (or project skill folder context).
- Skill content is taken from the entire `SKILL.md` body.
- Optional YAML frontmatter key `description` is used for help text.
- Skill commands are registered dynamically and can be invoked as `/<skill-name>`.

## Global skill example

Create this file:

`~/.coding-agent/skills/code-review/SKILL.md`

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

Create `<repo-root>/SKILL.md`:

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

This skill is loaded for the current repository and can override a same-named global skill.

## Managing built-in skills

The CLI also supports toggling packaged skills from config:

```bash
coding-agent skills
coding-agent skills all
coding-agent skills none
coding-agent skills 1,3,5
```

These settings are stored in `~/.coding-agent/config.yaml` under `skills`.

## Tips

- Keep skills single-purpose.
- Put stable cross-project workflows in global skills.
- Put repo conventions in project `SKILL.md`.
- Include explicit output format instructions for consistent results.

## Related docs

- Installation and environment setup: `docs/INSTALLATION.md`
- Runtime flags and slash commands: `docs/CLI-REFERENCE.md`
- Project motivation and roadmap context: `README.md`
- License: `LICENSE`
