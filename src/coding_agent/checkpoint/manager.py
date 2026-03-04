from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Callable

from coding_agent.checkpoint.models import (
    Checkpoint,
    CheckpointSummary,
    Message,
    RestoreMode,
    SessionState,
    ToolInvocation,
)
from coding_agent.checkpoint.storage import CheckpointStorage, LocalCheckpointStorage

_log = logging.getLogger(__name__)


class CheckpointManager:
    def __init__(
        self,
        storage: CheckpointStorage | None = None,
        storage_dir: Path | None = None,
        compression: bool = True,
    ):
        if storage is not None:
            self._storage = storage
        elif storage_dir is not None:
            self._storage = LocalCheckpointStorage(storage_dir, compression)
        else:
            default_dir = Path.home() / ".coding-agent" / "checkpoints"
            self._storage = LocalCheckpointStorage(default_dir, compression)

    def create(
        self,
        name: str,
        messages: list[Message],
        tool_invocations: list[ToolInvocation] | None = None,
        agent_context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Checkpoint:
        session_state = self._capture_state()
        
        if agent_context is None:
            agent_context = {}

        session_state.agent_context = agent_context

        checkpoint = Checkpoint.create(
            name=name,
            session_state=session_state,
            messages=messages,
            tool_invocations=tool_invocations,
            metadata=metadata,
        )

        self._storage.save(checkpoint)
        _log.info("Created checkpoint %s: %s", checkpoint.id, name)

        return checkpoint

    def restore(
        self,
        checkpoint_id: str,
        mode: RestoreMode = RestoreMode.FULL,
    ) -> dict[str, Any] | None:
        checkpoint = self._storage.load(checkpoint_id)
        if checkpoint is None:
            _log.error("Checkpoint %s not found", checkpoint_id)
            return None

        if mode == RestoreMode.PREVIEW:
            return self._preview_checkpoint(checkpoint)

        if mode == RestoreMode.FULL:
            return self._restore_full(checkpoint)

        if mode == RestoreMode.MERGE:
            return self._restore_merge(checkpoint)

        return None

    def _preview_checkpoint(self, checkpoint: Checkpoint) -> dict[str, Any]:
        current_state = self._capture_state()
        
        changes = {
            "added_files": checkpoint.session_state.modified_files,
            "removed_files": [
                f for f in current_state.modified_files
                if f not in checkpoint.session_state.modified_files
            ],
            "modified_files": [
                f for f in checkpoint.session_state.modified_files
                if f in current_state.modified_files
            ],
        }

        return {
            "checkpoint": checkpoint,
            "current_state": current_state,
            "changes": changes,
            "message_count": len(checkpoint.messages),
            "tool_count": len(checkpoint.tool_invocations),
        }

    def _restore_full(self, checkpoint: Checkpoint) -> dict[str, Any]:
        self._apply_workspace_state(checkpoint.session_state)
        
        return {
            "checkpoint": checkpoint,
            "messages": checkpoint.messages,
            "tool_invocations": checkpoint.tool_invocations,
            "agent_context": checkpoint.session_state.agent_context,
            "workspace_state": checkpoint.session_state,
        }

    def _restore_merge(self, checkpoint: Checkpoint) -> dict[str, Any]:
        current_state = self._capture_state()
        
        merged_changes = {
            "keep_current": [],
            "restore_checkpoint": [],
        }

        for f in checkpoint.session_state.modified_files:
            if f in current_state.modified_files:
                merged_changes["keep_current"].append(f)
            else:
                merged_changes["restore_checkpoint"].append(f)

        self._apply_workspace_state(checkpoint.session_state)

        return {
            "checkpoint": checkpoint,
            "messages": checkpoint.messages,
            "tool_invocations": checkpoint.tool_invocations,
            "agent_context": checkpoint.session_state.agent_context,
            "workspace_state": checkpoint.session_state,
            "merged_changes": merged_changes,
        }

    def _apply_workspace_state(self, state: SessionState) -> None:
        for file_path, content in state.uncommitted_changes.items():
            path = Path(state.project_path) / file_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def list(self) -> list[CheckpointSummary]:
        return self._storage.list()

    def delete(self, checkpoint_id: str) -> bool:
        result = self._storage.delete(checkpoint_id)
        if result:
            _log.info("Deleted checkpoint %s", checkpoint_id)
        return result

    def cleanup(self, max_count: int, max_age_days: int) -> int:
        return self._storage.cleanup(max_count, max_age_days)

    def _capture_state(self) -> SessionState:
        project_path = str(Path.cwd())
        
        git_info = self._get_git_info()
        
        modified_files = []
        uncommitted_changes = {}
        
        if git_info:
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split("\n"):
                        if line:
                            status = line[:2]
                            file_path = line[3:]
                            modified_files.append(file_path)
                            
                            if status in ("M ", "??", "A "):
                                full_path = Path(project_path) / file_path
                                if full_path.exists() and full_path.is_file():
                                    try:
                                        uncommitted_changes[file_path] = full_path.read_text(
                                            encoding="utf-8"
                                        )
                                    except OSError:
                                        pass
            except (subprocess.TimeoutExpired, OSError) as e:
                _log.warning("Failed to get git status: %s", e)

        return SessionState(
            project_path=project_path,
            git_branch=git_info.get("branch") if git_info else None,
            git_commit=git_info.get("commit") if git_info else None,
            modified_files=modified_files,
            uncommitted_changes=uncommitted_changes,
        )

    def _get_git_info(self) -> dict[str, str] | None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=10,
            )
            branch = result.stdout.strip() if result.returncode == 0 else None

            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=10,
            )
            commit = result.stdout.strip()[:8] if result.returncode == 0 else None

            if branch or commit:
                return {"branch": branch, "commit": commit}
        except (subprocess.TimeoutExpired, OSError):
            pass
        return None
