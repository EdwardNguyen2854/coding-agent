from pathlib import Path

from coding_agent.workflow.models import WorkflowStep
from coding_agent.workflow.resolver import VariableResolver


class CheckpointManager:
    """Manage workflow checkpoints."""

    def __init__(self, resolver: VariableResolver, output_dir: Path):
        self.resolver = resolver
        self.output_dir = output_dir

    async def save(self, step: WorkflowStep, content: str) -> Path:
        """Save checkpoint content to file."""
        path_template = step.checkpoint
        path_str = self.resolver.resolve(path_template)
        file_path = self.output_dir / path_str.lstrip("/")

        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(content, encoding="utf-8")

        return file_path

    async def load(self, step: WorkflowStep) -> str | None:
        """Load checkpoint content if exists."""
        path_template = step.checkpoint
        path_str = self.resolver.resolve(path_template)
        file_path = self.output_dir / path_str.lstrip("/")

        if file_path.exists():
            return file_path.read_text(encoding="utf-8")

        return None
