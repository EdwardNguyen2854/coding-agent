# Tool Output Improvements - Implementation Plan

## Overview

This document details the implementation tasks for enhancing tool output display in the CLI.

## Task Breakdown

### Phase 1: Configuration & Infrastructure

| Task | Description | File |
|------|-------------|------|
| 1.1 | Add `OutputConfig` class to config module | `src/coding_agent/config/config.py` |
| 1.2 | Add output settings to AgentConfig | `src/coding_agent/config/config.py` |
| 1.3 | Add output config loading in `load_config()` | `src/coding_agent/config/config.py` |
| 1.4 | Add config CLI options (`--output-enabled`, `--output-max-lines`, etc.) | `src/coding_agent/ui/cli.py` |

**Config Options:**
```python
class OutputConfig(BaseModel):
    enabled: bool = True
    truncate: bool = True
    max_lines: int = 50
    max_chars: int = 2000
    show_timing: bool = True
    timing_format: str = "ms"  # ms, s, human
    syntax_highlight: bool = True
    status_indicators: bool = True
```

---

### Phase 2: Core Formatter Module

| Task | Description | File |
|------|-------------|------|
| 2.1 | Create `OutputFormatter` class | `src/coding_agent/ui/output/__init__.py` |
| 2.2 | Implement output type detection | `src/coding_agent/ui/output/formatter.py` |
| 2.3 | Implement smart truncation | `src/coding_agent/ui/output/formatter.py` |
| 2.4 | Implement syntax highlighting | `src/coding_agent/ui/output/formatter.py` |
| 2.5 | Implement status indicator rendering | `src/coding_agent/ui/output/formatter.py` |

**Output Types to Detect:**
- `file_read` → code/plain text
- `file_patch`, `git_diff` → diff
- `grep` → matches
- `run_tests` → test results
- `run_lint` → lint issues
- JSON objects → JSON tree

---

### Phase 3: UI Components

| Task | Description | File |
|------|-------------|------|
| 3.1 | Create `render_tool_header()` - tool name, status, timing | `src/coding_agent/ui/output/render.py` |
| 3.2 | Create `render_json_output()` - syntax highlighted JSON | `src/coding_agent/ui/output/render.py` |
| 3.3 | Create `render_diff_output()` - diff with highlighting | `src/coding_agent/ui/output/render.py` |
| 3.4 | Create `render_table_output()` - for test/lint results | `src/coding_agent/ui/output/render.py` |
| 3.5 | Create `render_truncated_output()` - with expand hint | `src/coding_agent/ui/output/render.py` |

---

### Phase 4: Integration

| Task | Description | File |
|------|-------------|------|
| 4.1 | Update Renderer class to use OutputFormatter | `src/coding_agent/ui/renderer.py` |
| 4.2 | Update Agent.execute_tool() to pass timing | `src/coding_agent/core/agent.py` |
| 4.3 | Add output rendering to agent tool execution | `src/coding_agent/core/agent.py` |
| 4.4 | Wire up config options in CLI | `src/coding_agent/ui/cli.py` |

---

### Phase 5: Filtering Commands

| Task | Description | File |
|------|-------------|------|
| 5.1 | Add `/filter` slash command | `src/coding_agent/ui/slash_commands.py` |
| 5.2 | Implement filter state management | `src/coding_agent/ui/output/filters.py` |
| 5.3 | Add `/expand` command for truncated output | `src/coding_agent/ui/slash_commands.py` |
| 5.4 | Add `/output` command for output history | `src/coding_agent/ui/slash_commands.py` |

---

### Phase 6: Testing & Polish

| Task | Description | File |
|------|-------------|------|
| 6.1 | Unit tests for OutputFormatter | `tests/test_output_formatter.py` |
| 6.2 | Unit tests for truncation logic | `tests/test_output_formatter.py` |
| 6.3 | Integration tests for CLI output | `tests/test_cli_output.py` |
| 6.4 | Test terminal compatibility | Manual testing |

---

## File Structure

```
src/coding_agent/ui/output/
├── __init__.py           # Exports
├── config.py             # OutputConfig
├── formatter.py          # ToolOutputFormatter class
├── render.py             # UI rendering functions
└── filters.py            # Output filtering
```

---

## Implementation Order

1. **Start with Phase 1** - Add configuration (low risk, foundational)
2. **Phase 2** - Core formatter (can be tested in isolation)
3. **Phase 3** - UI components (depends on Phase 2)
4. **Phase 4** - Integration (most risky, test thoroughly)
5. **Phase 5** - Filtering (nice-to-have, can iterate)
6. **Phase 6** - Testing throughout

---

## Key Dependencies

- `rich` - Already used in renderer
- `pygments` - For syntax highlighting (if needed beyond Rich)
- Existing `ToolResult` schema - Must remain compatible

---

## Backward Compatibility

All new features must be:
- Disabled by default or configurable
- Fallback to existing behavior when disabled
- Preserve full output in conversation for LLM context
