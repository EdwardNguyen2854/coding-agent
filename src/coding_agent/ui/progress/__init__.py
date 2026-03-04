"""Progress indicators for long-running operations.

This module provides progress bars and workflow progress indicators
for giving users visual feedback during long-running operations.

Usage:
    # Simple progress bar
    with create_progress("Processing", total=100) as p:
        for i in range(100):
            p.increment()
            time.sleep(0.01)

    # Workflow progress
    with create_workflow_progress(["Step 1", "Step 2", "Step 3"]) as wf:
        do_step_1()
        wf.next_step()
        do_step_2()
        wf.next_step()
        do_step_3()
"""

from coding_agent.ui.progress.config import (
    get_progress_config,
    reset_progress_config,
    set_progress_config_override,
)
from coding_agent.ui.progress.progress import (
    Progress,
    WorkflowProgress,
    create_progress,
    create_workflow_progress,
)
from coding_agent.ui.progress.render import (
    ProgressRenderer,
    SpinnerRenderer,
    create_progress_renderer,
    create_spinner_renderer,
)
from coding_agent.ui.progress.terminal import (
    TerminalCapabilities,
    get_terminal_capabilities,
    should_show_progress,
)
from coding_agent.ui.progress.types import (
    ProgressConfig,
    ProgressStyle,
    SpinnerStyle,
    WorkflowStep,
)

__all__ = [
    # Types
    "ProgressConfig",
    "ProgressStyle",
    "SpinnerStyle",
    "WorkflowStep",
    "TerminalCapabilities",
    # Terminal
    "get_terminal_capabilities",
    "should_show_progress",
    # Config
    "get_progress_config",
    "set_progress_config_override",
    "reset_progress_config",
    # Renderers
    "ProgressRenderer",
    "SpinnerRenderer",
    "create_progress_renderer",
    "create_spinner_renderer",
    # Main implementations
    "Progress",
    "WorkflowProgress",
    "create_progress",
    "create_workflow_progress",
]
