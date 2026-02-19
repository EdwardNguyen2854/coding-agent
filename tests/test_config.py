"""Tests for configuration system."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError

from coding_agent.config import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
    AgentConfig,
    ConfigError,
    apply_cli_overrides,
    load_config,
)


class TestAgentConfigModel:
    """Test Pydantic config model validation."""

    def test_valid_config_required_fields(self):
        """AC #2: Valid config with model and api_base creates successfully."""
        config = AgentConfig(model="litellm/gpt-4o", api_base="http://localhost:4000")
        assert config.model == "litellm/gpt-4o"
        assert config.api_base == "http://localhost:4000"
        assert config.api_key is None
        # Default model parameters
        assert config.temperature == 0.0
        assert config.max_output_tokens == 4096
        assert config.top_p == 1.0

    def test_valid_config_all_fields(self):
        """AC #2: Valid config with all fields including api_key."""
        config = AgentConfig(
            model="litellm/gpt-4o",
            api_base="https://llm.internal.com",
            api_key="sk-secret-key-123",
            temperature=0.7,
            max_output_tokens=8192,
            top_p=0.9,
        )
        assert config.model == "litellm/gpt-4o"
        assert config.api_base == "https://llm.internal.com"
        assert config.api_key == "sk-secret-key-123"
        assert config.temperature == 0.7
        assert config.max_output_tokens == 8192
        assert config.top_p == 0.9

    def test_missing_required_model(self):
        """AC #2: Missing model field raises validation error."""
        with pytest.raises(ValidationError):
            AgentConfig(api_base="http://localhost:4000")

    def test_missing_required_api_base(self):
        """AC #2: Missing api_base field raises validation error."""
        with pytest.raises(ValidationError):
            AgentConfig(model="litellm/gpt-4o")

    def test_unknown_field_rejected(self):
        """Extra fields are rejected (ConfigDict extra=forbid)."""
        with pytest.raises(ValidationError):
            AgentConfig(
                model="litellm/gpt-4o",
                api_base="http://localhost:4000",
                unknown_field="value",
            )

    def test_invalid_api_base_no_protocol(self):
        """api_base must start with http:// or https://."""
        with pytest.raises(ValidationError):
            AgentConfig(model="litellm/gpt-4o", api_base="localhost:4000")

    def test_api_base_trailing_slash_stripped(self):
        """api_base trailing slash is stripped."""
        config = AgentConfig(model="litellm/gpt-4o", api_base="http://localhost:4000/")
        assert config.api_base == "http://localhost:4000"

    def test_api_key_masked_in_repr(self):
        """AC #4: api_key is never displayed in repr."""
        config = AgentConfig(
            model="litellm/gpt-4o",
            api_base="http://localhost:4000",
            api_key="sk-secret-key-123",
            temperature=0.7,
        )
        repr_str = repr(config)
        assert "sk-secret-key-123" not in repr_str
        assert "***" in repr_str
        # Check model parameters are shown
        assert "temperature=0.7" in repr_str

    def test_api_key_masked_in_str(self):
        """AC #4: api_key is never displayed in str output."""
        config = AgentConfig(
            model="litellm/gpt-4o",
            api_base="http://localhost:4000",
            api_key="sk-secret-key-123",
        )
        str_output = str(config)
        assert "sk-secret-key-123" not in str_output

    def test_no_api_key_repr_shows_none(self):
        """repr shows None for api_key when not set."""
        config = AgentConfig(model="litellm/gpt-4o", api_base="http://localhost:4000")
        repr_str = repr(config)
        assert "None" in repr_str

    def test_default_config_paths(self):
        """Default config paths are correct."""
        assert DEFAULT_CONFIG_DIR == Path.home() / ".coding-agent"
        assert DEFAULT_CONFIG_FILE == Path.home() / ".coding-agent" / "config.yaml"


class TestLoadConfig:
    """Test config loading from YAML files."""

    def test_missing_config_file_raises_error(self, tmp_path):
        """AC #1: Missing config file raises clear error with path and required fields."""
        fake_path = tmp_path / "nonexistent" / "config.yaml"
        with pytest.raises(ConfigError) as exc_info:
            load_config(fake_path)
        error_msg = str(exc_info.value)
        assert str(fake_path) in error_msg
        assert "model" in error_msg
        assert "api_base" in error_msg

    def test_valid_yaml_loads_successfully(self, tmp_path):
        """AC #2: Valid YAML with required fields loads successfully."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"model": "litellm/gpt-4o", "api_base": "http://localhost:4000"})
        )
        config = load_config(config_file)
        assert config.model == "litellm/gpt-4o"
        assert config.api_base == "http://localhost:4000"

    def test_valid_yaml_with_model_params(self, tmp_path):
        """AC: Valid YAML with model parameters loads successfully."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({
                "model": "litellm/gpt-4o",
                "api_base": "http://localhost:4000",
                "temperature": 0.7,
                "max_output_tokens": 8192,
                "top_p": 0.9,
            })
        )
        config = load_config(config_file)
        assert config.temperature == 0.7
        assert config.max_output_tokens == 8192
        assert config.top_p == 0.9

    def test_yaml_missing_model_params_uses_defaults(self, tmp_path):
        """AC: Missing model params uses defaults (temperature=0, max_output_tokens=4096, top_p=1.0)."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"model": "litellm/gpt-4o", "api_base": "http://localhost:4000"})
        )
        config = load_config(config_file)
        assert config.temperature == 0.0
        assert config.max_output_tokens == 4096
        assert config.top_p == 1.0

    def test_valid_yaml_with_api_key(self, tmp_path):
        """AC #2: Valid YAML with api_key loads and stores the key."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({
                "model": "litellm/gpt-4o",
                "api_base": "http://localhost:4000",
                "api_key": "sk-secret-123",
            })
        )
        config = load_config(config_file)
        assert config.api_key == "sk-secret-123"

    def test_invalid_yaml_missing_field(self, tmp_path):
        """AC #1: Missing required field shows clear validation error."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"api_base": "http://localhost:4000"}))
        with pytest.raises(ConfigError) as exc_info:
            load_config(config_file)
        assert "model" in str(exc_info.value).lower()

    def test_invalid_yaml_unknown_field(self, tmp_path):
        """Unknown fields in YAML are rejected."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({
                "model": "litellm/gpt-4o",
                "api_base": "http://localhost:4000",
                "unknown": "value",
            })
        )
        with pytest.raises(ConfigError):
            load_config(config_file)

    def test_invalid_api_base_in_yaml(self, tmp_path):
        """Invalid api_base in YAML is rejected."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"model": "litellm/gpt-4o", "api_base": "not-a-url"})
        )
        with pytest.raises(ConfigError):
            load_config(config_file)

    def test_empty_yaml_file(self, tmp_path):
        """Empty YAML file raises clear error."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        with pytest.raises(ConfigError):
            load_config(config_file)

    def test_api_key_not_in_error_message(self, tmp_path):
        """AC #4: api_key value never appears in error messages."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({
                "api_base": "not-a-url",
                "api_key": "sk-super-secret-key",
            })
        )
        with pytest.raises(ConfigError) as exc_info:
            load_config(config_file)
        assert "sk-super-secret-key" not in str(exc_info.value)


class TestCLIOverrides:
    """Test CLI flag override behavior."""

    def _base_config(self) -> AgentConfig:
        return AgentConfig(
            model="litellm/default-model",
            api_base="http://localhost:4000",
            api_key="sk-key",
        )

    def test_model_override(self):
        """AC #3: CLI --model overrides config model."""
        config = self._base_config()
        result = apply_cli_overrides(config, model="litellm/gpt-4o", api_base=None)
        assert result.model == "litellm/gpt-4o"
        assert result.api_base == "http://localhost:4000"
        assert result.api_key == "sk-key"

    def test_api_base_override(self):
        """AC #3: CLI --api-base overrides config api_base."""
        config = self._base_config()
        result = apply_cli_overrides(config, model=None, api_base="https://new.server.com")
        assert result.model == "litellm/default-model"
        assert result.api_base == "https://new.server.com"

    def test_both_overrides(self):
        """AC #3: Both CLI flags override their respective values."""
        config = self._base_config()
        result = apply_cli_overrides(
            config, model="litellm/new-model", api_base="https://new.server.com"
        )
        assert result.model == "litellm/new-model"
        assert result.api_base == "https://new.server.com"
        assert result.api_key == "sk-key"

    def test_no_overrides(self):
        """No CLI flags means config unchanged."""
        config = self._base_config()
        result = apply_cli_overrides(config, model=None, api_base=None)
        assert result.model == config.model
        assert result.api_base == config.api_base
        assert result.api_key == config.api_key

    def test_override_precedence(self, tmp_path):
        """AC #3: Override precedence is Defaults → YAML → CLI."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"model": "yaml-model", "api_base": "http://yaml-server:4000"})
        )
        config = load_config(config_file)
        assert config.model == "yaml-model"

        result = apply_cli_overrides(config, model="cli-model", api_base=None)
        assert result.model == "cli-model"
        assert result.api_base == "http://yaml-server:4000"

    def test_original_config_unchanged(self):
        """Override returns new config, original is unchanged."""
        config = self._base_config()
        result = apply_cli_overrides(config, model="new-model", api_base=None)
        assert config.model == "litellm/default-model"
        assert result.model == "new-model"

    def test_temperature_override(self):
        """AC: CLI --temperature overrides config temperature."""
        config = self._base_config()
        result = apply_cli_overrides(config, temperature=0.7)
        assert result.temperature == 0.7
        assert result.max_output_tokens == 4096
        assert result.top_p == 1.0

    def test_max_output_tokens_override(self):
        """AC: CLI --max-output-tokens overrides config max_output_tokens."""
        config = self._base_config()
        result = apply_cli_overrides(config, max_output_tokens=8192)
        assert result.temperature == 0.0
        assert result.max_output_tokens == 8192
        assert result.top_p == 1.0

    def test_top_p_override(self):
        """AC: CLI --top-p overrides config top_p."""
        config = self._base_config()
        result = apply_cli_overrides(config, top_p=0.9)
        assert result.temperature == 0.0
        assert result.max_output_tokens == 4096
        assert result.top_p == 0.9

    def test_all_model_params_override(self):
        """AC: All model parameters can be overridden via CLI."""
        config = self._base_config()
        result = apply_cli_overrides(
            config,
            temperature=0.5,
            max_output_tokens=2048,
            top_p=0.8,
        )
        assert result.temperature == 0.5
        assert result.max_output_tokens == 2048
        assert result.top_p == 0.8

    def test_mixed_overrides(self):
        """AC: Mixed model and param overrides work together."""
        config = self._base_config()
        result = apply_cli_overrides(
            config,
            model="litellm/new-model",
            temperature=0.7,
            max_output_tokens=8192,
        )
        assert result.model == "litellm/new-model"
        assert result.temperature == 0.7
        assert result.max_output_tokens == 8192
        assert result.api_base == "http://localhost:4000"

    def test_invalid_api_base_override_rejected(self):
        """CLI --api-base with invalid URL is rejected by validation."""
        config = self._base_config()
        with pytest.raises(ConfigError):
            apply_cli_overrides(config, model=None, api_base="not-a-url")


class TestCLIIntegration:
    """Test CLI integration with config loading."""

    def test_cli_missing_config_shows_error(self, tmp_path, monkeypatch):
        """AC #1: CLI shows error with config path and required fields."""
        from click.testing import CliRunner

        from coding_agent.cli import main

        fake_path = tmp_path / "nonexistent" / "config.yaml"
        monkeypatch.setattr(
            "coding_agent.config.DEFAULT_CONFIG_FILE",
            fake_path,
        )
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code != 0
        combined = result.output
        assert str(fake_path) in combined
        assert "model" in combined
        assert "api_base" in combined

    @patch("coding_agent.cli.PromptSession")
    @patch("coding_agent.cli.LLMClient")
    def test_cli_valid_config_shows_summary(self, mock_llm, mock_session, tmp_path, monkeypatch):
        """AC #2: CLI shows config summary on successful load."""
        from click.testing import CliRunner

        from coding_agent.cli import main

        mock_session.return_value.prompt.side_effect = EOFError()
        mock_llm.return_value.verify_connection.return_value = None
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"model": "litellm/gpt-4o", "api_base": "http://localhost:4000"})
        )
        monkeypatch.setattr("coding_agent.config.DEFAULT_CONFIG_FILE", config_file)
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert "litellm/gpt-4o" in result.output
        assert "localhost:4000" in result.output

    @patch("coding_agent.cli.PromptSession")
    @patch("coding_agent.cli.LLMClient")
    def test_cli_model_override(self, mock_llm, mock_session, tmp_path, monkeypatch):
        """AC #3: CLI --model flag overrides config."""
        from click.testing import CliRunner

        from coding_agent.cli import main

        mock_session.return_value.prompt.side_effect = EOFError()
        mock_llm.return_value.verify_connection.return_value = None
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"model": "default-model", "api_base": "http://localhost:4000"})
        )
        monkeypatch.setattr("coding_agent.config.DEFAULT_CONFIG_FILE", config_file)
        runner = CliRunner()
        result = runner.invoke(main, ["--model", "override-model"])
        assert result.exit_code == 0
        assert "override-model" in result.output

    @patch("coding_agent.cli.PromptSession")
    @patch("coding_agent.cli.LLMClient")
    def test_cli_temperature_override(self, mock_llm, mock_session, tmp_path, monkeypatch):
        """AC: CLI --temperature flag shows in output."""
        from click.testing import CliRunner

        from coding_agent.cli import main

        mock_session.return_value.prompt.side_effect = EOFError()
        mock_llm.return_value.verify_connection.return_value = None
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"model": "litellm/gpt-4o", "api_base": "http://localhost:4000"})
        )
        monkeypatch.setattr("coding_agent.config.DEFAULT_CONFIG_FILE", config_file)
        runner = CliRunner()
        result = runner.invoke(main, ["--temperature", "0.7"])
        assert result.exit_code == 0
        assert "0.7" in result.output

    @patch("coding_agent.cli.PromptSession")
    @patch("coding_agent.cli.LLMClient")
    def test_cli_max_output_tokens_override(self, mock_llm, mock_session, tmp_path, monkeypatch):
        """AC: CLI --max-output-tokens flag shows in output."""
        from click.testing import CliRunner

        from coding_agent.cli import main

        mock_session.return_value.prompt.side_effect = EOFError()
        mock_llm.return_value.verify_connection.return_value = None
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"model": "litellm/gpt-4o", "api_base": "http://localhost:4000"})
        )
        monkeypatch.setattr("coding_agent.config.DEFAULT_CONFIG_FILE", config_file)
        runner = CliRunner()
        result = runner.invoke(main, ["--max-output-tokens", "8192"])
        assert result.exit_code == 0
        assert "8192" in result.output

    @patch("coding_agent.cli.PromptSession")
    @patch("coding_agent.cli.LLMClient")
    def test_cli_top_p_override(self, mock_llm, mock_session, tmp_path, monkeypatch):
        """AC: CLI --top-p flag shows in output."""
        from click.testing import CliRunner

        from coding_agent.cli import main

        mock_session.return_value.prompt.side_effect = EOFError()
        mock_llm.return_value.verify_connection.return_value = None
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"model": "litellm/gpt-4o", "api_base": "http://localhost:4000"})
        )
        monkeypatch.setattr("coding_agent.config.DEFAULT_CONFIG_FILE", config_file)
        runner = CliRunner()
        result = runner.invoke(main, ["--top-p", "0.9"])
        assert result.exit_code == 0
        assert "0.9" in result.output

    @patch("coding_agent.cli.PromptSession")
    @patch("coding_agent.cli.LLMClient")
    def test_cli_api_key_never_shown(self, mock_llm, mock_session, tmp_path, monkeypatch):
        """AC #4: api_key never appears in CLI output."""
        from click.testing import CliRunner

        from coding_agent.cli import main

        mock_session.return_value.prompt.side_effect = EOFError()
        mock_llm.return_value.verify_connection.return_value = None
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({
                "model": "litellm/gpt-4o",
                "api_base": "http://localhost:4000",
                "api_key": "sk-super-secret-key-12345",
            })
        )
        monkeypatch.setattr("coding_agent.config.DEFAULT_CONFIG_FILE", config_file)
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert "sk-super-secret-key-12345" not in result.output
