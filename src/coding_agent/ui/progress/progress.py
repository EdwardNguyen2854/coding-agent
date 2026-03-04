"""Progress bar and workflow progress implementations using Rich."""

import sys
import time
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.progress import Progress as RichProgress
from rich.progress import SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, TimeElapsedColumn
from rich.progress import TextColumn as RichTextColumn
from rich.progress import TaskID
from rich.style import Style

from coding_agent.ui.progress.config import get_progress_config
from coding_agent.ui.progress.terminal import should_show_progress
from coding_agent.ui.progress.types import Progress as ProgressProtocol


class Progress:
    """Progress bar implementation using Rich."""

    def __init__(
        self,
        description: str = "",
        total: int = 100,
        console: Optional[Console] = None,
    ):
        self.console = console or Console()
        self.config = get_progress_config()
        self.description = description
        self.total = total
        self.current = 0
        self.start_time: Optional[float] = None
        self._progress: Optional[RichProgress] = None
        self._task_id: Optional[TaskID] = None

    def start(self, total: int, description: str = "") -> None:
        """Start progress with total steps/items."""
        self.total = total
        self.description = description
        self.current = 0
        self.start_time = time.time()

        if not self.config.enabled or not should_show_progress():
            return

        self._progress = RichProgress(
            SpinnerColumn(),
            RichTextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
        )
        self._progress.start()
        self._task_id = self._progress.add_task(self.description, total=total)

    def increment(self, n: int = 1) -> None:
        """Increment progress by n."""
        self.current += n
        if self._progress and self._task_id is not None:
            self._progress.update(self._task_id, advance=n)

    def set_description(self, description: str) -> None:
        """Update the progress description."""
        self.description = description
        if self._progress and self._task_id is not None:
            self._progress.update(self._task_id, description=description)

    def stop(self) -> None:
        """Stop and complete the progress."""
        if self._progress:
            self._progress.stop()
            self._progress = None
            self._task_id = None

    def __enter__(self) -> "Progress":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()


class WorkflowProgress:
    """Multi-step workflow progress indicator."""

    def __init__(
        self,
        steps: list[str],
        console: Optional[Console] = None,
    ):
        self.console = console or Console()
        self.config = get_progress_config()
        self.steps = steps
        self.current_step = 0
        self.start_time: Optional[float] = None
        self._progress: Optional[RichProgress] = None
        self._task_id: Optional[TaskID] = None

    def start(self) -> None:
        """Start the workflow progress."""
        self.current_step = 0
        self.start_time = time.time()

        if not self.config.enabled or not should_show_progress():
            return

        self._progress = RichProgress(
            SpinnerColumn(),
            RichTextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
            transient=False,
        )
        self._progress.start()
        self._update_task()

    def set_step(self, step: int, description: Optional[str] = None) -> None:
        """Set the current step (1-indexed)."""
        if step < 1 or step > len(self.steps):
            return

        self.current_step = step - 1
        if description:
            self.steps[self.current_step] = description
        self._update_task()

    def next_step(self, description: Optional[str] = None) -> None:
        """Move to the next step."""
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            if description:
                self.steps[self.current_step] = description
            self._update_task()

    def _update_task(self) -> None:
        """Update the progress task."""
        if not self._progress:
            return

        total = len(self.steps)
        current = self.current_step + 1
        desc = self.steps[self.current_step]

        if self._task_id is None:
            self._task_id = self._progress.add_task(desc, total=total, completed=current)
        else:
            self._progress.update(self._task_id, description=desc, completed=current)

    def stop(self) -> None:
        """Stop the workflow progress."""
        if self._progress:
            self._progress.stop()
            self._progress = None
            self._task_id = None

    def __enter__(self) -> "WorkflowProgress":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()


class SimpleProgress:
    """Simple progress implementation for basic use cases."""

    def __init__(
        self,
        description: str = "",
        total: int = 100,
    ):
        self.description = description
        self.total = total
        self.current = 0
        self.start_time: Optional[float] = None

    def start(self, total: int, description: str = "") -> None:
        """Start progress."""
        self.total = total
        self.description = description
        self.current = 0
        self.start_time = time.time()
        print(f"{self.description} [0/{total}]")

    def increment(self, n: int = 1) -> None:
        """Increment progress."""
        self.current += n

    def set_description(self, description: str) -> None:
        """Update description."""
        self.description = description

    def stop(self) -> None:
        """Stop progress."""
        pass

    def __enter__(self) -> "SimpleProgress":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


def create_progress(
    description: str = "",
    total: int = 100,
    console: Optional[Console] = None,
) -> ProgressProtocol:
    """Factory function to create a progress indicator.

    Args:
        description: Initial description.
        total: Total steps/items.
        console: Rich console instance.

    Returns:
        Progress implementation based on terminal capabilities.
    """
    if should_show_progress():
        return Progress(description=description, total=total, console=console)
    return SimpleProgress(description=description, total=total)


def create_workflow_progress(
    steps: list[str],
    console: Optional[Console] = None,
) -> WorkflowProgress:
    """Factory function to create a workflow progress indicator.

    Args:
        steps: List of step names.
        console: Rich console instance.

    Returns:
        WorkflowProgress implementation.
    """
    return WorkflowProgress(steps=steps, console=console)
