from __future__ import annotations

import gzip
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from coding_agent.checkpoint.models import Checkpoint, CheckpointSummary

_log = logging.getLogger(__name__)


class CheckpointStorage(ABC):
    @abstractmethod
    def save(self, checkpoint: Checkpoint) -> None:
        pass

    @abstractmethod
    def load(self, checkpoint_id: str) -> Checkpoint | None:
        pass

    @abstractmethod
    def list(self) -> list[CheckpointSummary]:
        pass

    @abstractmethod
    def delete(self, checkpoint_id: str) -> bool:
        pass

    @abstractmethod
    def cleanup(self, max_count: int, max_age_days: int) -> int:
        pass


class LocalCheckpointStorage(CheckpointStorage):
    def __init__(self, storage_dir: Path, compression: bool = True):
        self._storage_dir = storage_dir
        self._compression = compression
        self._metadata_file = storage_dir / "metadata.json"
        self._ensure_storage_dir()
        self._ensure_metadata()

    def _ensure_storage_dir(self) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_metadata(self) -> None:
        if not self._metadata_file.exists():
            self._metadata_file.write_text(json.dumps({"checkpoints": []}))

    def _read_metadata(self) -> dict[str, Any]:
        try:
            return json.loads(self._metadata_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"checkpoints": []}

    def _write_metadata(self, metadata: dict[str, Any]) -> None:
        self._metadata_file.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        return self._storage_dir / f"{checkpoint_id}.json"

    def save(self, checkpoint: Checkpoint) -> None:
        checkpoint_path = self._get_checkpoint_path(checkpoint.id)

        data = asdict(checkpoint)
        json_data = json.dumps(data, indent=2, ensure_ascii=False)

        if self._compression:
            with gzip.open(checkpoint_path, "wt", encoding="utf-8") as f:
                f.write(json_data)
        else:
            checkpoint_path.write_text(json_data, encoding="utf-8")

        metadata = self._read_metadata()
        summaries = metadata.get("checkpoints", [])
        summaries.append(CheckpointSummary.from_checkpoint(checkpoint).__dict__)
        metadata["checkpoints"] = summaries
        self._write_metadata(metadata)

        _log.info("Saved checkpoint %s to %s", checkpoint.id, checkpoint_path)

    def load(self, checkpoint_id: str) -> Checkpoint | None:
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)
        if not checkpoint_path.exists():
            return None

        try:
            if self._compression:
                with gzip.open(checkpoint_path, "rt", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = json.loads(checkpoint_path.read_text(encoding="utf-8"))

            return Checkpoint(**data)
        except (json.JSONDecodeError, OSError) as e:
            _log.error("Failed to load checkpoint %s: %s", checkpoint_id, e)
            return None

    def list(self) -> list[CheckpointSummary]:
        metadata = self._read_metadata()
        summaries = []
        for item in metadata.get("checkpoints", []):
            checkpoint_path = self._get_checkpoint_path(item.get("id", ""))
            if checkpoint_path.exists():
                summaries.append(CheckpointSummary(**item))
        return sorted(summaries, key=lambda s: s.timestamp, reverse=True)

    def delete(self, checkpoint_id: str) -> bool:
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)
        if not checkpoint_path.exists():
            return False

        checkpoint_path.unlink()

        metadata = self._read_metadata()
        summaries = [
            s for s in metadata.get("checkpoints", []) if s.get("id") != checkpoint_id
        ]
        metadata["checkpoints"] = summaries
        self._write_metadata(metadata)

        _log.info("Deleted checkpoint %s", checkpoint_id)
        return True

    def cleanup(self, max_count: int, max_age_days: int) -> int:
        deleted = 0
        summaries = self.list()

        if max_age_days > 0:
            cutoff = datetime.now() - timedelta(days=max_age_days)
            for summary in summaries[:]:
                try:
                    checkpoint_time = datetime.fromisoformat(summary.timestamp)
                    if checkpoint_time < cutoff:
                        if self.delete(summary.id):
                            deleted += 1
                except ValueError:
                    continue

        summaries = self.list()
        if len(summaries) > max_count:
            for summary in summaries[max_count:]:
                if self.delete(summary.id):
                    deleted += 1

        return deleted
