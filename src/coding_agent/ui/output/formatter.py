"""Tool output formatting and display."""

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Any

from rich.syntax import Syntax
from rich.text import Text

from coding_agent.config import OutputConfig


class OutputType(Enum):
    """Types of tool output."""
    PLAIN = "plain"
    JSON = "json"
    DIFF = "diff"
    CODE = "code"
    TABLE = "table"
    TREE = "tree"
    ERROR = "error"
    SHELL = "shell"


class ToolStatus(Enum):
    """Tool execution status."""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


@dataclass
class FormattedOutput:
    """Formatted tool output ready for display."""
    output_type: OutputType
    content: str
    status: ToolStatus = ToolStatus.INFO
    timing_ms: float | None = None
    truncated: bool = False
    truncated_lines: int = 0


def detect_output_type(tool_name: str, output: str) -> OutputType:
    """Detect the type of tool output based on tool name and content.
    
    Args:
        tool_name: Name of the tool that produced the output
        output: The raw output string
        
    Returns:
        Detected OutputType
    """
    output = output.strip()
    
    if tool_name in ("file_patch", "git_diff"):
        return OutputType.DIFF

    if tool_name in ("shell", "safe_shell", "run_command"):
        return OutputType.SHELL

    if tool_name == "file_read":
        return OutputType.CODE

    if tool_name == "grep":
        if ":" in output and ("-" in output or re.search(r"\d+:", output)):
            return OutputType.TABLE

    if tool_name in ("run_tests", "run_lint", "typecheck"):
        return OutputType.TABLE

    if tool_name == "file_list":
        return OutputType.TREE

    if output.startswith("{") or output.startswith("["):
        try:
            json.loads(output)
            return OutputType.JSON
        except (json.JSONDecodeError, ValueError):
            pass

    if tool_name == "workspace_info":
        try:
            json.loads(output)
            return OutputType.JSON
        except (json.JSONDecodeError, ValueError):
            pass

    return OutputType.PLAIN


def detect_status(output: str, is_error: bool = False) -> ToolStatus:
    """Detect the status based on output content.
    
    Args:
        output: Tool output string
        is_error: Whether the tool reported an error
        
    Returns:
        Detected ToolStatus
    """
    if is_error:
        return ToolStatus.ERROR
    
    output_lower = output.lower()
    
    if ("error" in output_lower and "no error" not in output_lower) or "failed" in output_lower:
        return ToolStatus.ERROR
    
    if "warning" in output_lower or "warn" in output_lower:
        return ToolStatus.WARNING
    
    if "info" in output_lower or "workspace" in output_lower:
        return ToolStatus.INFO
    
    return ToolStatus.SUCCESS


def truncate_output_text(
    text: str,
    max_lines: int,
    max_chars: int,
    config: OutputConfig | None = None,
) -> tuple[str, bool, int]:
    """Smart truncation that keeps start and end of output.
    
    Args:
        text: Output text to truncate
        max_lines: Maximum number of lines to show
        max_chars: Maximum characters per line
        config: Optional OutputConfig for settings
        
    Returns:
        Tuple of (truncated text, was_truncated, lines_removed)
    """
    lines = text.split("\n")
    
    if len(lines) <= max_lines:
        truncated_text = "\n".join(line[:max_chars] for line in lines)
        return truncated_text, False, 0
    
    lines_removed = len(lines) - max_lines
    half = max_lines // 2
    
    kept_lines = []
    kept_lines.extend(lines[:half])
    kept_lines.append(f"... ({lines_removed} more lines) ...")
    kept_lines.extend(lines[-half:])
    
    truncated_text = "\n".join(line[:max_chars] for line in kept_lines)
    return truncated_text, True, lines_removed


def format_timing(timing_ms: float, format: str = "ms") -> str:
    """Format timing value based on format preference.
    
    Args:
        timing_ms: Timing in milliseconds
        format: Format type (ms, s, human)
        
    Returns:
        Formatted timing string
    """
    if format == "ms":
        return f"{timing_ms:.1f}ms"
    elif format == "s":
        seconds = timing_ms / 1000
        return f"{seconds:.2f}s"
    elif format == "human":
        if timing_ms < 1000:
            return f"{timing_ms:.0f}ms"
        else:
            seconds = timing_ms / 1000
            return f"{seconds:.1f}s"
    return f"{timing_ms:.1f}ms"


class ToolOutputFormatter:
    """Formatter for tool execution outputs."""
    
    def __init__(self, config: OutputConfig | None = None):
        """Initialize formatter with optional config.
        
        Args:
            config: Output configuration (uses defaults if None)
        """
        self.config = config or OutputConfig()
    
    def format(
        self,
        tool_name: str,
        output: str,
        is_error: bool = False,
        timing_ms: float | None = None,
    ) -> FormattedOutput:
        """Format tool output for display.
        
        Args:
            tool_name: Name of the tool
            output: Raw tool output
            is_error: Whether tool reported an error
            timing_ms: Execution time in milliseconds
            
        Returns:
            Formatted output ready for display
        """
        output_type = detect_output_type(tool_name, output)
        status = detect_status(output, is_error)
        
        truncated = False
        truncated_lines = 0
        
        if self.config.truncate:
            output, truncated, truncated_lines = truncate_output_text(
                output,
                self.config.max_lines,
                self.config.max_chars,
                self.config,
            )
        
        return FormattedOutput(
            output_type=output_type,
            content=output,
            status=status,
            timing_ms=timing_ms,
            truncated=truncated,
            truncated_lines=truncated_lines,
        )
    
    def get_status_indicator(self, status: ToolStatus) -> str:
        """Get the status indicator symbol.
        
        Args:
            status: ToolStatus to get indicator for
            
        Returns:
            Status indicator symbol
        """
        indicators = {
            ToolStatus.SUCCESS: "✓",
            ToolStatus.WARNING: "⚠",
            ToolStatus.ERROR: "✗",
            ToolStatus.INFO: "→",
        }
        return indicators.get(status, "→")
    
    def get_status_style(self, status: ToolStatus) -> str:
        """Get the Rich style for a status.
        
        Args:
            status: ToolStatus to get style for
            
        Returns:
            Rich style string
        """
        styles = {
            ToolStatus.SUCCESS: "green",
            ToolStatus.WARNING: "yellow",
            ToolStatus.ERROR: "red",
            ToolStatus.INFO: "cyan",
        }
        return styles.get(status, "blue")
