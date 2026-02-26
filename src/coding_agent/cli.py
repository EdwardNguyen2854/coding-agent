"""Coding-Agent CLI entry point."""

import os
import sys
from pathlib import Path

import click

# --- Early init: truststore + proxy must be set before importing litellm/openai/httpx ---
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from coding_agent.config import load_config, DEFAULT_SKILLS, SkillsConfig, SkillSetting, DEFAULT_CONFIG_FILE
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
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style as PTStyle

from coding_agent.agent import Agent
from coding_agent.config import ConfigError, OLLAMA_DEFAULT_API_BASE, apply_cli_overrides, ensure_docs_installed
from coding_agent.conversation import ConversationManager
from coding_agent.llm import LLMClient
from coding_agent.project_instructions import get_enhanced_system_prompt
from coding_agent.renderer import Renderer
from coding_agent.session import SessionManager
from coding_agent.skills import load_skills
from coding_agent.slash_commands import SlashCommandCompleter, execute_command, register_skills
from coding_agent.system_prompt import SYSTEM_PROMPT

from coding_agent import __version__
from coding_agent.sidebar import make_toolbar
from coding_agent.workflow import WorkflowManager, WorkflowState

import litellm
litellm.suppress_debug_info = True

from coding_agent import __version__

STYLED_PROMPT = FormattedText([
    ("class:user", "You"),
    ("class:arrow", " > "),
])

PROMPT_STYLE = PTStyle.from_dict({
    "user": "ansicyan bold",
    "arrow": "ansigreen",
    "rprompt": "#888888",
})


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


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--model", default=None, help="Override LLM model (e.g., litellm/gpt-4o)")
@click.option("--api-base", default=None, help="Override LiteLLM API base URL")
@click.option("--temperature", default=None, type=float, help="Override temperature (0.0-2.0)")
@click.option("--max-output-tokens", "max_output_tokens", default=None, type=int, help="Override max output tokens")
@click.option("--top-p", default=None, type=float, help="Override top_p (0.0-1.0)")
@click.option("--resume", is_flag=True, help="Resume the most recent session")
@click.option("--session", "session_id", default=None, help="Resume a specific session by ID")
@click.option("--ollama", "ollama_model", default=None, metavar="MODEL",
              help="Use a local Ollama model, e.g. llama3.2 or qwen2.5-coder:7b")
def cli(ctx, model, api_base, temperature, max_output_tokens, top_p, resume, session_id, ollama_model):
    """Coding-Agent CLI."""
    ctx.ensure_object(dict)
    ctx.obj["model"] = model
    ctx.obj["api_base"] = api_base
    ctx.obj["temperature"] = temperature
    ctx.obj["max_output_tokens"] = max_output_tokens
    ctx.obj["top_p"] = top_p
    ctx.obj["resume"] = resume
    ctx.obj["session_id"] = session_id
    ctx.obj["ollama_model"] = ollama_model
    if ctx.invoked_subcommand is None:
        ctx.invoke(run)


@cli.command("skills")
@click.argument('choice', required=False, default='')
def skills(choice):
    """Configure skills (tick/untick which skills to enable).
    
    Usage: coding-agent skills [numbers]
    Examples:
        coding-agent skills          # Show all skills
        coding-agent skills 1        # Toggle skill #1
        coding-agent skills 1,3,5    # Toggle skills 1, 3, and 5
        coding-agent skills all      # Enable all skills
        coding-agent skills none     # Disable all skills
    """
    import yaml
    from rich.console import Console
    from rich.table import Table
    from rich import box
    
    console = Console()
    config = load_config()
    current_skills = config.skills
    
    def render_table(selected_indices: list[int] | None = None):
        table = Table(title="Skills Configuration", box=box.ROUNDED, show_lines=True)
        table.add_column("#", style="cyan", width=4)
        table.add_column("Skill", style="bold")
        table.add_column("Enabled", justify="center", width=8)
        
        enabled_count = sum(1 for s in current_skills.skills if s.enabled)
        
        for i, skill in enumerate(current_skills.skills, 1):
            is_enabled = skill.enabled
            is_selected = selected_indices and i in selected_indices
            
            if is_selected:
                status = "[T]"
            elif is_enabled:
                status = "[x]"
            else:
                status = "[ ]"
            
            style = "green bold" if is_enabled else "dim"
            table.add_row(
                str(i),
                skill.name,
                status,
                style=style
            )
        
        console.print(table)
        console.print(f"\n{enabled_count}/{len(current_skills.skills)} skills enabled")
        console.print("[dim]Usage: coding-agent skills 1,3,5  (toggle)[/dim]")
    
    choice = choice.strip() if choice else ''
    
    if not choice:
        render_table()
        return
    
    if choice.lower() == 'q' or choice.lower() == 'quit':
        console.print("[yellow]Cancelled.[/yellow]")
        return
    
    indices: list[int] = []
    
    if choice.lower() == 'all':
        for s in current_skills.skills:
            s.enabled = True
    elif choice.lower() == 'none':
        for s in current_skills.skills:
            s.enabled = False
    else:
        for part in choice.split(','):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(current_skills.skills):
                    indices.append(idx + 1)
                    current_skills.skills[idx].enabled = not current_skills.skills[idx].enabled
    
    config_data = config.model_dump()
    config_data['skills'] = {'skills': [s.model_dump() for s in current_skills.skills]}
    
    DEFAULT_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_CONFIG_FILE, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False)
    
    console.print("\n[green]Configuration saved![/green]\n")
    render_table(indices if indices else None)
    console.print("[dim]Examples: coding-agent skills all / coding-agent skills none[/dim]")



@cli.command()
@click.version_option(version=__version__, prog_name="coding-agent")
@click.option("--model", default=None, help="Override LLM model (e.g., litellm/gpt-4o)")
@click.option("--api-base", default=None, help="Override LiteLLM API base URL")
@click.option("--temperature", default=None, type=float, help="Override temperature (0.0-2.0)")
@click.option("--max-output-tokens", "max_output_tokens", default=None, type=int, help="Override max output tokens")
@click.option("--top-p", default=None, type=float, help="Override top_p (0.0-1.0)")
@click.option("--resume", is_flag=True, help="Resume the most recent session")
@click.option("--session", "session_id", default=None, help="Resume a specific session by ID")
@click.option("--ollama", "ollama_model", default=None, metavar="MODEL",
              help="Use a local Ollama model, e.g. llama3.2 or qwen2.5-coder:7b")
@click.pass_context
def run(ctx, model: str | None, api_base: str | None, temperature: float | None, max_output_tokens: int | None, top_p: float | None, resume: bool, session_id: str | None, ollama_model: str | None) -> None:
    """AI coding agent - self-hosted, model-agnostic."""
    # Use parent context options as defaults if not provided
    parent = ctx.parent
    if parent and parent.obj:
        if model is None:
            model = parent.obj.get("model")
        if api_base is None:
            api_base = parent.obj.get("api_base")
        if temperature is None:
            temperature = parent.obj.get("temperature")
        if max_output_tokens is None:
            max_output_tokens = parent.obj.get("max_output_tokens")
        if top_p is None:
            top_p = parent.obj.get("top_p")
        if not resume:
            resume = parent.obj.get("resume", False)
        if session_id is None:
            session_id = parent.obj.get("session_id")
        if ollama_model is None:
            ollama_model = parent.obj.get("ollama_model")

    ensure_docs_installed()
    os.environ["LITELLM_NO_PROVIDER_LIST"] = "1"

    # Resolve --ollama shorthand into model + api_base overrides
    if ollama_model:
        if model is None:
            prefix = "" if ollama_model.startswith(("ollama/", "ollama_chat/")) else "ollama_chat/"
            model = f"{prefix}{ollama_model}"
        if api_base is None:
            api_base = OLLAMA_DEFAULT_API_BASE

    renderer = Renderer()
    renderer.render_banner(__version__)

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

    renderer.render_config({
        "Model": config.model,
        "API": config.api_base,
        **({"Proxy": config.https_proxy} if config.https_proxy else {}),
        "Temp": str(config.temperature),
        "MaxTok": str(config.max_output_tokens),
        "TopP": str(config.top_p),
    })
    renderer.console.print()

    try:
        llm_client = LLMClient(config)
        llm_client.verify_connection()
    except ConnectionError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    from coding_agent.config import is_ollama_model
    backend = "Ollama" if is_ollama_model(config.model) else "LiteLLM"
    renderer.print_info(f"Connected to {backend}")

    # Load project instructions lazily
    enhanced_prompt, loaded_files = _get_system_prompt()

    # Log loaded project instructions
    for path in loaded_files:
        renderer.print_info(f"Loaded project instructions from: {path}")


    session_manager = SessionManager()
    session_data = None
    conversation = ConversationManager(enhanced_prompt, model=config.model)

    # Create Agent instance
    agent = Agent(llm_client, conversation, renderer, config=config)

    # Load skills from SKILL.md and register as slash commands
    skills, skill_files = load_skills()
    if skills:
        enabled_skills = config.skills.get_enabled()
        filtered_skills = {k: v for k, v in skills.items() if k in enabled_skills}
        if filtered_skills:
            register_skills(filtered_skills, agent)
            renderer.print_info(f"Loaded {len(filtered_skills)} skills")
        else:
            renderer.print_info("No skills enabled in config. Skipping skill loading.")
    else:
        renderer.print_info("No skills found.")

    # Handle session resume
    if resume:
        loaded_session = session_manager.load_latest()
        if loaded_session:
            session_data = loaded_session
            msg_count = _restore_conversation(conversation, loaded_session.get("messages", []))
            renderer.print_info(f"Resuming session: {loaded_session['title']} ({msg_count} messages)")
            agent.set_session(session_manager, session_data)
        else:
            renderer.print_info("No previous sessions found. Starting a new session.")
    elif session_id:
        loaded_session = session_manager.load(session_id)
        if loaded_session:
            session_data = loaded_session
            msg_count = _restore_conversation(conversation, loaded_session.get("messages", []))
            renderer.print_info(f"Resuming session: {loaded_session['title']} ({msg_count} messages)")
            agent.set_session(session_manager, session_data)
        else:
            renderer.print_error(f"Session not found: {session_id}")
            sys.exit(1)

    workflow_manager = WorkflowManager(context_limit=128000)
    current_workflow = workflow_manager.get_current()

    def on_task_complete(completed_item):
        renderer.print_success(f"Task completed: {completed_item.description}")
        renderer.print_info(f"Progress: {current_workflow.todo_list.completed_count}/{current_workflow.todo_list.total}")

    current_workflow.set_task_complete_callback(on_task_complete)

    from coding_agent.slash_commands import set_workflow_manager
    set_workflow_manager(workflow_manager)

    renderer.print_info("Type 'exit' to quit.\n")

    import subprocess
    branch_name = "N/A"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            branch_name = result.stdout.strip()
    except Exception:
        pass

    # Slash command autocomplete
    slash_completer = SlashCommandCompleter()

    toolbar_func = make_toolbar(
        conversation=conversation,
        workflow=current_workflow,
        branch=branch_name,
        context_limit=128000,
    )

    from coding_agent.interrupt import get_interrupt_handler, trigger_interrupt
    interrupt_handler = get_interrupt_handler()
    interrupt_handler.start_keyboard_listener()

    def handle_interrupt():
        """Handle interrupt signal."""
        trigger_interrupt()
        renderer.print_warning("\n\nInterrupted! Type 'exit' to quit or continue chatting.")

    # Try prompt_toolkit, fallback to stdin if it fails (e.g., in non-Windows console)
    try:
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.keys import Keys

        key_bindings = KeyBindings()

        @key_bindings.add('c-c', filter=True)
        def _(event):
            """Handle Ctrl+C."""
            handle_interrupt()
            event.app.exit(exception=KeyboardInterrupt)

        @key_bindings.add('escape')
        def _(event):
            """Handle ESC key."""
            handle_interrupt()
            event.app.current_buffer.text = ""

        session = PromptSession(
            completer=slash_completer,
            complete_while_typing=True,
            style=PROMPT_STYLE,
            key_bindings=key_bindings,
        )
        input_func = lambda: session.prompt(STYLED_PROMPT, rprompt=toolbar_func)
    except Exception:
        # Fallback for non-Windows console environments
        input_func = lambda: input("You > ")

    while True:
        try:
            text = input_func()
        except KeyboardInterrupt:
            renderer.print_info("\nUse Ctrl+D or type 'exit' to quit.")
            continue
        except EOFError:
            conversation.clear()
            break

        text = text.strip()
        if not text:
            continue

        # Handle bare exit/quit commands
        if text.lower() in ("exit", "quit"):
            break

        # Check for slash commands
        should_continue = execute_command(text, conversation, session_manager, renderer, llm_client, agent)
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
            renderer.print_info(f"Session created: {session_data['title']}")
            agent.set_session(session_manager, session_data)

        # Delegate to Agent for ReAct loop
        try:
            agent.run(text)
            # Show status line after response
            token_count = conversation.token_count
            session_id = session_data.get("id") if session_data else None
            renderer.render_status_line(config.model, token_count, session_id)
        except ConnectionError as e:
            renderer.print_error(str(e))


# Alias for test compatibility
from click import Group
main: Group | type = cli  # type: ignore[assignment]
