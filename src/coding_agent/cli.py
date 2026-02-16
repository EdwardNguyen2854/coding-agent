"""Coding-Agent CLI entry point."""

import os

import sys

import click
from prompt_toolkit import PromptSession

from coding_agent.config import ConfigError, apply_cli_overrides, load_config
from coding_agent.conversation import ConversationManager
from coding_agent.llm import LLMClient
from coding_agent.renderer import Renderer
from coding_agent.system_prompt import SYSTEM_PROMPT

import litellm
litellm.suppress_debug_info = True


def print_banner() -> None:
    """Print the EMN Coding Agent banner."""
    import os
    os.environ["LITELLM_NO_PROVIDER_LIST"] = "1"
    
    banner = """
███████╗███╗   ███╗███╗   ██╗
██╔════╝████╗ ████║████╗  ██║
█████╗  ██╔████╔██║██╔██╗ ██║
██╔══╝  ██║╚██╔╝██║██║╚██╗██║
███████╗██║ ╚═╝ ██║██║ ╚████║
╚══════╝╚═╝     ╚═╝╚═╝  ╚═══╝

  ██████╗ ██████╗ ██████╗ ██╗███╗   ██╗ ██████╗       █████╗  ██████╗ ███████╗███╗   ██╗████████╗
 ██╔════╝██╔═══██╗██╔══██╗██║████╗  ██║██╔════╝      ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
 ██║     ██║   ██║██║  ██║██║██╔██╗ ██║██║  ███╗     ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
 ██║     ██║   ██║██║  ██║██║██║╚██╗██║██║   ██║     ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
 ╚██████╗╚██████╔╝██████╔╝██║██║ ╚████║╚██████╔╝     ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
  ╚═════╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝      ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
"""
    click.echo(click.style(banner, fg="cyan", bold=True))


DEFAULT_SYSTEM_PROMPT = SYSTEM_PROMPT


@click.command()
@click.option("--model", default=None, help="Override LLM model (e.g., litellm/gpt-4o)")
@click.option("--api-base", default=None, help="Override LiteLLM API base URL")
def main(model: str | None, api_base: str | None) -> None:
    """AI coding agent - self-hosted, model-agnostic."""
    print_banner()

    try:
        config = load_config()
        config = apply_cli_overrides(config, model=model, api_base=api_base)
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    click.echo(f"Model: {config.model}")
    click.echo(f"API:   {config.api_base}")
    click.echo("")

    try:
        llm_client = LLMClient(config)
        llm_client.verify_connection()
    except ConnectionError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    renderer = Renderer()
    renderer.print_info(f"Connected to LiteLLM")

    click.echo(click.style("Type 'exit' to quit.\n", fg="green"))

    conversation = ConversationManager(DEFAULT_SYSTEM_PROMPT)
    session = PromptSession()

    while True:
        try:
            text = session.prompt("you> ")
        except KeyboardInterrupt:
            click.echo("\nUse Ctrl+D or type 'exit' to quit.")
            continue
        except EOFError:
            conversation.clear()
            break

        text = text.strip()
        if not text:
            continue
        if text.lower() in ("exit", "quit"):
            conversation.clear()
            break

        conversation.add_message("user", text)

        has_output = False
        try:
            full_response = ""
            for delta in llm_client.send_message_stream(conversation.get_messages()):
                click.echo(delta, nl=False)
                has_output = True
                full_response += delta
            click.echo("")
            conversation.add_message("assistant", full_response)
        except ConnectionError as e:
            if has_output:
                renderer.print_error("[streaming interrupted]")
            renderer.print_error(str(e))
