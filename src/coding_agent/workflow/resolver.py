import os
import re
from pathlib import Path
from typing import Any

from coding_agent.workflow.models import Workflow


class VariableResolver:
    """Resolve variables in workflow strings."""

    def __init__(self, workflow: Workflow):
        self.workflow = workflow
        self.variables = workflow.variables_values.copy()

    def resolve(self, template: str) -> str:
        """Resolve {variable} references in template string."""
        pattern = r"\{([^}]+)\}"

        def replace(match: re.Match) -> str:
            var_name = match.group(1)
            return self.get(var_name, match.group(0))

        return re.sub(pattern, replace, template)

    def get(self, var_name: str, default: str | None = None) -> str:
        """Get variable value by name."""
        if var_name in self.variables:
            return str(self.variables[var_name])

        if var_name == "project-root":
            return str(Path.cwd())

        if var_name.startswith("env:"):
            env_var = var_name[4:]
            return os.environ.get(env_var, default or "")

        return default or f"{{{var_name}}}"

    def set(self, var_name: str, value: Any) -> None:
        """Set variable value."""
        self.variables[var_name] = value
        self.workflow.variables_values[var_name] = value

    def evaluate_condition(self, condition: str) -> bool:
        """Evaluate a condition string."""
        resolved = self.resolve(condition)

        if "==" in resolved:
            left, right = resolved.split("==", 1)
            return left.strip() == right.strip().strip("'\"")

        if "!=" in resolved:
            left, right = resolved.split("!=", 1)
            return left.strip() != right.strip().strip("'\"")

        return bool(resolved and resolved != "None")
