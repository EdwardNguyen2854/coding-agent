"""Configuration management - Pydantic model with YAML loading and CLI overrides."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

DEFAULT_CONFIG_DIR = Path.home() / ".coding-agent"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""


class AgentConfig(BaseModel):
    """Agent configuration with validation."""

    model_config = ConfigDict(extra="forbid")

    model: str
    api_base: str
    api_key: str | None = None
    https_proxy: str | None = None

    @field_validator("api_base")
    @classmethod
    def validate_api_base(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("Must start with http:// or https://")
        return v.rstrip("/")

    def __repr__(self) -> str:
        api_key_display = "***" if self.api_key else "None"
        return (
            f"AgentConfig(model={self.model!r}, "
            f"api_base={self.api_base!r}, "
            f"api_key={api_key_display!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def load_config(config_path: Path | None = None) -> AgentConfig:
    """Load and validate config from YAML file.

    Args:
        config_path: Path to config file. Defaults to ~/.coding-agent/config.yaml.

    Returns:
        Validated AgentConfig instance.

    Raises:
        ConfigError: If file is missing, empty, or contains invalid config.
    """
    path = config_path or DEFAULT_CONFIG_FILE

    if not path.exists():
        raise ConfigError(
            f"Configuration file not found.\n\n"
            f"Expected location: {path}\n\n"
            f"Create the file with at least these required fields:\n"
            f"  model: litellm/gpt-4o\n"
            f"  api_base: http://localhost:4000\n"
            f"  https_proxy: http://proxy.example.com:8080  # optional"
        )

    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    if not isinstance(data, dict):
        raise ConfigError(
            f"Invalid configuration in {path}\n\n"
            f"  Config file is empty or not a valid YAML mapping.\n\n"
            f"Required fields:\n"
            f"  model: litellm/gpt-4o\n"
            f"  api_base: http://localhost:4000\n"
            f"  https_proxy: http://proxy.example.com:8080  # optional"
        )

    try:
        return AgentConfig(**data)
    except ValidationError as e:
        errors = []
        for err in e.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            msg = err["msg"]
            errors.append(f"  - {field}: {msg}")
        error_text = "\n".join(errors)
        raise ConfigError(
            f"Invalid configuration in {path}\n\n{error_text}"
        ) from None


def apply_cli_overrides(
    config: AgentConfig,
    model: str | None = None,
    api_base: str | None = None,
) -> AgentConfig:
    """Apply CLI flag overrides to config. Returns a new AgentConfig instance.

    Override precedence: Defaults → YAML → CLI flags.
    """
    overrides = {}
    if model is not None:
        overrides["model"] = model
    if api_base is not None:
        overrides["api_base"] = api_base

    if not overrides:
        return config

    try:
        return AgentConfig.model_validate(config.model_dump() | overrides)
    except ValidationError as e:
        errors = []
        for err in e.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            msg = err["msg"]
            errors.append(f"  - {field}: {msg}")
        error_text = "\n".join(errors)
        raise ConfigError(
            f"Invalid CLI override:\n\n{error_text}"
        ) from None
