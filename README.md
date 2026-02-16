# Coding-Agent

Self-hosted, model-agnostic AI coding agent for internal department use.

## Quick Start

### Prerequisites

- Python 3.11+
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

### Usage

```bash
# Launch interactive mode
coding-agent

# Override model
coding-agent --model litellm/gpt-4o

# Show help
coding-agent --help
```
