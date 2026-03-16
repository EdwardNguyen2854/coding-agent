"""Tool output rendering functions."""

import json
import re
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from coding_agent.config import OutputConfig
from coding_agent.ui.output.formatter import (
    FormattedOutput,
    OutputType,
    ToolOutputFormatter,
    ToolStatus,
    detect_output_type,
    detect_status,
    format_timing,
    truncate_output_text,
)  # noqa: F401 — re-exported for callers


def render_tool_header(
    console: Console,
    tool_name: str,
    status: ToolStatus,
    status_indicator: str,
    timing_ms: float | None = None,
    show_timing: bool = True,
    timing_format: str = "ms",
    status_indicators: bool = True,
) -> None:
    """Render tool execution header with status and timing.
    
    Args:
        console: Rich Console instance
        tool_name: Name of the tool
        status: Tool execution status
        status_indicator: Status indicator symbol
        timing_ms: Execution time in milliseconds
        show_timing: Whether to show timing
        timing_format: Timing format (ms, s, human)
        status_indicators: Whether to show status indicators
    """
    style = "green" if status == ToolStatus.SUCCESS else \
            "yellow" if status == ToolStatus.WARNING else \
            "red" if status == ToolStatus.ERROR else "blue"

    parts = []
    if status_indicators:
        parts.append(f"[{style}]{status_indicator}[/{style}]")
    parts.append(f"[blue]{tool_name}[/blue]")

    if show_timing and timing_ms is not None:
        timing_str = format_timing(timing_ms, timing_format)
        parts.append(f"[dim]{timing_str}[/dim]")

    console.print(Rule(" ".join(parts), style="dim", align="left"))


def render_json_output(
    console: Console,
    output: str,
    syntax_highlight: bool = True,
) -> None:
    """Render JSON output with optional syntax highlighting.
    
    Args:
        console: Rich Console instance
        output: JSON output string
        syntax_highlight: Whether to apply syntax highlighting
    """
    try:
        parsed = json.loads(output)
        formatted = json.dumps(parsed, indent=2)
        
        if syntax_highlight:
            syntax = Syntax(formatted, "json", theme="ansi_dark")
            console.print(syntax)
        else:
            console.print(formatted)
    except (json.JSONDecodeError, ValueError):
        console.print(output)


def render_diff_output(
    console: Console,
    output: str,
    syntax_highlight: bool = True,
) -> None:
    """Render diff output with syntax highlighting.
    
    Args:
        console: Rich Console instance
        output: Diff output string
        syntax_highlight: Whether to apply syntax highlighting
    """
    if syntax_highlight:
        syntax = Syntax(output, "diff", theme="ansi_dark")
        console.print(syntax)
    else:
        console.print(output)


def render_table_output(
    console: Console,
    output: str,
    tool_name: str,
) -> None:
    """Render table-style output for test/lint results.
    
    Args:
        console: Rich Console instance
        output: Table output string
        tool_name: Tool name for formatting
    """
    table = Table(show_header=False, box=None, padding=(0, 1))
    
    lines = output.split("\n")
    for line in lines:
        if not line.strip():
            continue
        if "pass" in line.lower() or "✓" in line:
            table.add_row(Text(line, style="green"))
        elif "fail" in line.lower() or "✗" in line or "error" in line.lower():
            table.add_row(Text(line, style="red"))
        elif "warn" in line.lower():
            table.add_row(Text(line, style="yellow"))
        else:
            table.add_row(line)
    
    if table.row_count > 0:
        console.print(table)
    else:
        console.print(output)


def render_tree_output(
    console: Console,
    output: str,
) -> None:
    """Render tree-structured output.
    
    Args:
        console: Rich Console instance
        output: Tree output string
    """
    for line in output.split("\n"):
        if line.strip():
            console.print(f"  {line}")


def render_shell_output(
    console: Console,
    output: str,
) -> None:
    """Render shell tool output, splitting stdout/stderr visually.

    Args:
        console: Rich Console instance
        output: Shell output string (may be JSON)
    """
    try:
        data = json.loads(output)
        stdout = data.get("output") or data.get("stdout", "")
        stderr = data.get("stderr", "")
        exit_code = data.get("exit_code") if data.get("exit_code") is not None else data.get("returncode")
        message = data.get("message") or data.get("error", "")

        if stdout:
            console.print(f"[dim]stdout ▸[/dim] {stdout}")
        if stderr:
            console.print(f"[yellow]stderr ▸[/yellow] {stderr}")
        if exit_code is not None and exit_code != 0:
            console.print(f"[red]exit {exit_code}[/red]")
        if message and not stdout and not stderr:
            console.print(message)
        if not stdout and not stderr and not message:
            console.print(output)
    except (json.JSONDecodeError, ValueError):
        console.print(output)


_EXT_LEXER: dict[str, str] = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".tsx": "tsx", ".jsx": "jsx", ".json": "json", ".yaml": "yaml",
    ".yml": "yaml", ".md": "markdown", ".sh": "bash", ".bash": "bash",
    ".html": "html", ".css": "css", ".rs": "rust", ".go": "go",
    ".java": "java", ".cpp": "cpp", ".c": "c", ".h": "c",
    ".rb": "ruby", ".php": "php", ".sql": "sql", ".xml": "xml",
    ".toml": "toml", ".ini": "ini",
}


def render_code_output(
    console: Console,
    output: str,
    syntax_highlight: bool = True,
) -> None:
    """Render file content with syntax highlighting.

    Args:
        console: Rich Console instance
        output: File content or JSON wrapper
        syntax_highlight: Whether to apply syntax highlighting
    """
    file_path: str | None = None
    content = output

    try:
        data = json.loads(output)
        if isinstance(data, dict):
            file_path = data.get("path") or data.get("file_path")
            content = data.get("content") or data.get("data", output)
    except (json.JSONDecodeError, ValueError):
        pass

    if syntax_highlight:
        lexer = "text"
        if file_path:
            lexer = _EXT_LEXER.get(Path(file_path).suffix.lower(), "text")
        console.print(Syntax(content, lexer, line_numbers=True, theme="ansi_dark"))
    else:
        console.print(content)


_GREP_LINE = re.compile(r"^([^:]+):(\d+):(.*)$")


def render_grep_output(
    console: Console,
    output: str,
) -> None:
    """Render grep results as structured columns grouped by file.

    Args:
        console: Rich Console instance
        output: Grep output string
    """
    table = Table(show_header=False, box=None, padding=(0, 1))
    last_file: str | None = None
    has_matches = False

    for line in output.split("\n"):
        if not line.strip():
            continue
        m = _GREP_LINE.match(line)
        if m:
            has_matches = True
            file, lineno, content = m.group(1), m.group(2), m.group(3)
            if file != last_file:
                if last_file is not None:
                    table.add_row(Text("", style="dim"), Text("", style="dim"), Text("", style="dim"))
                last_file = file
            table.add_row(Text(file, style="cyan"), Text(lineno, style="yellow"), content)
        else:
            table.add_row(Text(line, style="dim"), Text("", style="dim"), Text("", style="dim"))

    if has_matches:
        console.print(table)
    else:
        console.print(output)


def render_truncated_hint(
    console: Console,
    truncated_lines: int,
) -> None:
    """Render hint about truncated output.
    
    Args:
        console: Rich Console instance
        truncated_lines: Number of lines removed
    """
    if truncated_lines > 0:
        console.print(f"[dim]... ({truncated_lines} more lines) ...[/dim]")
        console.print("[dim italic]Use /expand to see full output[/dim italic]")


def render_plain_output(
    console: Console,
    output: str,
) -> None:
    """Render plain text output.
    
    Args:
        console: Rich Console instance
        output: Plain text output
    """
    console.print(output)


def render_tool_output(
    console: Console,
    formatted: FormattedOutput,
    config: OutputConfig,
    tool_name: str,
) -> None:
    """Render formatted tool output based on type.
    
    Args:
        console: Rich Console instance
        formatted: Formatted output
        config: Output configuration
        tool_name: Name of the tool
    """
    if not config.enabled:
        console.print(formatted.content)
        return
    
    if formatted.output_type == OutputType.JSON:
        render_json_output(console, formatted.content, config.syntax_highlight)
    elif formatted.output_type == OutputType.DIFF:
        render_diff_output(console, formatted.content, config.syntax_highlight)
    elif formatted.output_type == OutputType.SHELL:
        render_shell_output(console, formatted.content)
    elif formatted.output_type == OutputType.CODE:
        render_code_output(console, formatted.content, config.syntax_highlight)
    elif formatted.output_type == OutputType.TABLE:
        if tool_name == "grep":
            render_grep_output(console, formatted.content)
        else:
            render_table_output(console, formatted.content, tool_name)
    elif formatted.output_type == OutputType.TREE:
        render_tree_output(console, formatted.content)
    else:
        render_plain_output(console, formatted.content)
    
    if formatted.truncated:
        render_truncated_hint(console, formatted.truncated_lines)