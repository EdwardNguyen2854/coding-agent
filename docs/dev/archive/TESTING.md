# Testing Guide

## Running Tests

```bash
# All tests
pytest

# Single file
pytest tests/test_renderer.py

# Single test
pytest tests/test_performance.py::TestTokenCountCache::test_token_count_cache

# Verbose
pytest -v

# Coverage
pytest --cov=src/coding_agent --cov-report=term-missing
```

## Mocking Rich / Console

Rich writes to a real terminal. For unit tests, inject a `MagicMock()` console
or use `Console(file=io.StringIO())` to capture output:

```python
from unittest.mock import MagicMock, patch
from rich.console import Console
import io

# Option 1: mock console entirely
mock_console = MagicMock()
renderer = Renderer()
renderer.console = mock_console
renderer.print_error("oops")
mock_console.print.assert_called_once()

# Option 2: capture to StringIO
buf = io.StringIO()
console = Console(file=buf, highlight=False)
renderer = Renderer()
renderer.console = console
renderer.print_info("hello")
assert "hello" in buf.getvalue()
```

## Mocking litellm

Use `patch("litellm.completion")` or `patch("litellm.token_counter")`:

```python
from unittest.mock import patch

with patch("litellm.token_counter", return_value=1234) as mock_tc:
    count = conv.token_count
    mock_tc.assert_called_once()
```

Token count is cached, so multiple property accesses do not call `token_counter`
again until a mutation method is called.

## CLI Tests with CliRunner

Use `click.testing.CliRunner` to exercise the full CLI:

```python
from click.testing import CliRunner
from coding_agent.cli import cli

runner = CliRunner()
result = runner.invoke(cli, ["run"], input="exit\n", catch_exceptions=False)
assert result.exit_code == 0
```

Patch `LLMClient.verify_connection` to avoid real network calls:

```python
with patch("coding_agent.cli.LLMClient") as MockLLM:
    MockLLM.return_value.verify_connection.return_value = None
    result = runner.invoke(cli, ["run"], input="exit\n")
```

## Token Count Test Patterns

To assert caching without real LiteLLM:

```python
conv = ConversationManager("system")
call_count = [0]
original = conv._estimate_tokens

def counting(*args, **kwargs):
    call_count[0] += 1
    return original(*args, **kwargs)

conv._estimate_tokens = counting

_ = conv.token_count   # call 1
_ = conv.token_count   # still call 1 (cached)
conv.add_message("user", "hello")
_ = conv.token_count   # call 2 (invalidated)

assert call_count[0] == 2
```

## Test File Conventions

| File | Covers |
|---|---|
| `test_split_layout_removed.py` | Phase 1: split-pane is gone |
| `test_stability.py` | Phase 2: EOF handling, loop guards, silent exceptions |
| `test_performance.py` | Phase 3: lazy Markdown, token caching |
| `test_polish.py` | Phase 4: named constants importable |
| `test_renderer.py` | Renderer output helpers |
| `test_permissions.py` | Permission approval logic |
| `test_agent.py` | ReAct loop |
| `test_cli.py` | CLI entry point |
| `test_conversation.py` | Message history, truncation |
| `test_session.py` | Session persistence |
