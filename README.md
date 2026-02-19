# Coding-Agent

Self-hosted, model-agnostic AI coding agent for internal department use.

## Features

- Interactive REPL mode with conversation history
- Streaming responses for real-time feedback
- Model-agnostic (works with any LiteLLM-supported model)
- Configuration via YAML file with CLI overrides
- Secure API key handling (masked in logs/output)

## Quick Start

### Prerequisites

- Python 3.10+
- [ripgrep](https://github.com/BurntSushi/ripgrep) installed and on PATH
- Access to internal LiteLLM server

### Installation

```bash
# Clone the repository
git clone <internal-repo-url>
cd Coding-Agent

# Install in development mode
pip install -e ".[dev]"
```

### Configuration

Create a config file at `~/.coding-agent/config.yaml`:

```yaml
model: litellm/gpt-4o
api_base: http://localhost:4000
api_key: your-api-key  # optional
https_proxy: http://proxy.example.com:8080  # optional
```

### Usage

```bash
# Launch interactive mode
coding-agent

# Override model from CLI
coding-agent --model litellm/gpt-4o

# Override API base from CLI
coding-agent --api-base http://localhost:4000

# Override both
coding-agent --model litellm/gpt-4o --api-base http://localhost:4000

# Show help
coding-agent --help
```

## Configuration Reference

| Option | Required | Description |
|--------|----------|-------------|
| `model` | Yes | LiteLLM model string (e.g., `litellm/gpt-4o`) |
| `api_base` | Yes | Base URL for the LiteLLM API server |
| `api_key` | No | API key for authentication |
| `https_proxy` | No | Proxy URL for HTTPS connections |

## CLI Options

- `--model TEXT` - Override the configured model
- `--api-base TEXT` - Override the configured API base URL
- `--help` - Show help message and exit

## Development

```bash
# Run tests
pytest

# Run tests with verbose output
pytest -v

# Run specific test file
pytest tests/test_llm.py
```
