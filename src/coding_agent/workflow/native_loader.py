from pathlib import Path

from coding_agent.workflow.models import Workflow, WorkflowStep
from coding_agent.workflow.parser import parse_workflow, validate_workflow


class NativeWorkflowLoader:
    """Load native workflows from directory structure.
    
    Directory structure:
        workflows/
        ├── registry.yaml           # Workflow definitions
        ├── default/
        │   ├── workflow.yaml
        │   └── steps/
        ├── agile/
        │   ├── workflow.yaml
        │   └── steps/
        └── ...
    """

    def __init__(self, workflows_dir: Path):
        self.workflows_dir = workflows_dir

    def load_workflow(self, name: str) -> Workflow | None:
        """Load workflow from directory structure.
        
        Args:
            name: Workflow name (directory name)
            
        Returns:
            Workflow object or None if not found
        """
        workflow_dir = self.workflows_dir / name
        if not workflow_dir.is_dir():
            return None

        workflow_file = workflow_dir / "workflow.yaml"
        if not workflow_file.exists():
            return None

        workflow = parse_workflow(workflow_file)
        errors = validate_workflow(workflow)

        if errors:
            raise ValueError(f"Invalid workflow: {errors}")

        workflow._source_path = workflow_file

        self._load_step_prompts(workflow, workflow_dir)

        return workflow

    def _load_step_prompts(self, workflow: Workflow, workflow_dir: Path) -> None:
        """Load step prompt templates from steps directory.
        
        Args:
            workflow: The workflow to populate
            workflow_dir: The workflow directory
        """
        steps_dir = workflow_dir / "steps"
        if not steps_dir.is_dir():
            return

        for step in workflow.steps:
            prompt_file = steps_dir / f"{step.id}.md"
            if prompt_file.exists():
                step.description = prompt_file.read_text(encoding="utf-8").strip()

    def get_available_workflows(self) -> list[str]:
        """List all available workflow names from directory structure.
        
        Returns:
            List of workflow directory names
        """
        if not self.workflows_dir.exists():
            return []

        workflows = []
        for item in self.workflows_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                workflow_file = item / "workflow.yaml"
                if workflow_file.exists():
                    workflows.append(item.name)

        return workflows

    def workflow_exists(self, name: str) -> bool:
        """Check if a workflow exists.
        
        Args:
            name: Workflow name
            
        Returns:
            True if workflow exists
        """
        workflow_dir = self.workflows_dir / name
        return workflow_dir.is_dir() and (workflow_dir / "workflow.yaml").exists()
