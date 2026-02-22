# Installation

This guide walks through a clean local install of `coding-agent`.

For project context and motivation, see `README.md`.

## Prerequisites

- Python `3.10+`
- `ripgrep` on PATH (required by the `grep` tool)
- A reachable model backend:
  - LiteLLM/OpenAI-compatible endpoint, or
  - local Ollama runtime

Install `ripgrep`:

```bash
# Windows
winget install BurntSushi.ripgrep.MSI

# macOS
brew install ripgrep

# Ubuntu/Debian
sudo apt install ripgrep
```

## 1) Clone the repository

```bash
git clone <your-repo-url>
cd Coding-Agent
```

## 2) Create and activate a virtual environment

```bash
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (cmd)
# .venv\Scripts\activate.bat

# macOS/Linux
# source .venv/bin/activate
```

## 3) Install package dependencies

```bash
pip install -e ".[dev]"
```

## 4) Create config file

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

Notes:

- For Ollama, you can use model values like `ollama_chat/llama3.2`.
- If using `--ollama` on CLI, `api_base` defaults to `http://localhost:11434`.

## 5) Verify install

```bash
coding-agent --help
coding-agent skills
coding-agent --version
```

Optional smoke test:

```bash
coding-agent --ollama llama3.2
```

Run a chat session:

```bash
coding-agent
```

## Quick-start (Ollama)

If Ollama is running locally:

```bash
coding-agent --ollama llama3.2
```

## Troubleshooting

### `ripgrep` not found

Install ripgrep and reopen terminal so PATH refreshes.

### Config file errors

- Ensure file exists at `~/.coding-agent/config.yaml`
- Ensure `api_base` starts with `http://` or `https://`
- Ensure YAML is a mapping (not empty list/string)

### Connection failures

- Verify backend is up and reachable.
- Confirm `model` and `api_base` are compatible.
- If behind corporate proxy, set `https_proxy` in config.

### SSL/proxy issues

`coding-agent` applies truststore and proxy env vars early in startup. If you still fail TLS handshakes, verify system certificates and proxy settings.

## Related docs

- CLI flags and slash commands: `docs/CLI-REFERENCE.md`
- Skill authoring and loading: `docs/SKILL-USAGE.md`
- Project overview and motivation: `README.md`
- License: `LICENSE`
