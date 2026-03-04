"""Tool output display module."""

from coding_agent.config import OutputConfig
from coding_agent.ui.output.formatter import (
    OutputType,
    ToolOutputFormatter,
    ToolStatus,
    detect_output_type,
    detect_status,
    format_timing,
    truncate_output_text,
)
from coding_agent.ui.output.render import (
    render_tool_header,
    render_tool_output,
    render_json_output,
    render_diff_output,
    render_table_output,
    render_tree_output,
    render_truncated_hint,
    render_plain_output,
)

__all__ = [
    "OutputConfig",
    "OutputType",
    "ToolOutputFormatter",
    "ToolStatus",
    "detect_output_type",
    "detect_status",
    "format_timing",
    "truncate_output_text",
    "render_tool_header",
    "render_tool_output",
    "render_json_output",
    "render_diff_output",
    "render_table_output",
    "render_tree_output",
    "render_truncated_hint",
    "render_plain_output",
]
