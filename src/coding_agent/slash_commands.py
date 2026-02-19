"""Slash command system for CLI."""

import click
from typing import Callable
from urllib.error import URLError
from socket import timeout as socket_timeout

import litellm

from coding_agent.conversation import ConversationManager
from coding_agent.llm import LLMClient
from coding_agent.renderer import Renderer
from coding_agent.session import SessionManager


class SlashCommand:
    """Represents a slash command."""
    
    def __init__(self, name: str, handler: Callable, help_text: str, arg_required: bool = False):
        self.name = name
        self.handler = handler
        self.help_text = help_text
        self.arg_required = arg_required


def cmd_help(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None) -> bool:
    """Show help message."""
    help_text = """
Available commands:
  /help              Show this help message
  /clear             Clear conversation history (preserves system prompt)
  /compact           Manually trigger conversation truncation
  /sessions          List saved sessions
  /model <name>      Switch to a different model
  /exit              Exit the session

Type /help for this message at any time.
""".strip()
    click.echo(help_text)
    return True


def cmd_clear(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None) -> bool:
    """Clear conversation history."""
    conversation.clear()
    click.echo(click.style("Conversation cleared.", fg="green"))
    return True


def cmd_compact(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None) -> bool:
    """Trigger conversation truncation."""
    conversation.truncate_if_needed(max_tokens=64000)
    click.echo(click.style("Conversation compacted.", fg="green"))
    return True


def cmd_sessions(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None) -> bool:
    """List saved sessions."""
    sessions = session_manager.list()
    
    if not sessions:
        click.echo(click.style("No saved sessions.", fg="yellow"))
        return True
    
    click.echo("Saved sessions:")
    for i, session in enumerate(sessions, 1):
        title = session.get("title", "Untitled")
        date = session.get("updated_at", "Unknown")[:10]
        msg_count = session.get("token_count", 0)
        model = session.get("model", "Unknown")
        click.echo(f"  {i}. {title}")
        click.echo(f"     Date: {date} | Messages: ~{msg_count} tokens | Model: {model}")
    
    return True


def cmd_exit(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None) -> bool:
    """Exit the session."""
    click.echo(click.style("Goodbye!", fg="cyan"))
    return False


def cmd_model(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None) -> bool:
    """Switch to a different model."""
    if not args:
        click.echo(click.style("Command /model requires an argument.", fg="red"))
        return True

    if llm_client is None:
        click.echo(click.style("Model switching is not available in this context.", fg="red"))
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
        click.echo(click.style(f"Error: Model '{model_name}' validation timed out. Please try again.", fg="red"))
        return True
    except Exception as e:
        # Use generic error message to avoid exposing sensitive info (API keys, rate limits, etc.)
        click.echo(click.style(f"Error: Model '{model_name}' is not available or not accessible.", fg="red"))
        return True

    # Model is valid - switch to it
    llm_client.model = model_name
    click.echo(click.style(f"Switched to model: {model_name}", fg="green"))
    return True


COMMANDS: dict[str, SlashCommand] = {
    "help": SlashCommand("help", cmd_help, "Show help message", False),
    "clear": SlashCommand("clear", cmd_clear, "Clear conversation history", False),
    "compact": SlashCommand("compact", cmd_compact, "Manually trigger conversation truncation", False),
    "sessions": SlashCommand("sessions", cmd_sessions, "List saved sessions", False),
    "model": SlashCommand("model", cmd_model, "Switch to a different model", True),
    "exit": SlashCommand("exit", cmd_exit, "Exit the session", False),
}


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
) -> bool | None:
    """Execute a slash command if the input is one.
    
    Args:
        text: User input
        conversation: ConversationManager instance
        session_manager: SessionManager instance
        renderer: Renderer instance
        llm_client: LLMClient instance (optional, for commands that need it)
        
    Returns:
        True if command executed and session should continue
        False if command executed and session should exit
        None if input is not a slash command
    """
    if not is_slash_command(text):
        return None
    
    command_name, args = parse_command(text)
    
    if command_name not in COMMANDS:
        click.echo(click.style(f"Unknown command: /{command_name}. Type /help for available commands.", fg="red"))
        return True
    
    cmd = COMMANDS[command_name]
    
    if cmd.arg_required and not args:
        click.echo(click.style(f"Command /{command_name} requires an argument.", fg="red"))
        return True
    
    return cmd.handler(args, conversation, session_manager, renderer, llm_client)
