import pytest
import tempfile
import shutil
from pathlib import Path

from coding_agent.checkpoint.models import (
    Checkpoint,
    CheckpointSummary,
    Message,
    SessionState,
    ToolInvocation,
    RestoreMode,
)
from coding_agent.checkpoint.storage import LocalCheckpointStorage
from coding_agent.checkpoint.manager import CheckpointManager


class TestCheckpointModels:
    def test_checkpoint_create(self):
        session_state = SessionState(project_path="/test/project")
        messages = [Message(role="user", content="Hello")]
        
        checkpoint = Checkpoint.create(
            name="Test Checkpoint",
            session_state=session_state,
            messages=messages,
        )
        
        assert checkpoint.id is not None
        assert checkpoint.name == "Test Checkpoint"
        assert checkpoint.timestamp is not None
        assert len(checkpoint.messages) == 1
        assert checkpoint.messages[0].content == "Hello"

    def test_checkpoint_summary_from_checkpoint(self):
        session_state = SessionState(project_path="/test/project")
        messages = [Message(role="user", content="Hello")]
        tool_invocations = [
            ToolInvocation(
                tool_name="test",
                arguments={},
                result="ok",
                timestamp="2024-01-01T00:00:00",
                duration_ms=100,
            )
        ]
        
        checkpoint = Checkpoint.create(
            name="Test",
            session_state=session_state,
            messages=messages,
            tool_invocations=tool_invocations,
        )
        
        summary = CheckpointSummary.from_checkpoint(checkpoint)
        
        assert summary.id == checkpoint.id
        assert summary.name == "Test"
        assert summary.message_count == 1
        assert summary.tool_count == 1
        assert summary.modified_files_count == 0


class TestLocalCheckpointStorage:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage = LocalCheckpointStorage(Path(self.temp_dir), compression=False)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_save_and_load(self):
        session_state = SessionState(project_path="/test/project")
        checkpoint = Checkpoint.create(
            name="Test",
            session_state=session_state,
            messages=[Message(role="user", content="Hello")],
        )
        
        self.storage.save(checkpoint)
        loaded = self.storage.load(checkpoint.id)
        
        assert loaded is not None
        assert loaded.id == checkpoint.id
        assert loaded.name == "Test"
        assert len(loaded.messages) == 1

    def test_list(self):
        session_state = SessionState(project_path="/test/project")
        
        for i in range(3):
            checkpoint = Checkpoint.create(
                name=f"Checkpoint {i}",
                session_state=session_state,
                messages=[],
            )
            self.storage.save(checkpoint)
        
        summaries = self.storage.list()
        
        assert len(summaries) == 3

    def test_delete(self):
        session_state = SessionState(project_path="/test/project")
        checkpoint = Checkpoint.create(
            name="Test",
            session_state=session_state,
            messages=[],
        )
        
        self.storage.save(checkpoint)
        assert self.storage.delete(checkpoint.id) is True
        assert self.storage.load(checkpoint.id) is None
        assert self.storage.delete("nonexistent") is False

    def test_cleanup_max_count(self):
        session_state = SessionState(project_path="/test/project")
        
        for i in range(5):
            checkpoint = Checkpoint.create(
                name=f"Checkpoint {i}",
                session_state=session_state,
                messages=[],
            )
            self.storage.save(checkpoint)
        
        deleted = self.storage.cleanup(max_count=3, max_age_days=0)
        
        assert deleted == 2
        assert len(self.storage.list()) == 3


class TestCheckpointManager:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = CheckpointManager(storage_dir=Path(self.temp_dir), compression=False)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_create_checkpoint(self):
        checkpoint = self.manager.create(
            name="Test Checkpoint",
            messages=[Message(role="user", content="Hello")],
            tool_invocations=[],
        )
        
        assert checkpoint.id is not None
        assert checkpoint.name == "Test Checkpoint"

    def test_list_checkpoints(self):
        self.manager.create(name="CP1", messages=[], tool_invocations=[])
        self.manager.create(name="CP2", messages=[], tool_invocations=[])
        
        summaries = self.manager.list()
        
        assert len(summaries) == 2

    def test_restore_preview(self):
        checkpoint = self.manager.create(
            name="Test",
            messages=[Message(role="user", content="Hello")],
        )
        
        result = self.manager.restore(checkpoint.id, RestoreMode.PREVIEW)
        
        assert result is not None
        assert "changes" in result

    def test_delete_checkpoint(self):
        checkpoint = self.manager.create(name="Test", messages=[], tool_invocations=[])
        
        assert self.manager.delete(checkpoint.id) is True
        assert self.manager.list() == []


class TestRestoreMode:
    def test_restore_modes(self):
        assert RestoreMode.FULL.value == "full"
        assert RestoreMode.MERGE.value == "merge"
        assert RestoreMode.PREVIEW.value == "preview"
