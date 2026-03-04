"""Progress indicator types and interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class ProgressStyle(str, Enum):
    """Progress bar display style."""

    BAR = "bar"
    DOTS = "dots"
    MINIMAL = "minimal"


class SpinnerStyle(str, Enum):
    """Spinner animation style."""

    DOTS = "dots"
    LINE = "line"
    BOUNCING = "bouncing"


@dataclass
class ProgressConfig:
    """Progress display configuration."""

    enabled: bool = True
    style: ProgressStyle = ProgressStyle.BAR
    refresh_rate: int = 100
    show_time: bool = True
    show_step: bool = True


class Progress(Protocol):
    """Protocol for progress indicators."""

    def start(self, total: int, description: str) -> None:
        """Start progress with total steps/items."""
        ...

    def increment(self, n: int = 1) -> None:
        """Increment progress by n."""
        ...

    def set_description(self, description: str) -> None:
        """Update the progress description."""
        ...

    def stop(self) -> None:
        """Stop and complete the progress."""
        ...

    def __enter__(self) -> "Progress":
        """Context manager entry."""
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        ...


class WorkflowStep:
    """A single step in a workflow."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.started: bool = False
        self.completed: bool = False

    def __repr__(self) -> str:
        return f"WorkflowStep({self.name!r})"
