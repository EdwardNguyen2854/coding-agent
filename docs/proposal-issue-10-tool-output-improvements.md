# Tool Output Improvements - Proposal

## Overview

Enhance the display of tool execution results in the CLI to provide better readability, structured information display, and improved user experience for long-running or complex tool operations.

## Motivation

Currently, tool outputs are displayed with limited formatting and structure. Users face challenges with:

- **Long output truncation** - Large outputs are cut off without context
- **No visual hierarchy** - It's difficult to distinguish between different types of tool results
- **Poor readability** - JSON/diff output lacks syntax highlighting
- **No timing information** - Users can't see how long tools took to execute
- **Inconsistent formatting** - Different tools format their outputs differently

## Proposed Solution

### 1. Structured Output Display

**Tool Result Header**
```
[TOOL] file_read | users.py | 0.8ms
```

**Formatted Output Types**

| Output Type | Display Style |
|-------------|---------------|
| JSON | Syntax-highlighted, collapsible for large objects |
| Diff | Side-by-side or unified with syntax highlighting |
| Table | Rich Table with alignment |
| Tree | Indented tree structure |
| Plain text | Simple formatted output |

### 2. Output Truncation Improvements

- **Smart truncation** - Truncate in the middle, keeping start and end of output
- **Line count limits** - Configurable max lines per output type
- **Expandable output** - Allow users to expand truncated output
- **Full output option** - Save full output to file for inspection

```
[TOOL] grep | pattern="error" | 12 matches (showing first 5)
──────────────────────────────────────────────────────────
src/app.py:42:     logger.error("Failed to connect")
src/app.py:128:    error_handler("Connection failed")
src/utils.py:15:  raise Error("...")
... 7 more matches in 3 files
[Use /expand to see full output]
```

### 3. Execution Timing Display

| Option | Default | Description |
|--------|---------|-------------|
| `output.showTiming` | `true` | Show execution time per tool |
| `output.timingFormat` | `ms` | Timing format: ms, s, or human |

```
[TOOL] run_tests | ✓ Passed: 45/50 | 2.3s
```

### 4. Output Filtering

Allow users to filter tool output by:
- Tool name
- Output type (errors, warnings, success)
- File path pattern

```
/filter tool:grep    # Only show grep results
/filter error        # Only show errors
/filter clear        # Clear filters
```

### 5. Syntax Highlighting

Enable syntax highlighting for:
- JSON output
- Diff/patch output
- Code in tool results
- Error messages with stack traces

### 6. Color-Coded Status Indicators

```
[✓] file_write     - Success (green)
[⚠] run_lint       - Warnings (yellow)
[✗] run_tests      - Failed (red)
[→] file_read       - In progress / neutral (blue)
[i] workspace_info - Informational (cyan)
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `output.enabled` | `true` | Enable enhanced output display |
| `output.truncate` | `true` | Truncate long outputs |
| `output.maxLines` | `50` | Maximum lines to show |
| `output.maxChars` | `2000` | Maximum characters per line |
| `output.showTiming` | `true` | Show execution time |
| `output.syntaxHighlight` | `true` | Enable syntax highlighting |
| `output.statusIndicators` | `true` | Show color-coded status |

## Implementation

### Core API

```python
class ToolOutputFormatter:
    def format(self, tool_name: str, result: ToolResult) -> FormattedOutput:
        """Format tool result based on output type."""
        
    def truncate(self, output: str, max_lines: int, max_chars: int) -> str:
        """Smart truncation with context preservation."""
        
    def highlight(self, output: str, language: str) -> str:
        """Apply syntax highlighting."""
        
class OutputDisplay:
    def __init__(self, console: Console, config: OutputConfig):
        self.formatter = ToolOutputFormatter(config)
        
    def display(self, tool_name: str, result: ToolResult) -> None:
        """Display formatted tool output."""
```

### Output Type Detection

Automatically detect output type from tool result:
- `file_read` → plain text / code
- `file_patch` / `git_diff` → diff
- `grep` → matches with context
- `run_tests` → table with pass/fail
- `run_lint` → issue list
- JSON results → collapsible JSON tree

### UI Components

```
┌─────────────────────────────────────────────────────────┐
│ [✓] file_read │ users.py │ 0.8ms                       │
├─────────────────────────────────────────────────────────┤
│  1: import os                                           │
│  2: from datetime import datetime                       │
│  3:                                                      │
│  4: class User:                                         │
│  5:     def __init__(self, name: str):                  │
│  6:         self.name = name                             │
│  7:         self.created_at = datetime.now()            │
│  8:                                                      │
│  9:     def __repr__(self):                              │
│ 10:         return f"User({self.name!r})"                │
└─────────────────────────────────────────────────────────┘
```

## Alternatives Considered

1. **Use existing Rich panels** - Already partially implemented, but needs enhancement
2. **Full TUI for output** - Overkill for this use case
3. **External output viewer** - Less integrated, requires additional commands
4. **Simple print improvements** - Doesn't provide enough enhancement

## Compatibility

- Backward compatible: all enhancements can be disabled via config
- Works with existing tool result schema
- Preserves output for scripting when enhanced display is disabled
- Terminal auto-detection for color/syntax support
