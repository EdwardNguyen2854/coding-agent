"""Coding-Agent CLI entry point."""

import os
import re
import json

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

__version__ = "0.1.5"

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


def parse_tool_calls(response: str) -> list[dict]:
    """Parse tool calls from LLM response - supports both XML and JSON format."""
    tool_calls = []
    xml_pattern = r"<tool_call>\s*<function=([\w.-]+)>(.*?)</function>\s*</tool_call>"
    xml_matches = re.findall(xml_pattern, response, re.DOTALL)

    for func_name, body in xml_matches:
        params: dict[str, str] = {}

        named_params = re.findall(r"<parameter=(\w+)>\s*(.*?)\s*</parameter>", body, re.DOTALL)
        for key, value in named_params:
            params[key] = value.strip()

        generic_params = re.findall(r"<(\w+)>\s*(.*?)\s*</\1>", body, re.DOTALL)
        for key, value in generic_params:
            if key not in params:
                params[key] = value.strip()

        tool_calls.append({"name": func_name, "params": params, "id": f"call_{len(tool_calls)}"})
    
    # Try JSON format
    if not tool_calls:
        json_pattern = r'```json\s*(\{[\s\S]*?\})\s*```'
        json_matches = re.findall(json_pattern, response)
        
        for json_str in json_matches:
            try:
                tool_data = json.loads(json_str)
                tool_name = tool_data.get("tool") or tool_data.get("function", {}).get("name", "")
                tool_params = tool_data.get("parameters") or tool_data.get("function", {}).get("arguments", {})
                if isinstance(tool_params, str):
                    tool_params = json.loads(tool_params)
                if tool_name and tool_params:
                    tool_calls.append({"name": tool_name, "params": tool_params, "id": f"call_{len(tool_calls)}"})
            except json.JSONDecodeError:
                pass
    
    return tool_calls


def process_response(llm_client: LLMClient, conversation: ConversationManager) -> None:
    """Process LLM response and execute tools if needed."""
    full_response = ""
    click.echo(ASSISTANT_PREFIX, nl=False)
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
            
            click.echo(f"[tool] {tool_name}")
            for k, v in tool_params.items():
                click.echo(f"  - {k}: {str(v)[:80]}")
            click.echo("  running...")
            
            result = execute_tool(tool_name, tool_params)
            
            if result.is_error:
                click.echo(f"  error: {result.error}")
                conversation.add_message("tool", f"Error: {result.error}", tool_call_id=tool_id)
            else:
                click.echo("  done")
                conversation.add_message("tool", result.output, tool_call_id=tool_id)
        click.echo("-" * 40)
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
