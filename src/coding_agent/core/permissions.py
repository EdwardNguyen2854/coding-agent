"""Permission system for tool execution approval."""

import re
from pathlib import Path

_MAX_PARAM_DISPLAY = 120


def _fmt_params(params: dict) -> str:
    """Format params dict with long values truncated for display."""
    parts = []
    for k, v in params.items():
        v_str = str(v)
        if len(v_str) > _MAX_PARAM_DISPLAY:
            v_str = v_str[:_MAX_PARAM_DISPLAY] + f"... ({len(v_str)} chars)"
        parts.append(f"{k}={v_str!r}")
    return "{" + ", ".join(parts) + "}"


DESTRUCTIVE_PATTERNS = [
    r"\brm\s+(-\w*r\w*f|-\w*f\w*r)\b",  # rm -rf, rm -fr and variants
    r"\brm\s+-r\b",                        # rm -r (recursive without force)
    r"\brmdir\b.*(/s|/q)",                 # Windows rmdir /s or /q (any order)
    r"\bdel\b.*(/s|/q)",                   # Windows del /s or /q (any order)
    r"\brd\b.*(/s|/q)",                    # Windows rd /s or /q (any order)
    r"\bformat\b\s+\w",                    # format <drive>
    r"\bmkfs\b",                           # mkfs (create filesystem)
    r"\bshred\b",                          # shred (secure delete)
    r">\s*/dev/(?!null\b|zero\b)",         # redirect to /dev/ except /dev/null, /dev/zero
    r"\bdd\b.*\bif=",                      # dd if= (disk duplicate)
]

TOOLS_REQUIRING_APPROVAL = {"file_write", "file_edit", "shell"}


class PermissionSystem:
    """System for checking user approval before tool execution."""

    def __init__(self, renderer=None, auto_allow: bool = False):
        """Initialize permission system.

        Args:
            renderer: Optional renderer for console output
            auto_allow: If True, automatically approve tool executions
        """
        self.renderer = renderer
        self.approved_operations = {}
        self.auto_allow = auto_allow
        self._prompt_callback = None
        self._tool_overrides: list[set[str]] = []

    def set_prompt_callback(self, callback) -> None:
        """Set a callback for async prompting in TUI context.

        Args:
            callback: Async function that takes (tool_name, params, is_warning)
                     and returns True/False for approval
        """
        self._prompt_callback = callback

    def set_auto_allow(self, enabled: bool) -> None:
        """Enable or disable auto-allow mode."""
        self.auto_allow = enabled

    def is_auto_allow_enabled(self) -> bool:
        """Check if auto-allow mode is enabled."""
        return self.auto_allow

    def push_allowed_tools(self, tools: list[str]) -> None:
        """Temporarily allow tools without approval (stack-based).

        Args:
            tools: Tool names to allow without prompting.
        """
        self._tool_overrides.append(set(tools))

    def pop_allowed_tools(self) -> None:
        """Remove the most recent allowed-tools override frame."""
        if self._tool_overrides:
            self._tool_overrides.pop()

    def check_approval(self, tool_name: str, params: dict) -> bool:
        """Check if user approves this tool execution.

        Args:
            tool_name: Name of the tool to execute
            params: Parameters for the tool

        Returns:
            True if approved, False if denied
        """
        if self.auto_allow:
            return True

        # Skill-scoped tool allowlist
        if any(tool_name in frame for frame in self._tool_overrides):
            return True

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
        if self._prompt_callback:
            return self._prompt_callback(tool_name, params, False)

        prompt_text = f"\nAllow {tool_name}? [Y/n]: "
        try:
            response = input(prompt_text).strip().lower()
        except EOFError:
            return False
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
            self.renderer.print_warning("  ⚠  destructive command — review carefully")
        else:
            print("\n⚠️  WARNING: This command may delete or overwrite files!")

        if self._prompt_callback:
            return self._prompt_callback(tool_name, params, True)

        prompt_text = f"Allow {tool_name}? [y/N]: "
        try:
            response = input(prompt_text).strip().lower()
        except EOFError:
            return False
        if response in ("y", "yes"):
            return True
        return False

    def _get_approval_key(self, tool_name: str, params: dict) -> str:
        """Generate approval key for session memory.

        Keys are intentionally exact so that approving one operation does not
        implicitly pre-approve broader operations.  For example, approving
        ``git status`` does not pre-approve ``git push``, and approving an edit
        to ``src/foo.py`` does not pre-approve edits to ``src/bar.py``.

        Args:
            tool_name: Name of the tool
            params: Tool parameters

        Returns:
            Approval key string
        """
        if tool_name == "shell":
            command = params.get("command", "").strip()
            return f"shell:{command}" if command else "shell:unknown"

        if tool_name in ("file_write", "file_edit"):
            path = params.get("path", "")
            if path:
                return f"{tool_name}:{Path(path).resolve()}"

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
