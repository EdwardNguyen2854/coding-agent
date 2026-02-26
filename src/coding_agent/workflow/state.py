import json
from datetime import datetime
from pathlib import Path

from coding_agent.workflow.models import WorkflowState, Workflow


class StateManager:
    """Manage workflow state persistence."""

    STATE_DIR = Path.home() / ".coding-agent" / "workflows" / ".state"

    def __init__(self):
        self.STATE_DIR.mkdir(parents=True, exist_ok=True)

    def _state_file(self, workflow_name: str) -> Path:
        """Get state file path for workflow."""
        safe_name = workflow_name.replace("/", "_").replace("\\", "_")
        return self.STATE_DIR / f"{safe_name}.json"

    def save_state(
        self,
        workflow: Workflow,
        output_dir: Path | None = None,
        session_id: str | None = None,
    ) -> None:
        """Save current workflow state.
        
        Args:
            workflow: The workflow to save
            output_dir: Optional output directory for workflow artifacts
            session_id: Optional session ID for session continuation
        """
        state = WorkflowState(
            workflow_name=workflow.name,
            current_step=workflow.current_step,
            completed_steps=workflow.completed_steps,
            variables=workflow.variables_values,
            started_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            output_dir=output_dir,
        )
        
        extra_data = {"session_id": session_id} if session_id else {}

        state_file = self._state_file(workflow.name)
        state_data = state.__dict__.copy()
        state_data.update(extra_data)
        state_file.write_text(
            json.dumps(state_data, indent=2, default=str),
            encoding="utf-8"
        )

    def load_state(self, workflow_name: str) -> WorkflowState | None:
        """Load saved workflow state."""
        state_file = self._state_file(workflow_name)

        if not state_file.exists():
            return None

        data = json.loads(state_file.read_text(encoding="utf-8"))
        return WorkflowState(**data)

    def load_state_with_session(self, workflow_name: str) -> tuple[WorkflowState | None, str | None]:
        """Load saved workflow state and return session_id if available.
        
        Args:
            workflow_name: Name of the workflow
            
        Returns:
            Tuple of (WorkflowState, session_id) - session_id may be None
        """
        state_file = self._state_file(workflow_name)

        if not state_file.exists():
            return None, None

        data = json.loads(state_file.read_text(encoding="utf-8"))
        session_id = data.pop("session_id", None)
        return WorkflowState(**data), session_id

    def clear_state(self, workflow_name: str) -> None:
        """Clear workflow state."""
        state_file = self._state_file(workflow_name)
        if state_file.exists():
            state_file.unlink()

    def list_incomplete(self) -> list[WorkflowState]:
        """List all incomplete workflows."""
        states = []
        for state_file in self.STATE_DIR.glob("*.json"):
            try:
                state = WorkflowState(**json.loads(state_file.read_text()))
                states.append(state)
            except Exception:
                continue
        return states
