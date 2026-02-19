"""Permission system for tool execution approval."""

import re
from pathlib import Path

from prompt_toolkit import prompt as pt_prompt


DESTRUCTIVE_PATTERNS = [
    r"rm\s+-rf\s+",
    r"rm\s+-r\s+",
    r"rmdir\s+/s\s+/q",
    r"del\s+/s\s+/q",
    r"rd\s+/s\s+/q",
    r"format\s+",
    r"mkfs",
    r"shred",
    r">\s*/dev/",
    r"dd\s+if=",
]

TOOLS_REQUIRING_APPROVAL = {"file_write", "file_edit", "shell"}


class PermissionSystem:
    """System for checking user approval before tool execution."""

    def __init__(self, renderer=None):
        """Initialize permission system.

        Args:
            renderer: Optional renderer for console output
        """
        self.renderer = renderer
        self.approved_operations = {}

    def check_approval(self, tool_name: str, params: dict) -> bool:
        """Check if user approves this tool execution.

        Args:
            tool_name: Name of the tool to execute
            params: Parameters for the tool

        Returns:
            True if approved, False if denied
        """
        if tool_name not in TOOLS_REQUIRING_APPROVAL:
            return True

        if tool_name == "shell":
            command = params.get("command", "")
            if self._is_destructive(command):
                return self._prompt_with_warning(tool_name, params)

        approval_key = self._get_approval_key(tool_name, params)
        if approval_key in self.approved_operations:
            return True

        return self._prompt_user(tool_name, params)

    def _is_destructive(self, command: str) -> bool:
        """Check if command is potentially destructive.

        Args:
            command: Shell command to check

        Returns:
            True if command is potentially destructive
        """
        command_lower = command.lower()
        for pattern in DESTRUCTIVE_PATTERNS:
            if re.search(pattern, command_lower):
                return True
        return False

    def _prompt_user(self, tool_name: str, params: dict) -> bool:
        """Prompt user for approval.

        Args:
            tool_name: Name of the tool
            params: Tool parameters

        Returns:
            True if approved (Y), False if denied (N)
        """
        if self.renderer:
            self.renderer.print_info(f"\nTool: {tool_name}")
            self.renderer.print_info(f"Parameters: {params}")

        styled_prompt = [
            ("ansibrightcyan", f"Allow {tool_name}? "),
            ("", "[Y/n]: "),
        ]
        try:
            response = pt_prompt(styled_prompt).strip().lower()
        except Exception:
            response = input(f"Allow {tool_name}? [Y/n]: ").strip().lower()
        if response in ("", "y", "yes"):
            self.approve(tool_name, params)
            return True
        return False

    def _prompt_with_warning(self, tool_name: str, params: dict) -> bool:
        """Prompt user with destructive warning.

        Args:
            tool_name: Name of the tool
            params: Tool parameters

        Returns:
            True if approved (Y), False if denied (N)
        """
        if self.renderer:
            self.renderer.print_error("\n⚠️  WARNING: Potentially destructive command!")
            self.renderer.print_error(f"Tool: {tool_name}")
            self.renderer.print_error(f"Parameters: {params}")
        else:
            print("\n⚠️  WARNING: This command may delete or overwrite files!")

        styled_prompt = [
            ("ansired bold", f"Allow {tool_name}? "),
            ("ansibrightcyan", "[Y/n]: "),
        ]
        try:
            response = pt_prompt(styled_prompt).strip().lower()
        except Exception:
            response = input(f"Allow {tool_name}? [Y/n]: ").strip().lower()
        if response in ("", "y", "yes"):
            return True
        return False

    def _get_approval_key(self, tool_name: str, params: dict) -> str:
        """Generate approval key for session memory.

        Args:
            tool_name: Name of the tool
            params: Tool parameters

        Returns:
            Approval key string
        """
        if tool_name == "shell":
            command = params.get("command", "")
            parts = command.split()
            if parts:
                return f"shell:{parts[0]}"
            return "shell:unknown"

        if tool_name in ("file_write", "file_edit"):
            path = params.get("path", "")
            if path:
                return f"{tool_name}:{Path(path).parent}"

        return f"{tool_name}:default"

    def approve(self, tool_name: str, params: dict) -> None:
        """Remember this approval for session.

        Args:
            tool_name: Name of the tool
            params: Tool parameters
        """
        approval_key = self._get_approval_key(tool_name, params)
        self.approved_operations[approval_key] = True

    def clear(self) -> None:
        """Clear session memory (call on session end)."""
        self.approved_operations = {}
