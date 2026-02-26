from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class WorkflowRegistryEntry:
    name: str
    description: str
    type: str
    entry: str


class WorkflowRegistry:
    """Load and manage workflow registry."""

    def __init__(self, workflows_dir: Path):
        self.workflows_dir = workflows_dir
        self._entries: list[WorkflowRegistryEntry] | None = None

    def _registry_path(self) -> Path:
        return self.workflows_dir / "registry" / "registry.yaml"

    def load(self) -> list[WorkflowRegistryEntry]:
        """Load all workflow registry entries."""
        if self._entries is not None:
            return self._entries

        registry_path = self._registry_path()
        if not registry_path.exists():
            return []

        data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        if not data or "workflows" not in data:
            return []

        self._entries = [
            WorkflowRegistryEntry(
                name=w["name"],
                description=w.get("description", ""),
                type=w.get("type", "yaml"),
                entry=w["entry"],
            )
            for w in data["workflows"]
        ]
        return self._entries

    def get(self, name: str) -> WorkflowRegistryEntry | None:
        """Get a specific workflow entry by name."""
        for entry in self.load():
            if entry.name == name:
                return entry
        return None

    def list_names(self) -> list[str]:
        """List all available workflow names."""
        return [entry.name for entry in self.load()]
