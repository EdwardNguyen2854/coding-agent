"""Coding-Agent CLI entry point."""

import os
import re

import sys

import click
from prompt_toolkit import PromptSession

from coding_agent.config import ConfigError, apply_cli_overrides, load_config
from coding_agent.conversation import ConversationManager
from coding_agent.llm import LLMClient
from coding_agent.renderer import Renderer
from coding_agent.system_prompt import SYSTEM_PROMPT
from coding_agent.tools import execute_tool

import litellm
litellm.suppress_debug_info = True

__version__ = "0.1.1"


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
 ╚██████╗╚██████╔╝██████╔╝██║██║ ╚████║╚██████╔╝     ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
 ╚═════╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝      ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
                                                        v{__version__}
"""
    click.echo(click.style(banner, fg="cyan", bold=True))


def parse_tool_calls(response: str) -> list[dict]:
    """Parse tool calls from LLM response XML format."""
    tool_calls = []
    pattern = r"<tool_call>\s*<function=(\w+)>(.*?)</tool_call>"
    matches = re.findall(pattern, response, re.DOTALL)
    
    for func_name, params_str in matches:
        params = {}
        param_pattern = r"<(\w+)>(.*?)</\1>"
        param_matches = re.findall(param_pattern, params_str)
        for key, value in param_matches:
            params[key] = value.strip()
        tool_calls.append({"name": func_name, "params": params, "id": f"call_{len(tool_calls)}"})
    
    return tool_calls


def process_response(llm_client: LLMClient, conversation: ConversationManager) -> None:
    """Process LLM response and execute tools if needed."""
    full_response = ""
    for delta in llm_client.send_message_stream(conversation.get_messages()):
        click.echo(delta, nl=False)
        full_response += delta
    click.echo("")
    
    tool_calls = parse_tool_calls(full_response)
    
    if tool_calls:
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_params = tool_call["params"]
            tool_id = tool_call.get("id", "call_0")
            
            click.echo(click.style(f"\n→ Running {tool_name}...", fg="yellow"))
            result = execute_tool(tool_name, tool_params)
            
            if result.is_error:
                click.echo(click.style(f"Error: {result.error}", fg="red"))
                conversation.add_message("tool", f"Error: {result.error}", tool_call_id=tool_id)
            else:
                output_preview = result.output[:100] + "..." if len(result.output) > 100 else result.output
                click.echo(click.style(f"✓ {tool_name}: {output_preview}", fg="green"))
                conversation.add_message("tool", result.output, tool_call_id=tool_id)
        
        click.echo(click.style("\n→ Continuing...\n", fg="cyan"))
        process_response(llm_client, conversation)
    else:
        conversation.add_message("assistant", full_response)


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

        try:
            process_response(llm_client, conversation)
        except ConnectionError as e:
            renderer.print_error(str(e))
