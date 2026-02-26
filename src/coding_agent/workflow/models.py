from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class WorkflowVariable:
    name: str
    required: bool = False
    default: str | None = None
    enum: list[str] | None = None


@dataclass
class WorkflowStep:
    id: str
    title: str
    description: str | None = None
    condition: str | None = None
    for_each: str | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)
    checkpoint: str | None = None
    confirm: bool = False
    skill: str | None = None
    on_failure: dict[str, Any] | None = None


@dataclass
class Workflow:
    name: str
    version: str = "1.0"
    description: str | None = None
    variables: dict[str, WorkflowVariable] = field(default_factory=dict)
    inputs: dict[str, dict] = field(default_factory=dict)
    steps: list[WorkflowStep] = field(default_factory=list)
    skill: str | None = None

    current_step: int = 0
    completed_steps: list[str] = field(default_factory=list)
    variables_values: dict[str, Any] = field(default_factory=dict)

    _source_path: Path | None = None

    def restore_state(self, state: "WorkflowState") -> None:
        """Restore workflow state from a saved state.
        
        Args:
            state: The WorkflowState to restore from
        """
        self.current_step = state.current_step
        self.completed_steps = state.completed_steps.copy()
        self.variables_values = state.variables.copy()

    def get_next_step(self) -> WorkflowStep | None:
        """Get the next uncompleted step.
        
        Returns:
            The next step to execute, or None if all steps are complete
        """
        for i, step in enumerate(self.steps):
            if step.id not in self.completed_steps:
                return step
        return None

    def get_progress(self) -> dict[str, Any]:
        """Get workflow progress information.
        
        Returns:
            Dict with progress details
        """
        total_steps = len(self.steps)
        completed = len(self.completed_steps)
        next_step = self.get_next_step()
        return {
            "total_steps": total_steps,
            "completed_steps": completed,
            "progress_percent": (completed / total_steps * 100) if total_steps > 0 else 0,
            "current_step_index": self.current_step,
            "next_step": next_step.id if next_step else None,
        }

    def is_complete(self) -> bool:
        """Check if all steps are completed.
        
        Returns:
            True if workflow is complete
        """
        return self.get_next_step() is None


@dataclass
class WorkflowState:
    workflow_name: str
    current_step: int
    completed_steps: list[str]
    variables: dict[str, Any]
    started_at: str
    updated_at: str
    output_dir: Path | None = None
