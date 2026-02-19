"""Slash command system for CLI."""

from typing import TYPE_CHECKING, Callable
from urllib.error import URLError
from socket import timeout as socket_timeout

import litellm
from prompt_toolkit.completion import Completer, Completion
from rich.table import Table

from coding_agent.conversation import ConversationManager
from coding_agent.llm import LLMClient
from coding_agent.project_instructions import find_git_root
from coding_agent.renderer import Renderer
from coding_agent.session import SessionManager

if TYPE_CHECKING:
    from coding_agent.agent import Agent


class SlashCommand:
    """Represents a slash command."""

    def __init__(self, name: str, handler: Callable, help_text: str, arg_required: bool = False):
        self.name = name
        self.handler = handler
        self.help_text = help_text
        self.arg_required = arg_required


def cmd_help(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """Show help message."""
    table = Table(title="Available Commands", show_header=True, header_style="bold cyan")
    table.add_column("Command", style="cyan")
    table.add_column("Description")

    for cmd in COMMANDS.values():
        name = f"/{cmd.name}"
        if cmd.arg_required:
            name += " <arg>"
        table.add_row(name, cmd.help_text)

    renderer.console.print(table)
    return True


def cmd_clear(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """Clear conversation history."""
    conversation.clear()
    renderer.print_success("Conversation cleared.")
    return True


def cmd_compact(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """Trigger conversation truncation."""
    conversation.truncate_if_needed(max_tokens=64000)
    renderer.print_success("Conversation compacted.")
    return True


def cmd_sessions(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """List saved sessions."""
    sessions = session_manager.list()

    if not sessions:
        renderer.print_info("No saved sessions.")
        return True

    table = Table(title="Saved Sessions", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Title", style="cyan")
    table.add_column("Date")
    table.add_column("Tokens", justify="right")
    table.add_column("Model")

    for i, session in enumerate(sessions, 1):
        title = session.get("title", "Untitled")
        date = session.get("updated_at", "Unknown")[:10]
        token_count = str(session.get("token_count", 0))
        model = session.get("model", "Unknown")
        table.add_row(str(i), title, date, token_count, model)

    renderer.console.print(table)
    return True


def cmd_exit(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """Exit the session."""
    renderer.print_info("Goodbye!")
    return False


def cmd_model(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """Switch to a different model."""
    if not args:
        renderer.print_error("Command /model requires an argument.")
        return True

    if llm_client is None:
        renderer.print_error("Model switching is not available in this context.")
        return True

    model_name = args.strip()

    # Validate the model by making a test completion call
    # Note: litellm.validate_model() does not exist - using test completion instead
    try:
        litellm.completion(
            model=model_name,
            messages=[{"role": "user", "content": "ping"}],
            api_base=llm_client.api_base,
            api_key=llm_client.api_key,
            max_tokens=1,
            timeout=10,
        )
    except (URLError, socket_timeout, TimeoutError):
        renderer.print_error(f"Error: Model '{model_name}' validation timed out. Please try again.")
        return True
    except Exception as e:
        # Use generic error message to avoid exposing sensitive info (API keys, rate limits, etc.)
        renderer.print_error(f"Error: Model '{model_name}' is not available or not accessible.")
        return True

    # Model is valid - switch to it
    llm_client.model = model_name
    renderer.print_success(f"Switched to model: {model_name}")
    return True


_AGENTS_MD_TEMPLATE = """\
# AGENTS.md - Agent Instructions

## Project Overview

_Describe your project here._

## Architecture

_Describe the key components and their relationships._

## Build & Test

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run the app
your-cli-command
```

## Code Style

_Describe coding conventions and preferences._

## Important Notes

_Special instructions for the agent, e.g., files to avoid, patterns to follow._
"""


def cmd_init(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """Create an AGENTS.md template in the current project root."""
    from pathlib import Path

    git_root = find_git_root()
    target_dir = git_root if git_root else Path.cwd()
    agents_md = target_dir / "AGENTS.md"

    if agents_md.exists():
        renderer.print_error(f"AGENTS.md already exists at {agents_md}")
        return True

    try:
        agents_md.write_text(_AGENTS_MD_TEMPLATE, encoding="utf-8")
        renderer.print_success(f"Created AGENTS.md at {agents_md}")
    except OSError as e:
        renderer.print_error(f"Failed to create AGENTS.md: {e}")

    return True


COMMANDS: dict[str, SlashCommand] = {
    "help": SlashCommand("help", cmd_help, "Show help message", False),
    "clear": SlashCommand("clear", cmd_clear, "Clear conversation history", False),
    "compact": SlashCommand("compact", cmd_compact, "Manually trigger conversation truncation", False),
    "sessions": SlashCommand("sessions", cmd_sessions, "List saved sessions", False),
    "model": SlashCommand("model", cmd_model, "Switch to a different model", True),
    "init": SlashCommand("init", cmd_init, "Create AGENTS.md template in project root", False),
    "exit": SlashCommand("exit", cmd_exit, "Exit the session", False),
}


def register_skills(skills: dict[str, str], agent: "Agent") -> list[str]:
    """Register skills from SKILL.md as dynamic slash commands.

    Each skill becomes a slash command that runs its instructions through
    the agent. Project skills override built-in commands with the same name.

    Args:
        skills: Mapping of skill name to instruction content.
        agent: Agent instance used to execute skill prompts.

    Returns:
        List of registered skill names.
    """
    registered: list[str] = []

    for name, content in skills.items():
        if not name:
            continue

        # Capture skill content in a closure
        def _make_handler(skill_content: str):
            def handler(
                args: str,
                conversation: ConversationManager,
                session_manager: SessionManager,
                renderer: Renderer,
                llm_client: LLMClient | None = None,
                _agent: "Agent | None" = None,
            ) -> bool:
                prompt = skill_content
                if args:
                    prompt = f"{skill_content}\n\nAdditional context: {args}"
                effective_agent = _agent or agent
                if effective_agent is None:
                    renderer.print_error("No agent available to run skill.")
                    return True
                effective_agent.run(prompt)
                return True
            return handler

        COMMANDS[name] = SlashCommand(
            name=name,
            handler=_make_handler(content),
            help_text=f"[skill] {content[:60].splitlines()[0] if content else name}",
            arg_required=False,
        )
        registered.append(name)

    return registered


class SlashCommandCompleter(Completer):
    """Autocomplete for slash commands in prompt-toolkit."""

    def get_completions(self, document, complete_event):
        """Yield completions when input starts with '/'."""
        text = document.text_before_cursor

        if not text.startswith("/"):
            return

        # Extract the partial command name (strip leading '/')
        partial = text[1:]

        for name, cmd in COMMANDS.items():
            if name.startswith(partial):
                yield Completion(
                    name,
                    start_position=-len(partial),
                    display_meta=cmd.help_text,
                )


def is_slash_command(text: str) -> bool:
    """Check if input is a slash command."""
    return text.strip().startswith("/")


def parse_command(text: str) -> tuple[str, str]:
    """Parse command name and arguments from input.

    Returns:
        Tuple of (command_name, arguments)
    """
    text = text.strip()
    if not text.startswith("/"):
        return "", ""

    parts = text[1:].split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    return command, args


def execute_command(
    text: str,
    conversation: ConversationManager,
    session_manager: SessionManager,
    renderer: Renderer,
    llm_client: LLMClient | None = None,
    agent: "Agent | None" = None,
) -> bool | None:
    """Execute a slash command if the input is one.

    Args:
        text: User input
        conversation: ConversationManager instance
        session_manager: SessionManager instance
        renderer: Renderer instance
        llm_client: LLMClient instance (optional, for commands that need it)
        agent: Agent instance (optional, required for skill commands)

    Returns:
        True if command executed and session should continue
        False if command executed and session should exit
        None if input is not a slash command
    """
    if not is_slash_command(text):
        return None

    command_name, args = parse_command(text)

    if command_name not in COMMANDS:
        renderer.print_error(f"Unknown command: /{command_name}. Type /help for available commands.")
        return True

    cmd = COMMANDS[command_name]

    if cmd.arg_required and not args:
        renderer.print_error(f"Command /{command_name} requires an argument.")
        return True

    return cmd.handler(args, conversation, session_manager, renderer, llm_client, agent)
