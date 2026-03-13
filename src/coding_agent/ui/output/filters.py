"""Output filtering functionality."""

from dataclasses import dataclass, field
from typing import Callable

from coding_agent.ui.output.formatter import ToolStatus


@dataclass
class OutputFilter:
    """Filter for tool output."""
    tool_names: set[str] = field(default_factory=set)
    statuses: set[ToolStatus] = field(default_factory=set)
    patterns: list[str] = field(default_factory=list)


_HISTORY_LIMIT = 200


class OutputFilterManager:
    """Manages output filtering state."""

    def __init__(self):
        self._filters: list[OutputFilter] = []
        self._history: list[dict] = []
        self._expanded_outputs: dict[str, str] = {}
        self._next_id = 0
    
    def add_filter(self, filter: OutputFilter) -> None:
        self._filters.append(filter)
    
    def clear_filters(self) -> None:
        self._filters.clear()
    
    @property
    def filters(self) -> list[OutputFilter]:
        return self._filters
    
    def should_show(self, tool_name: str, status: ToolStatus, output: str) -> bool:
        if not self._filters:
            return True
        
        for f in self._filters:
            if f.tool_names and tool_name not in f.tool_names:
                return False
            if f.statuses and status not in f.statuses:
                return False
            if f.patterns:
                matched = any(p.lower() in output.lower() for p in f.patterns)
                if not matched:
                    return False
        return True
    
    def add_to_history(self, tool_name: str, status: ToolStatus, output: str, full_output: str) -> str:
        output_id = f"output_{self._next_id}"
        self._next_id += 1
        self._history.append({
            "id": output_id,
            "tool_name": tool_name,
            "status": status,
            "output": output,
            "full_output": full_output,
        })
        if len(self._history) > _HISTORY_LIMIT:
            self._history.pop(0)
        return output_id
    
    def get_full_output(self, output_id: str) -> str | None:
        for entry in self._history:
            if entry["id"] == output_id:
                return entry.get("full_output")
        return None
    
    def get_history(self) -> list[dict]:
        return self._history


_filter_manager: OutputFilterManager | None = None


def get_filter_manager() -> OutputFilterManager:
    global _filter_manager
    if _filter_manager is None:
        _filter_manager = OutputFilterManager()
    return _filter_manager


def parse_filter_args(args: str) -> OutputFilter:
    """Parse filter arguments into an OutputFilter.
    
    Args:
        args: Filter arguments like "tool:grep" or "error" or "tool:file_read,file_write"
        
    Returns:
        OutputFilter with parsed criteria
    """
    filter = OutputFilter()
    
    if not args or args.strip() == "":
        return filter
    
    parts = args.split()
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        if ":" in part:
            key, value = part.split(":", 1)
            key = key.lower()
            
            if key == "tool":
                tool_names = {t.strip() for t in value.split(",")}
                filter.tool_names = tool_names
            elif key == "status":
                statuses = set()
                for s in value.split(","):
                    s = s.strip().lower()
                    if s == "error":
                        statuses.add(ToolStatus.ERROR)
                    elif s == "warning":
                        statuses.add(ToolStatus.WARNING)
                    elif s == "success":
                        statuses.add(ToolStatus.SUCCESS)
                    elif s == "info":
                        statuses.add(ToolStatus.INFO)
                filter.statuses = statuses
            elif key == "pattern":
                filter.patterns.append(value)
        else:
            part_lower = part.lower()
            if part_lower in ("error", "errors"):
                filter.statuses.add(ToolStatus.ERROR)
            elif part_lower in ("warning", "warnings", "warn"):
                filter.statuses.add(ToolStatus.WARNING)
            elif part_lower in ("success", "ok"):
                filter.statuses.add(ToolStatus.SUCCESS)
            elif part_lower in ("info"):
                filter.statuses.add(ToolStatus.INFO)
            else:
                filter.patterns.append(part)
    
    return filter
