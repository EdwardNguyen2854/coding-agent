from importlib.resources import files
from pathlib import Path

from coding_agent.workflow.models import Workflow
from coding_agent.workflow.parser import parse_workflow, validate_workflow
from coding_agent.workflow.registry import WorkflowRegistry, WorkflowRegistryEntry
from coding_agent.workflow.native_loader import NativeWorkflowLoader


def _get_package_workflow_dir() -> Path | None:
    """Get the workflows directory from the installed package."""
    try:
        pkg = files("coding_agent")
        wf_dir = pkg / "workflows"
        if wf_dir.is_dir():
            return Path(str(wf_dir))
    except Exception:
        pass
    return None


WORKFLOW_DIRS = [
    Path.cwd() / "workflows",
    Path.home() / ".coding-agent" / "workflows",
    _get_package_workflow_dir(),
]


def _get_registry(workflows_dir: Path) -> WorkflowRegistry:
    """Get workflow registry for a workflows directory."""
    return WorkflowRegistry(workflows_dir)


def _get_native_loader(workflows_dir: Path) -> NativeWorkflowLoader:
    """Get native workflow loader for a workflows directory."""
    return NativeWorkflowLoader(workflows_dir)


def _find_workflow_in_dirs(name: str) -> Path | None:
    """Find workflow file by name in workflow directories."""
    for dir_path in WORKFLOW_DIRS:
        if not dir_path.exists():
            continue

        wf_file = dir_path / f"{name}.yaml"
        if wf_file.exists():
            return wf_file

        wf_file = dir_path / "examples" / f"{name}.yaml"
        if wf_file.exists():
            return wf_file

    return None


def find_workflow(name: str) -> Path | None:
    """Find workflow file by name.
    
    First checks for directory-based native workflows,
    then checks the registry, then falls back to direct file lookup.
    """
    for dir_path in WORKFLOW_DIRS:
        if not dir_path.exists():
            continue

        native_loader = _get_native_loader(dir_path)
        if native_loader.workflow_exists(name):
            return dir_path / name / "workflow.yaml"

        registry = _get_registry(dir_path)
        entry = registry.get(name)
        if entry:
            wf_file = dir_path / entry.entry
            if wf_file.exists():
                return wf_file

    return _find_workflow_in_dirs(name)


def load_workflow(name: str) -> Workflow | None:
    """Load workflow by name.
    
    First tries to load from directory-based native workflow,
    then falls back to registry and file lookup.
    """
    for dir_path in WORKFLOW_DIRS:
        if not dir_path.exists():
            continue

        native_loader = _get_native_loader(dir_path)
        workflow = native_loader.load_workflow(name)
        if workflow:
            return workflow

        wf_path = find_workflow(name)
        if wf_path:
            workflow = parse_workflow(wf_path)
            errors = validate_workflow(workflow)
            if errors:
                raise ValueError(f"Invalid workflow: {errors}")
            workflow._source_path = wf_path
            return workflow

    wf_path = find_workflow(name)
    if not wf_path:
        return None

    workflow = parse_workflow(wf_path)
    errors = validate_workflow(workflow)

    if errors:
        raise ValueError(f"Invalid workflow: {errors}")

    workflow._source_path = wf_path

    return workflow


def list_workflows() -> list[Workflow]:
    """List all available workflows."""
    workflows = []

    for dir_path in WORKFLOW_DIRS:
        if not dir_path.exists():
            continue

        native_loader = _get_native_loader(dir_path)
        for name in native_loader.get_available_workflows():
            try:
                workflow = native_loader.load_workflow(name)
                if workflow:
                    workflows.append(workflow)
            except Exception:
                continue

        registry = _get_registry(dir_path)
        for entry in registry.load():
            wf_file = dir_path / entry.entry
            if wf_file.exists():
                try:
                    workflow = parse_workflow(wf_file)
                    workflows.append(workflow)
                except Exception:
                    continue

        for wf_file in dir_path.glob("*.yaml"):
            try:
                workflow = parse_workflow(wf_file)
                workflows.append(workflow)
            except Exception:
                continue

        examples_dir = dir_path / "examples"
        if examples_dir.exists():
            for wf_file in examples_dir.glob("*.yaml"):
                try:
                    workflow = parse_workflow(wf_file)
                    workflows.append(workflow)
                except Exception:
                    continue

    return workflows
