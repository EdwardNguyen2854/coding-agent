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

from coding_agent.config import ConfigError, apply_cli_overrides
from coding_agent.conversation import ConversationManager
from coding_agent.llm import LLMClient
from coding_agent.renderer import Renderer
from coding_agent.system_prompt import SYSTEM_PROMPT
from coding_agent.tools import execute_tool

import litellm
litellm.suppress_debug_info = True

__version__ = "0.2.3"

USER_PROMPT = "You   > "
ASSISTANT_PREFIX = "Agent > "


def print_banner() -> None:
    """Print the EMN Coding Agent banner."""
    os.environ["LITELLM_NO_PROVIDER_LIST"] = "1"

    banner = f"""
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
 ██████╗╚██████╔╝██████╔╝██║██║ ╚████║╚██████╔╝     ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
 ╚═════╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝      ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝

v{__version__}
"""
    click.echo(click.style(banner, fg="cyan", bold=True))


def process_response(llm_client: LLMClient, conversation: ConversationManager) -> None:
    """Process LLM response and execute tools if needed."""
    # Stream text deltas; the generator returns an LLMResponse when exhausted
    gen = llm_client.send_message_stream(conversation.get_messages())
    full_text = ""
    try:
        while True:
            delta = next(gen)
            full_text += delta
    except StopIteration as e:
        llm_response = e.value

    if full_text.strip():
        click.echo(f"{ASSISTANT_PREFIX}{full_text.strip()}")

    if llm_response and llm_response.tool_calls:
        # Add assistant message with tool_calls to conversation
        conversation.add_assistant_tool_call(llm_response.content, llm_response.tool_calls)

        # Execute each tool and add results
        for tc in llm_response.tool_calls:
            tool_name = tc["name"]
            tool_params = tc["arguments"]

            click.echo(f"[tool] {tool_name}")
            for k, v in tool_params.items():
                click.echo(f"  - {k}: {str(v)[:80]}")
            click.echo("  running...")

            result = execute_tool(tool_name, tool_params)

            if result.is_error:
                click.echo(f"  error: {result.error}")
                conversation.add_tool_result(tc["id"], f"Error: {result.error}")
            else:
                click.echo("  done")
                conversation.add_tool_result(tc["id"], result.output)

        click.echo("-" * 40)
        process_response(llm_client, conversation)
    else:
        # No tool calls - just a plain text response
        conversation.add_message("assistant", llm_response.content if llm_response else full_text)


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
    if config.https_proxy:
        click.echo(f"Proxy: {config.https_proxy}")
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
        if text.lower() in ("exit", "quit"):
            conversation.clear()
            break

        conversation.add_message("user", text)

        try:
            process_response(llm_client, conversation)
        except ConnectionError as e:
            renderer.print_error(str(e))
