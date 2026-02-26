"""Slash command system for CLI."""

from pathlib import Path
from typing import TYPE_CHECKING, Callable
from urllib.error import URLError
from socket import timeout as socket_timeout

import yaml

import litellm
from prompt_toolkit.completion import Completer, Completion
from rich.table import Table

from coding_agent.config import DEFAULT_CONFIG_FILE, DEFAULT_DOCS_DIR, SkillSetting, load_config
from coding_agent.core.conversation import ConversationManager
from coding_agent.core.llm import LLMClient
from coding_agent.config.project_instructions import find_git_root
from coding_agent.ui.renderer import Renderer
from coding_agent.state.session import SessionManager
from coding_agent.config.skills import Skill
from coding_agent.state.workflow_impl import WorkflowManager, WorkflowState, Plan

if TYPE_CHECKING:
    from coding_agent.core.agent import Agent


_workflow_manager: WorkflowManager | None = None


def set_workflow_manager(wm: WorkflowManager) -> None:
    """Set the global workflow manager instance."""
    global _workflow_manager
    _workflow_manager = wm


def get_workflow_manager() -> WorkflowManager | None:
    """Get the global workflow manager instance."""
    return _workflow_manager


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
    renderer.console.clear()
    renderer.print_success("Conversation cleared.")
    return True


def cmd_compact(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """Trigger conversation truncation."""
    session_id = args.strip() or (agent.session_data.get("id") if agent and agent.session_data else None)
    if session_id:
        result = session_manager.compact(session_id, max_tokens=64000)
        if result:
            renderer.print_success(f"Session compacted. Tokens: {result.get('token_count', 0)}")
        else:
            renderer.print_error("Failed to compact session")
    else:
        conversation.truncate_if_needed(max_tokens=64000)
        renderer.print_success("Conversation compacted (in-memory).")
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


def cmd_todo(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """Show or manage todo list."""
    wm = get_workflow_manager()
    if not wm:
        renderer.print_error("Workflow not initialized.")
        return True

    workflow = wm.get_current()
    todos = workflow.todo_list

    if not args:
        if todos.total == 0:
            renderer.print_info("No tasks in todo list.")
        else:
            markdown_output = todos.to_markdown()
            renderer.console.print(markdown_output)
        return True

    action = args.strip().split()[0] if args.strip() else ""

    if action == "clear":
        todos.clear_completed()
        renderer.print_success("Completed tasks cleared.")
    elif action == "next":
        next_task = todos.get_next()
        if next_task:
            renderer.print_info(f"Next task: {next_task.description}")
        else:
            renderer.print_info("No pending tasks.")
    elif action.startswith("done:"):
        task_desc = args[5:].strip()
        for item in todos.items:
            if item.description == task_desc and item.status != "completed":
                workflow.complete_task(item.id)
                break
        else:
            renderer.print_error(f"Task not found: {task_desc}")
    else:
        renderer.print_info("Usage: /todo [clear|next|done:<task description>]")

    return True


def cmd_approve(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """Approve the current implementation plan."""
    wm = get_workflow_manager()
    if not wm:
        renderer.print_error("Workflow not initialized.")
        return True

    workflow = wm.get_current()

    if workflow.state != WorkflowState.PLAN_CREATED:
        renderer.print_info("No plan to approve. Use the workflow to create a plan first.")
        return True

    workflow.approve_plan()
    workflow.state = WorkflowState.EXECUTING

    next_task = workflow.get_next_task()
    if next_task:
        workflow.start_task(next_task.id)
        renderer.print_success("Plan approved! Starting task execution.")
        renderer.print_info(f"First task: {next_task.description}")

        if agent:
            agent.run(f"Execute the task: {next_task.description}")
    else:
        renderer.print_info("Plan approved but no tasks to execute.")

    return True


def cmd_reject(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """Reject the current implementation plan."""
    wm = get_workflow_manager()
    if not wm:
        renderer.print_error("Workflow not initialized.")
        return True

    workflow = wm.get_current()

    if workflow.state != WorkflowState.PLAN_CREATED:
        renderer.print_info("No plan to reject.")
        return True

    workflow.reject_plan()
    workflow.state = WorkflowState.IDLE
    renderer.print_info("Plan rejected. You can ask for a new implementation plan.")

    return True


def cmd_auto_allow(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """Toggle auto-allow mode for tool execution approvals."""
    if not agent:
        renderer.print_error("No agent available.")
        return True

    current_state = agent.permissions.is_auto_allow_enabled()
    
    if args.strip().lower() in ("on", "enable", "true", "1"):
        agent.permissions.set_auto_allow(True)
        renderer.print_success("Auto-allow mode: ON (all tool executions approved)")
    elif args.strip().lower() in ("off", "disable", "false", "0"):
        agent.permissions.set_auto_allow(False)
        renderer.print_info("Auto-allow mode: OFF (tool executions require approval)")
    else:
        status = "ON" if current_state else "OFF"
        renderer.print_info(f"Auto-allow mode is currently: {status}")
        renderer.print_info("Usage: /auto-allow [on|off]")

    return True


def cmd_plan(args: str, conversation: ConversationManager, session_manager: SessionManager, renderer: Renderer, llm_client: LLMClient | None = None, agent: "Agent | None" = None) -> bool:
    """Create an implementation plan from the current task."""
    wm = get_workflow_manager()
    if not wm:
        renderer.print_error("Workflow not initialized.")
        return True

    workflow = wm.get_current()

    if not args:
        renderer.print_info("Usage: /plan <description of what you want to build>")
        return True

    workflow.state = WorkflowState.AWAITING_PLAN
    renderer.print_info("Creating implementation plan...")

    if agent:
        agent.run(f"""Create an implementation plan for: {args}

Please create a detailed plan with:
1. A clear title
2. Description of what will be built
3. A list of specific tasks that need to be done

Save this plan to {DEFAULT_DOCS_DIR / "implementation-plan.md"} and then tell me the plan is ready for approval.""")

    # Check if plan file was created and load it
    plan_path = DEFAULT_DOCS_DIR / "implementation-plan.md"
    if plan_path.exists():
        content = plan_path.read_text(encoding="utf-8")
        workflow.current_plan = Plan.from_markdown(content)
        workflow.state = WorkflowState.PLAN_CREATED
        renderer.print_success("Plan created! Use /approve to approve or /reject to reject.")
    else:
        renderer.print_warning("Plan file not found. Please check the output above.")

    return True


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


def run_skills_tui(skills: list[SkillSetting]) -> list[SkillSetting] | None:
    """Run an interactive TUI for configuring skills.

    Two-phase flow:
      Phase 1 – checkbox list with ↑/↓ navigation and Space to toggle.
      Phase 2 – confirmation screen before saving.

    Args:
        skills: List of SkillSetting objects to configure.

    Returns:
        Updated list of SkillSetting with modified enabled flags, or None if cancelled.
    """
    import copy

    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    working_skills = [copy.copy(s) for s in skills]
    state: dict = {"cursor": 0, "phase": 1, "cancelled": False}

    def get_content() -> list[tuple[str, str]]:
        lines: list[tuple[str, str]] = []
        if state["phase"] == 1:
            lines.append(("bold", " Configure Skills\n"))
            lines.append(("", " \u2191\u2193 navigate   Space toggle   Enter confirm   Esc cancel\n\n"))
            for i, skill in enumerate(working_skills):
                cursor_char = "\u25b6" if i == state["cursor"] else " "
                check = "x" if skill.enabled else " "
                style = "bold" if i == state["cursor"] else ""
                lines.append((style, f" {cursor_char} [{check}] {skill.name}\n"))
            enabled_count = sum(1 for s in working_skills if s.enabled)
            lines.append(("", f"\n {enabled_count}/{len(working_skills)} skills enabled\n"))
        else:
            lines.append(("bold", " Save Changes?\n\n"))
            enabled_count = sum(1 for s in working_skills if s.enabled)
            lines.append(("", f"  {enabled_count} of {len(working_skills)} skills will be enabled.\n\n"))
            lines.append(("", " Enter to save   Esc to go back\n"))
        return lines

    kb = KeyBindings()

    @kb.add("up")
    def _up(event) -> None:
        if state["phase"] == 1:
            state["cursor"] = max(0, state["cursor"] - 1)

    @kb.add("down")
    def _down(event) -> None:
        if state["phase"] == 1:
            state["cursor"] = min(len(working_skills) - 1, state["cursor"] + 1)

    @kb.add("space")
    def _toggle(event) -> None:
        if state["phase"] == 1:
            working_skills[state["cursor"]].enabled = not working_skills[state["cursor"]].enabled

    @kb.add("enter")
    def _enter(event) -> None:
        if state["phase"] == 1:
            state["phase"] = 2
        else:
            event.app.exit()

    @kb.add("escape", eager=True)
    def _escape(event) -> None:
        if state["phase"] == 2:
            state["phase"] = 1
        else:
            state["cancelled"] = True
            event.app.exit()

    @kb.add("c-c")
    def _ctrl_c(event) -> None:
        state["cancelled"] = True
        event.app.exit()

    layout = Layout(Window(FormattedTextControl(get_content, focusable=True)))
    app = Application(layout=layout, key_bindings=kb, full_screen=False)
    app.run()

    if state["cancelled"]:
        return None
    return working_skills


def cmd_skills(
    args: str,
    conversation: ConversationManager,
    session_manager: SessionManager,
    renderer: Renderer,
    llm_client: LLMClient | None = None,
    agent: "Agent | None" = None,
) -> bool:
    """Configure skills via interactive TUI."""
    try:
        config = load_config()
    except Exception as e:
        renderer.print_error(f"Failed to load config: {e}")
        return True

    updated = run_skills_tui(config.skills.skills)

    if updated is None:
        renderer.print_info("Cancelled.")
        return True

    config_data = config.model_dump()
    config_data["skills"] = {"skills": [s.model_dump() for s in updated]}
    DEFAULT_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False)

    enabled_count = sum(1 for s in updated if s.enabled)
    renderer.print_success(
        f"Saved: {enabled_count}/{len(updated)} skills enabled. Changes take effect next session."
    )
    return True


def _get_workflows_dir() -> Path:
    """Return the path to the built-in workflows directory."""
    return Path(__file__).parent.parent / "workflows"


def _load_registry() -> list[dict]:
    """Load workflow entries from registry.yaml."""
    registry_path = _get_workflows_dir() / "registry" / "registry.yaml"
    if not registry_path.exists():
        return []
    with open(registry_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("workflows", []) if data else []


def _load_workflow_yaml(entry: str) -> dict | None:
    """Load a workflow YAML file by its registry entry filename."""
    workflows_dir = _get_workflows_dir()
    yaml_path = workflows_dir / entry
    if not yaml_path.exists():
        yaml_path = workflows_dir / Path(entry).name
    if not yaml_path.exists():
        return None
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def cmd_workflow(
    args: str,
    conversation: ConversationManager,
    session_manager: SessionManager,
    renderer: Renderer,
    llm_client: LLMClient | None = None,
    agent: "Agent | None" = None,
) -> bool:
    """List available workflows or run one by name."""
    registry = _load_registry()

    if not args:
        if not registry:
            renderer.print_info("No workflows available.")
            return True
        table = Table(title="Available Workflows", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        for wf in registry:
            table.add_row(wf.get("name", ""), wf.get("description", ""))
        renderer.console.print(table)
        renderer.print_info("Run a workflow: /workflow <name> [input]")
        return True

    parts = args.strip().split(maxsplit=1)
    name = parts[0]
    user_input = parts[1] if len(parts) > 1 else ""

    entry = next((wf for wf in registry if wf.get("name") == name), None)
    if not entry:
        renderer.print_error(f"Unknown workflow: {name}. Use /workflow to list available workflows.")
        return True

    wf_data = _load_workflow_yaml(entry.get("entry", f"{name}.yaml"))
    if not wf_data:
        renderer.print_error(f"Could not load workflow file for: {name}")
        return True

    wf_name = wf_data.get("name", name)
    wf_desc = wf_data.get("description", "")
    steps = wf_data.get("steps", [])
    variables = wf_data.get("variables", {})

    # Build variable substitution map from user_input
    var_map: dict[str, str] = {}
    for var_name, var_meta in variables.items():
        if isinstance(var_meta, dict):
            var_map[var_name] = user_input if user_input else var_meta.get("default", "")
        else:
            var_map[var_name] = user_input

    def _substitute(text: str) -> str:
        for k, v in var_map.items():
            text = text.replace(f"{{{k}}}", v)
        return text

    prompt_lines = [f"Execute the '{wf_name}' workflow.", f"Goal: {wf_desc}"]
    if user_input:
        prompt_lines.append(f"Input: {user_input}")
    prompt_lines.append("\nFollow these steps in order:")

    for i, step in enumerate(steps, 1):
        title = step.get("title", step.get("id", f"Step {i}"))
        step_desc = step.get("description", "")
        actions = step.get("actions", [])
        prompt_lines.append(f"\n## Step {i}: {title}")
        if step_desc:
            prompt_lines.append(f"{step_desc}")
        for action in actions:
            if isinstance(action, dict) and "task" in action:
                prompt_lines.append(f"- {_substitute(action['task'])}")

    prompt = "\n".join(prompt_lines)

    renderer.print_info(f"Running workflow: {wf_name}")
    if agent:
        agent.run(prompt)
    else:
        renderer.print_error("No agent available to run workflow.")
    return True


COMMANDS: dict[str, SlashCommand] = {
    "help": SlashCommand("help", cmd_help, "Show help message", False),
    "clear": SlashCommand("clear", cmd_clear, "Clear conversation history", False),
    "compact": SlashCommand("compact", cmd_compact, "Manually trigger conversation truncation", False),
    "sessions": SlashCommand("sessions", cmd_sessions, "List saved sessions", False),
    "model": SlashCommand("model", cmd_model, "Switch to a different model", True),
    "init": SlashCommand("init", cmd_init, "Create AGENTS.md template in project root", False),
    "skills": SlashCommand("skills", cmd_skills, "Configure skills (toggle enabled/disabled)", False),
    "exit": SlashCommand("exit", cmd_exit, "Exit the session", False),
    "todo": SlashCommand("todo", cmd_todo, "Show/manage todo list", False),
    "plan": SlashCommand("plan", cmd_plan, "Create implementation plan", True),
    "approve": SlashCommand("approve", cmd_approve, "Approve implementation plan", False),
    "reject": SlashCommand("reject", cmd_reject, "Reject implementation plan", False),
    "auto-allow": SlashCommand("auto-allow", cmd_auto_allow, "Toggle auto-allow mode for approvals", False),
    "workflow": SlashCommand("workflow", cmd_workflow, "List or run a YAML workflow", False),
}


def register_skills(skills: dict[str, Skill], agent: "Agent") -> list[str]:
    """Register skills from SKILL.md as dynamic slash commands.

    Each skill becomes a slash command that runs its instructions through
    the agent. Project skills override built-in commands with the same name.

    Args:
        skills: Mapping of skill name to Skill object.
        agent: Agent instance used to execute skill prompts.

    Returns:
        List of registered skill names.
    """
    registered: list[str] = []

    for name, skill in skills.items():
        if not name:
            continue

        content = skill.instructions
        description = skill.description

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
            help_text=f"[skill] {description or content[:60].splitlines()[0] if content else name}",
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
