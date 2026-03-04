from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class RestoreMode(Enum):
    FULL = "full"
    MERGE = "merge"
    PREVIEW = "preview"


@dataclass
class WorkspaceState:
    project_path: str
    git_branch: str | None = None
    git_commit: str | None = None
    modified_files: list[str] = field(default_factory=list)
    uncommitted_changes: dict[str, str] = field(default_factory=dict)
    untracked_files: list[str] = field(default_factory=list)


@dataclass
class SessionState:
    project_path: str
    git_branch: str | None = None
    git_commit: str | None = None
    modified_files: list[str] = field(default_factory=list)
    uncommitted_changes: dict[str, str] = field(default_factory=dict)
    untracked_files: list[str] = field(default_factory=list)
    agent_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolInvocation:
    tool_name: str
    arguments: dict[str, Any]
    result: str | None
    timestamp: str
    duration_ms: int = 0


@dataclass
class Message:
    role: str
    content: str
    timestamp: str | None = None


@dataclass
class Checkpoint:
    id: str
    name: str
    timestamp: str
    session_state: SessionState
    messages: list[Message]
    tool_invocations: list[ToolInvocation]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        name: str,
        session_state: SessionState,
        messages: list[Message],
        tool_invocations: list[ToolInvocation] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Checkpoint:
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            timestamp=datetime.now().isoformat(),
            session_state=session_state,
            messages=messages,
            tool_invocations=tool_invocations or [],
            metadata=metadata or {},
        )


@dataclass
class CheckpointSummary:
    id: str
    name: str
    timestamp: str
    message_count: int
    tool_count: int
    modified_files_count: int

    @classmethod
    def from_checkpoint(cls, checkpoint: Checkpoint) -> CheckpointSummary:
        return cls(
            id=checkpoint.id,
            name=checkpoint.name,
            timestamp=checkpoint.timestamp,
            message_count=len(checkpoint.messages),
            tool_count=len(checkpoint.tool_invocations),
            modified_files_count=len(checkpoint.session_state.modified_files),
        )
