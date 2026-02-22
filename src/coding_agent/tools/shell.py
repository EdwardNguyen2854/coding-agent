"""Shell tool - execute shell commands."""

import platform
import subprocess
from pathlib import Path

from coding_agent.tools.base import ToolDefinition, ToolResult
from coding_agent.utils import truncate_output


DEFAULT_TIMEOUT = 120
MAX_OUTPUT_LENGTH = 30000

_cwd = Path.cwd()


def execute(params: dict) -> ToolResult:
    """Execute a shell command.

    Args:
        params: Dict with 'command' (required), 'timeout' (optional)

    Returns:
        ToolResult with command output
    """
    global _cwd

    command = params.get("command", "")
    timeout = params.get("timeout", DEFAULT_TIMEOUT)

    if not command:
        return ToolResult(output="", error="Command is required", is_error=True)

    command_stripped = command.strip()

    is_cd_command = (
        command_stripped.startswith("cd ") or
        command_stripped == "cd" or
        command_stripped.startswith("cd/") or
        command_stripped.startswith("cd\\")
    )

    if is_cd_command:
        if command_stripped in ("cd", "cd/", "cd\\"):
            return ToolResult(output=str(_cwd), error=None, is_error=False)

        if command_stripped.startswith("cd "):
            new_dir = command_stripped[3:].strip()
        elif command_stripped.startswith("cd/"):
            new_dir = command_stripped[3:]
        else:
            new_dir = command_stripped[2:]

        if not new_dir:
            return ToolResult(output=str(_cwd), error=None, is_error=False)

        try:
            target_path = _cwd / new_dir
            target_path = target_path.resolve()

            if not target_path.exists():
                return ToolResult(output="", error=f"cd: no such directory: {target_path}", is_error=True)

            if not target_path.is_dir():
                return ToolResult(output="", error=f"cd: not a directory: {target_path}", is_error=True)

            _cwd = target_path
            return ToolResult(output=str(_cwd), error=None, is_error=False)
        except Exception as e:
            return ToolResult(output="", error=f"cd failed: {str(e)}", is_error=True)

    if platform.system() == "Windows":
        shell_cmd = ["cmd", "/c", command]
    else:
        shell_cmd = ["bash", "-c", command]

    try:
        result = subprocess.run(
            shell_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(_cwd),
        )

        output = result.stdout
        if result.stderr:
            if output:
                output += "\n[stderr]\n" + result.stderr
            else:
                output = result.stderr

        output = truncate_output(output, MAX_OUTPUT_LENGTH)

        return ToolResult(output=output, error=None, is_error=False)

    except subprocess.TimeoutExpired:
        return ToolResult(output="", error=f"Command timed out after {timeout} seconds", is_error=True)
    except FileNotFoundError:
        shell_name = "cmd" if platform.system() == "Windows" else "bash"
        return ToolResult(output="", error=f"Shell '{shell_name}' not found", is_error=True)
    except Exception as e:
        return ToolResult(output="", error=str(e), is_error=True)


definition = ToolDefinition(
    name="shell",
    description="Execute a shell command in the terminal",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "number", "description": "Timeout in seconds (default 120)", "default": 120},
        },
        "required": ["command"],
    },
    handler=execute,
)
