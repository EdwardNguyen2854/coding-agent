"""Coding-Agent CLI entry point."""

import os
import sys

import click

# --- Early init: truststore + proxy must be set before importing litellm/openai/httpx ---
try:
    import truststore
    truststore.inject_into_ssl()
    click.echo("truststore: using OS certificate store")
except Exception:
    pass

from coding_agent.config import load_config
_early_config = None
try:
    _early_config = load_config()
    if _early_config.https_proxy:
        os.environ["HTTPS_PROXY"] = _early_config.https_proxy
        os.environ["HTTP_PROXY"] = _early_config.https_proxy
except Exception:
    pass
# --- End early init ---

from prompt_toolkit import PromptSession

from coding_agent.agent import Agent
from coding_agent.config import ConfigError, apply_cli_overrides
from coding_agent.conversation import ConversationManager
from coding_agent.llm import LLMClient
from coding_agent.project_instructions import get_enhanced_system_prompt
from coding_agent.renderer import Renderer
from coding_agent.session import SessionManager
from coding_agent.slash_commands import execute_command
from coding_agent.system_prompt import SYSTEM_PROMPT

import litellm
litellm.suppress_debug_info = True

__version__ = "0.3.2"

USER_PROMPT = "You   > "


def print_banner() -> None:
    """Print the EMN Coding Agent banner."""
    os.environ["LITELLM_NO_PROVIDER_LIST"] = "1"

    banner = f"""
██████ ███╗   ███╗███╗   ██╗
██╔═══╝████╗ ████║████╗  ██║
████╗  ██╔████╔██║██╔██╗ ██║
██╔═╝  ██║╚██╔╝██║██║╚██╗██║
██████╗██║ ╚═╝ ██║██║ ╚████║
╚═════╝╚═╝     ╚═╝╚═╝  ╚═══╝

 ██████╗ ██████╗ ██████╗ ██╗███╗   ██╗ ██████╗       █████╗  ██████╗ ███████╗███╗   ██╗████████╗
██╔════╝██╔═══██╗██╔══██╗██║████╗  ██║██╔════╝      ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
██║     ██║   ██║██║  ██║██║██╔██╗ ██║██║  ███╗     ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
██║     ██║   ██║██║  ██║██║██║╚██╗██║██║   ██║     ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
 ██████╗╚██████╔╝██████╔╝██║██║ ╚████║╚██████╔╝     ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
 ╚═════╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝      ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝

v{__version__}
"""
    click.echo(click.style(banner, fg="cyan", bold=True))


def _restore_conversation(conversation: ConversationManager, messages: list[dict]) -> int:
    """Restore conversation messages from session data.
    
    Args:
        conversation: ConversationManager to populate
        messages: List of message dicts from session
        
    Returns:
        Number of non-system messages restored
    """
    for msg in messages:
        if msg.get("role") == "system":
            continue  # Skip system prompt, we use default
        elif msg.get("tool_calls"):
            conversation.add_assistant_tool_call(
                msg.get("content", ""),
                msg["tool_calls"]
            )
        elif msg.get("role") == "tool":
            conversation.add_tool_result(
                msg.get("tool_call_id", ""),
                msg.get("content", "")
            )
        else:
            conversation.add_message(msg["role"], msg.get("content", ""))
    
    return len([m for m in messages if m.get("role") != "system"])


DEFAULT_SYSTEM_PROMPT = SYSTEM_PROMPT


def _get_system_prompt() -> tuple[str, list[str]]:
    """Get system prompt with project instructions loaded lazily."""
    return get_enhanced_system_prompt(SYSTEM_PROMPT)


@click.command()
@click.option("--model", default=None, help="Override LLM model (e.g., litellm/gpt-4o)")
@click.option("--api-base", default=None, help="Override LiteLLM API base URL")
@click.option("--temperature", default=None, type=float, help="Override temperature (0.0-2.0)")
@click.option("--max-output-tokens", "max_output_tokens", default=None, type=int, help="Override max output tokens")
@click.option("--top-p", default=None, type=float, help="Override top_p (0.0-1.0)")
@click.option("--resume", is_flag=True, help="Resume the most recent session")
@click.option("--session", "session_id", default=None, help="Resume a specific session by ID")
def main(model: str | None, api_base: str | None, temperature: float | None, max_output_tokens: int | None, top_p: float | None, resume: bool, session_id: str | None) -> None:
    """AI coding agent - self-hosted, model-agnostic."""
    print_banner()

    try:
        config = load_config()
        config = apply_cli_overrides(
            config,
            model=model,
            api_base=api_base,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            top_p=top_p,
        )
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    click.echo(f"Model: {config.model}")
    click.echo(f"API:   {config.api_base}")
    if config.https_proxy:
        click.echo(f"Proxy: {config.https_proxy}")
    click.echo(f"Temp:  {config.temperature}")
    click.echo(f"MaxTok: {config.max_output_tokens}")
    click.echo(f"TopP:  {config.top_p}")
    click.echo("")
    
    try:
        llm_client = LLMClient(config)
        llm_client.verify_connection()
    except ConnectionError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    renderer = Renderer()
    renderer.print_info(f"Connected to LiteLLM")

    # Load project instructions lazily
    enhanced_prompt, loaded_files = _get_system_prompt()

    # Log loaded project instructions
    for path in loaded_files:
        click.echo(f"Loaded project instructions from: {path}")

    session_manager = SessionManager()
    session_data = None
    conversation = ConversationManager(enhanced_prompt)

    # Create Agent instance
    agent = Agent(llm_client, conversation, renderer)

    # Handle session resume
    if resume:
        loaded_session = session_manager.load_latest()
        if loaded_session:
            session_data = loaded_session
            msg_count = _restore_conversation(conversation, loaded_session.get("messages", []))
            click.echo(f"Resuming session: {loaded_session['title']} ({msg_count} messages)")
            agent.set_session(session_manager, session_data)
        else:
            click.echo(click.style("No previous sessions found. Starting a new session.", fg="yellow"))
    elif session_id:
        loaded_session = session_manager.load(session_id)
        if loaded_session:
            session_data = loaded_session
            msg_count = _restore_conversation(conversation, loaded_session.get("messages", []))
            click.echo(f"Resuming session: {loaded_session['title']} ({msg_count} messages)")
            agent.set_session(session_manager, session_data)
        else:
            click.echo(click.style(f"Session not found: {session_id}", fg="red"), err=True)
            sys.exit(1)

    click.echo(click.style("Type 'exit' to quit.\n", fg="green"))

    session = PromptSession()

    while True:
        try:
            text = session.prompt(USER_PROMPT)
        except KeyboardInterrupt:
            click.echo("\nUse Ctrl+D or type 'exit' to quit.")
            continue
        except EOFError:
            conversation.clear()
            break

        text = text.strip()
        if not text:
            continue
        
        # Check for slash commands
        should_continue = execute_command(text, conversation, session_manager, renderer, llm_client)
        if should_continue is False:
            break
        if should_continue is True:
            continue
        
        # Regular message - create session if needed
        if session_data is None:
            session_data = session_manager.create_session(
                first_message=text,
                model=config.model,
                messages=conversation.get_messages()
            )
            click.echo(f"Session created: {session_data['title']}")
            agent.set_session(session_manager, session_data)

        # Delegate to Agent for ReAct loop
        try:
            agent.run(text)
            # Show status line after response
            token_count = conversation._estimate_tokens() if hasattr(conversation, '_estimate_tokens') else None
            session_id = session_data.get("id") if session_data else None
            renderer.render_status_line(config.model, token_count, session_id)
        except ConnectionError as e:
            renderer.print_error(str(e))
