from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from coding_agent.checkpoint.models import Message, ToolInvocation

_log = logging.getLogger(__name__)


@dataclass
class AutoSaveConfig:
    enabled: bool = True
    interval: int = 10
    interval_minutes: int = 5


class CheckpointEventHandler:
    def __init__(
        self,
        get_messages: Callable[[], list[Message]],
        get_tool_invocations: Callable[[], list[ToolInvocation]],
        get_agent_context: Callable[[], dict[str, Any]],
        on_checkpoint_created: Callable[[str], None] | None = None,
    ):
        self._get_messages = get_messages
        self._get_tool_invocations = get_tool_invocations
        self._get_agent_context = get_agent_context
        self._on_checkpoint_created = on_checkpoint_created
        
        self._tool_count = 0
        self._last_save_time = time.time()
        self._lock = threading.Lock()

    def on_tool_executed(self, tool_name: str) -> bool:
        if not AutoSaveConfig().enabled:
            return False
            
        with self._lock:
            self._tool_count += 1
            config = AutoSaveConfig()
            
            if self._tool_count >= config.interval:
                self._tool_count = 0
                return True
        return False

    def on_timer_tick(self) -> bool:
        if not AutoSaveConfig().enabled:
            return False
            
        config = AutoSaveConfig()
        elapsed = time.time() - self._last_save_time
        
        if elapsed >= config.interval_minutes * 60:
            self._last_save_time = time.time()
            return True
        return False

    def on_risky_operation(self, operation: str) -> bool:
        risky_operations = {
            "file_delete",
            "git_force_push",
            "git_reset_hard",
            "shell_rm_rf",
        }
        return operation in risky_operations

    def should_auto_save(self) -> bool:
        config = AutoSaveConfig()
        if not config.enabled:
            return False
        
        if self._tool_count >= config.interval:
            return True
        
        elapsed = time.time() - self._last_save_time
        if elapsed >= config.interval_minutes * 60:
            return True
        
        return False

    def reset_counters(self) -> None:
        with self._lock:
            self._tool_count = 0
            self._last_save_time = time.time()

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "tool_count": self._tool_count,
                "last_save_time": self._last_save_time,
                "time_since_last_save": time.time() - self._last_save_time,
            }
