"""Progress configuration management."""

from typing import Callable

from coding_agent.ui.progress.terminal import get_terminal_capabilities, should_show_progress
from coding_agent.ui.progress.types import ProgressConfig, ProgressStyle


_default_config: ProgressConfig | None = None
_config_override: Callable[[], ProgressConfig] | None = None


def get_progress_config() -> ProgressConfig:
    """Get the current progress configuration.

    Returns:
        ProgressConfig instance.
    """
    if _config_override is not None:
        return _config_override()

    global _default_config
    if _default_config is None:
        _default_config = _create_default_config()
    return _default_config


def _create_default_config() -> ProgressConfig:
    """Create default progress configuration based on terminal."""
    caps = get_terminal_capabilities()
    enabled = should_show_progress()

    return ProgressConfig(
        enabled=enabled,
        style=ProgressStyle.BAR,
        refresh_rate=100,
        show_time=True,
        show_step=True,
    )


def set_progress_config_override(override: Callable[[], ProgressConfig]) -> None:
    """Set a callback to override progress config retrieval.

    Args:
        override: Callable that returns a ProgressConfig.
    """
    global _config_override
    _config_override = override


def reset_progress_config() -> None:
    """Reset progress config to defaults."""
    global _default_config, _config_override
    _default_config = None
    _config_override = None
