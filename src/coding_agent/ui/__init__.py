"""UI subpackage - everything the user sees."""

from coding_agent.ui.interrupt import is_interrupted, clear_interrupt, trigger_interrupt
from coding_agent.ui.renderer import Renderer
from coding_agent.ui.sidebar import make_toolbar
from coding_agent.ui.slash_commands import (
    COMMANDS,
    SlashCommand,
    SlashCommandCompleter,
    execute_command,
    register_skills,
    set_workflow_manager,
    get_workflow_manager,
)

main = None

def __getattr__(name):
    global main
    if name == "main":
        from coding_agent.ui.cli import main
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
