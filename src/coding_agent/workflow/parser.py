import re
from pathlib import Path
from typing import Any

import yaml

from coding_agent.workflow.models import Workflow, WorkflowStep, WorkflowVariable


def parse_workflow(yaml_path: Path) -> Workflow:
    """Parse YAML file into Workflow object."""
    content = yaml_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    variables = {}
    for name, config in data.get("variables", {}).items():
        if isinstance(config, str):
            variables[name] = WorkflowVariable(
                name=name,
                required=config == "required",
            )
        else:
            variables[name] = WorkflowVariable(
                name=name,
                required=config.get("required", False),
                default=config.get("default"),
                enum=config.get("enum"),
            )

    steps = []
    for step_data in data.get("steps", []):
        step = WorkflowStep(
            id=step_data["id"],
            title=step_data["title"],
            description=step_data.get("description"),
            condition=step_data.get("if"),
            for_each=step_data.get("for_each"),
            actions=step_data.get("actions", []),
            checkpoint=step_data.get("checkpoint"),
            confirm=step_data.get("confirm", False),
            skill=step_data.get("skill"),
            on_failure=step_data.get("on_failure"),
        )
        steps.append(step)

    return Workflow(
        name=data["name"],
        version=data.get("version", "1.0"),
        description=data.get("description"),
        variables=variables,
        inputs=data.get("inputs", {}),
        steps=steps,
        skill=data.get("skill"),
    )


def validate_workflow(workflow: Workflow) -> list[str]:
    """Validate workflow structure. Returns list of errors."""
    errors = []

    if not workflow.name:
        errors.append("Workflow must have a name")

    if not workflow.steps:
        errors.append("Workflow must have at least one step")

    step_ids = [s.id for s in workflow.steps]
    if len(step_ids) != len(set(step_ids)):
        errors.append("Step IDs must be unique")

    return errors
