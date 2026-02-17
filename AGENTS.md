# AGENTS.md - Agent Instructions for Coding-Agent

This document is for coding agents operating in this repository.

## Project Snapshot

- Name: `coding-agent`
- Python: 3.10+
- Packaging: `src/` layout (`src/coding_agent`)
- CLI entry point: `coding-agent`
- Main stack: `click`, `prompt-toolkit`, `litellm`, `pydantic`, `pyyaml`, `pytest`

## Build, Lint, and Test Commands

### Setup

```bash
pip install -e ".[dev]"
```

### Tests (most important)

```bash
# Run all tests
pytest

# Run one test file
pytest tests/test_llm.py

# Run one test class
pytest tests/test_llm.py::TestVerifyConnectionSuccess

# Run one test function (single test)
pytest tests/test_llm.py::TestVerifyConnectionSuccess::test_returns_without_error

# Run tests by substring expression
pytest -k "verify_connection"

# Verbose output
pytest -v

# Optional coverage (if plugin installed)
pytest --cov=src/coding_agent --cov-report=term-missing
```

### Lint / formatting

- No dedicated linter or formatter config is currently defined in `pyproject.toml`.
- Keep style consistent with existing code and this guide.

### Run the app

```bash
# Standard CLI
coding-agent

# Python module mode
python -m coding_agent

# Override config values from CLI
coding-agent --model litellm/gpt-4o --api-base http://localhost:4000
```

## Repository Structure

```text
src/coding_agent/
  __init__.py
  __main__.py
  cli.py
  config.py
  llm.py
  utils.py
  tools/
    __init__.py
    base.py

tests/
  conftest.py
  test_cli.py
  test_config.py
  test_llm.py
```

## Code Style Guidelines

### Imports

Use three groups with blank lines between them:
1. Standard library
2. Third-party packages
3. Local package imports

Example:

```python
from collections.abc import Generator
from pathlib import Path

import litellm
from pydantic import BaseModel

from coding_agent.config import AgentConfig
```

### Formatting and general style

- 4-space indentation, no tabs.
- Prefer <= 100 chars per line when practical.
- Use double quotes by default.
- Keep functions focused and small when possible.
- Add comments only for non-obvious logic.

### Type hints

- Use Python 3.10+ style annotations everywhere practical.
- Prefer concrete types like `list[dict]`, `str | None`, `Path`.
- Add return types to all public functions.

### Naming conventions

- Modules/functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private helpers: leading underscore (e.g., `_handle_llm_error`)

### Docstrings

- Use Google-style docstrings for public functions/classes.
- Include `Args`, `Returns`, and `Raises` where relevant.

### Error handling

- Use domain-specific exceptions (e.g., `ConfigError`) for config and validation paths.
- Raise clear, actionable errors with context (server URL, next steps).
- Prefer `raise ... from None` when suppressing noisy internal tracebacks.
- Do not leak secrets (API keys/tokens) in exceptions, logs, or CLI output.

## Testing Conventions

- `tests/` mirrors source modules.
- Use `pytest` fixtures for shared setup.
- Use `unittest.mock.patch` for network/LLM isolation.
- Use `click.testing.CliRunner` for CLI behavior tests.
- Test names should describe acceptance behavior, not implementation details.

Example single-test run:

```bash
pytest tests/test_config.py::TestLoadConfig::test_missing_config_file_raises_error
```

## Configuration Behavior (important for agents)

- Config file path: `~/.coding-agent/config.yaml`
- Required keys: `model`, `api_base`
- Optional key: `api_key`
- CLI flags override YAML config values.
- Pydantic model uses `extra="forbid"` (unknown keys fail validation).

## Security Expectations

- Never print or store plaintext secrets in output.
- Keep API key masking behavior intact (`repr`/`str` safety).
- Preserve actionable but sanitized error messages.

## Cursor / Copilot Rules

- Checked for Cursor rules in `.cursor/rules/` and `.cursorrules`: none found.
- Checked for Copilot rules in `.github/copilot-instructions.md`: none found.
- If these files are added later, merge their constraints into this document.

## Agent Workflow Notes

- Prefer minimal, targeted changes over broad refactors.
- Keep testability high; add or update tests with behavior changes.
- Preserve REPL conversation-history behavior in `cli.py`.
- Preserve streaming behavior and error translation in `llm.py`.
