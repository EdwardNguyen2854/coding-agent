"""Configuration management - Pydantic model with YAML loading and CLI overrides."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

DEFAULT_CONFIG_DIR = Path.home() / ".coding-agent"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"

OLLAMA_DEFAULT_API_BASE = "http://localhost:11434"


class SkillSetting(BaseModel):
    """Individual skill configuration."""
    name: str
    description: str
    enabled: bool = True


class SkillsConfig(BaseModel):
    """Skills configuration."""
    skills: list[SkillSetting] = []

    def __init__(self, **data):
        if not data.get("skills"):
            data["skills"] = DEFAULT_SKILLS.copy()
        super().__init__(**data)

    def get_enabled(self) -> list[str]:
        """Return list of enabled skill names."""
        return [s.name for s in self.skills if s.enabled]


DEFAULT_SKILLS = [
    SkillSetting(name="algorithmic-art", description="Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration. Use this when users request creating art using code, generative art, algorithmic art, flow fields, or particle systems. Create original algorithmic art rather than copying existing artists' work to avoid copyright violations.", enabled=True),
    SkillSetting(name="brand-guidelines", description="Applies Anthropic's official brand colors and typography to any sort of artifact that may benefit from having Anthropic's look-and-feel. Use it when brand colors or style guidelines, visual formatting, or company design standards apply.", enabled=True),
    SkillSetting(name="canvas-design", description="Create beautiful visual art in .png and .pdf documents using design philosophy. You should use this skill when the user asks to create a poster, piece of art, design, or other static piece. Create original visual designs, never copying existing artists' work to avoid copyright violations.", enabled=True),
    SkillSetting(name="doc-coauthoring", description="Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documentation, proposals, technical specs, decision docs, or similar structured content.", enabled=True),
    SkillSetting(name="docx", description="Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx files).", enabled=True),
    SkillSetting(name="frontend-design", description="Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, artifacts, posters, or applications.", enabled=True),
    SkillSetting(name="internal-comms", description="A set of resources to help me write all kinds of internal communications, using the formats that my company likes to use.", enabled=True),
    SkillSetting(name="mcp-builder", description="Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services through well-designed tools.", enabled=True),
    SkillSetting(name="pdf", description="Use this skill whenever the user wants to do anything with PDF files.", enabled=True),
    SkillSetting(name="pptx", description="Use this skill any time a .pptx file is involved in any way - as input, output, or both.", enabled=True),
    SkillSetting(name="skill-creator", description="Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Claude's capabilities.", enabled=True),
    SkillSetting(name="slack-gif-creator", description="Knowledge and utilities for creating animated GIFs optimized for Slack.", enabled=True),
    SkillSetting(name="theme-factory", description="Toolkit for styling artifacts with a theme. These artifacts can be slides, docs, reportings, HTML landing pages, etc.", enabled=True),
    SkillSetting(name="web-artifacts-builder", description="Suite of tools for creating elaborate, multi-component claude.ai HTML artifacts using modern frontend web technologies.", enabled=True),
    SkillSetting(name="webapp-testing", description="Toolkit for interacting with and testing local web applications using Playwright.", enabled=True),
    SkillSetting(name="xlsx", description="Use this skill any time a spreadsheet file is the primary input or output.", enabled=True),
]


def is_ollama_model(model: str) -> bool:
    """Return True if the model string uses the Ollama provider prefix."""
    return model.startswith(("ollama/", "ollama_chat/"))


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""


class AgentConfig(BaseModel):
    """Agent configuration with validation."""

    model_config = ConfigDict(extra="forbid")

    model: str
    api_base: str
    api_key: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _apply_ollama_defaults(cls, values: dict) -> dict:
        """Auto-set api_base for Ollama models when not explicitly provided."""
        if isinstance(values, dict) and "api_base" not in values:
            if is_ollama_model(values.get("model", "")):
                values = dict(values)
                values["api_base"] = OLLAMA_DEFAULT_API_BASE
        return values
    https_proxy: str | None = None

    # Model sampling parameters
    temperature: float = 0.0
    max_output_tokens: int = 4096
    top_p: float = 1.0

    # Context management
    max_context_tokens: int = 128000

    # Skills configuration
    skills: SkillsConfig = SkillsConfig()

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
            f"api_key={api_key_display!r}, "
            f"temperature={self.temperature!r}, "
            f"max_output_tokens={self.max_output_tokens!r}, "
            f"top_p={self.top_p!r})"
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
            f"For LiteLLM proxy / OpenAI-compatible APIs:\n"
            f"  model: litellm/gpt-4o\n"
            f"  api_base: http://localhost:4000\n\n"
            f"For local Ollama models (api_base defaults to {OLLAMA_DEFAULT_API_BASE}):\n"
            f"  model: ollama_chat/llama3.2\n\n"
            f"Optional fields: api_key, https_proxy"
        )

    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    if not isinstance(data, dict):
        raise ConfigError(
            f"Invalid configuration in {path}\n\n"
            f"  Config file is empty or not a valid YAML mapping.\n\n"
            f"For LiteLLM proxy / OpenAI-compatible APIs:\n"
            f"  model: litellm/gpt-4o\n"
            f"  api_base: http://localhost:4000\n\n"
            f"For local Ollama models (api_base defaults to {OLLAMA_DEFAULT_API_BASE}):\n"
            f"  model: ollama_chat/llama3.2"
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
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    top_p: float | None = None,
) -> AgentConfig:
    """Apply CLI flag overrides to config. Returns a new AgentConfig instance.

    Override precedence: Defaults → YAML → CLI flags.
    """
    overrides = {}
    if model is not None:
        overrides["model"] = model
    if api_base is not None:
        overrides["api_base"] = api_base
    if temperature is not None:
        overrides["temperature"] = temperature
    if max_output_tokens is not None:
        overrides["max_output_tokens"] = max_output_tokens
    if top_p is not None:
        overrides["top_p"] = top_p

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
