"""Tests for CLI entry point, project structure, and REPL loop."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from coding_agent.cli import main


@pytest.fixture()
def mock_renderer():
    """Mock Renderer to avoid Rich terminal behavior in tests."""
    with patch("coding_agent.cli.Renderer") as mock_cls:
        yield mock_cls


@pytest.fixture()
def mock_conversation():
    """Mock ConversationManager to avoid actual message history in tests."""
    with patch("coding_agent.cli.ConversationManager") as mock_cls:
        mock_conv = MagicMock()
        mock_conv.get_messages.return_value = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
        mock_cls.return_value = mock_conv
        yield mock_conv


@pytest.fixture()
def mock_config(tmp_path, monkeypatch):
    """Provide a valid config file for CLI tests."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump({"model": "litellm/gpt-4o", "api_base": "http://localhost:4000"})
    )
    monkeypatch.setattr("coding_agent.config.DEFAULT_CONFIG_FILE", config_file)
    return config_file


@pytest.fixture()
def mock_llm_client():
    """Mock LLMClient to prevent real network calls in CLI tests."""
    with patch("coding_agent.cli.LLMClient") as mock_cls:
        mock_cls.return_value.verify_connection.return_value = None
        mock_cls.return_value.send_message_stream.return_value = iter([])
        mock_cls.return_value.last_response = MagicMock()
        mock_cls.return_value.last_response.choices = [MagicMock()]
        mock_cls.return_value.last_response.choices[0].message.content = ""
        yield mock_cls


@pytest.fixture()
def mock_prompt_session():
    """Mock PromptSession to simulate user input without real terminal."""
    with patch("coding_agent.cli.PromptSession") as mock_cls:
        mock_session = MagicMock()
        mock_session.prompt.side_effect = EOFError()  # Default: immediate Ctrl+D
        mock_cls.return_value = mock_session
        yield mock_session


class TestProjectStructure:
    """Verify project skeleton follows architecture requirements."""

    def test_src_layout_exists(self):
        """AC #3: src layout with src/coding_agent/ as main package."""
        project_root = Path(__file__).parent.parent
        assert (project_root / "src" / "coding_agent" / "__init__.py").exists()

    def test_tools_package_exists(self):
        """Tools subpackage exists."""
        project_root = Path(__file__).parent.parent
        assert (project_root / "src" / "coding_agent" / "tools" / "__init__.py").exists()

    def test_tools_base_exists(self):
        """Tools base module exists."""
        project_root = Path(__file__).parent.parent
        assert (project_root / "src" / "coding_agent" / "tools" / "base.py").exists()

    def test_utils_exists(self):
        """Utils module exists."""
        project_root = Path(__file__).parent.parent
        assert (project_root / "src" / "coding_agent" / "utils.py").exists()

    def test_pyproject_toml_exists(self):
        """AC #4: pyproject.toml exists."""
        project_root = Path(__file__).parent.parent
        assert (project_root / "pyproject.toml").exists()


class TestPackageMetadata:
    """Verify package metadata and version."""

    def test_version_defined(self):
        """Package version is accessible."""
        from coding_agent import __version__
        assert __version__ == "0.1.0"

    def test_package_importable(self):
        """Package can be imported."""
        import coding_agent
        assert coding_agent is not None


class TestCLI:
    """Verify CLI entry point works correctly."""

    def test_help_flag(self):
        """AC #2: coding-agent --help displays usage info."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "AI coding agent" in result.output
        assert "--model" in result.output
        assert "--api-base" in result.output

    def test_model_option_accepted(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """AC #2: --model flag is recognized."""
        runner = CliRunner()
        result = runner.invoke(main, ["--model", "litellm/gpt-4o"])
        assert result.exit_code == 0

    def test_api_base_option_accepted(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """AC #2: --api-base flag is recognized."""
        runner = CliRunner()
        result = runner.invoke(main, ["--api-base", "http://localhost:4000"])
        assert result.exit_code == 0

    def test_default_invocation(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """CLI runs without arguments."""
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert "Loaded config" in result.output


class TestCLIConnectivity:
    """Story 1.3: Verify CLI integrates connectivity check on startup."""

    def test_successful_startup_shows_connected(
        self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer
    ):
        """AC #1: Successful connection shows confirmation message."""
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        mock_renderer.return_value.print_info.assert_any_call(
            "Connected to LiteLLM at http://localhost:4000"
        )

    def test_connection_failure_shows_error_and_exits(self, mock_config):
        """AC #2: Connection failure shows error and exits with code 1."""
        with patch("coding_agent.cli.LLMClient") as mock_cls:
            mock_cls.return_value.verify_connection.side_effect = ConnectionError(
                "Cannot connect to LiteLLM server.\n\n"
                "  Server: http://localhost:4000"
            )
            runner = CliRunner()
            result = runner.invoke(main, [])
            assert result.exit_code == 1
            assert "Cannot connect" in result.output

    def test_auth_failure_shows_distinct_error_and_exits(self, mock_config):
        """AC #3: Auth failure shows distinct auth error and exits with code 1."""
        with patch("coding_agent.cli.LLMClient") as mock_cls:
            mock_cls.return_value.verify_connection.side_effect = ConnectionError(
                "Authentication failed connecting to LiteLLM server.\n\n"
                "  Server: http://localhost:4000"
            )
            runner = CliRunner()
            result = runner.invoke(main, [])
            assert result.exit_code == 1
            assert "Authentication failed" in result.output
            assert "Cannot connect" not in result.output

    def test_llm_client_receives_config(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """LLMClient is instantiated with the loaded config."""
        runner = CliRunner()
        runner.invoke(main, [])
        config_arg = mock_llm_client.call_args[0][0]
        assert config_arg.model == "litellm/gpt-4o"
        assert config_arg.api_base == "http://localhost:4000"

    def test_verify_connection_called(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """verify_connection() is called during startup."""
        runner = CliRunner()
        runner.invoke(main, [])
        mock_llm_client.return_value.verify_connection.assert_called_once()

    def test_connectivity_check_after_config_loading(self, mock_config, mock_prompt_session):
        """Connectivity check happens after config is loaded (config errors take precedence)."""
        with patch("coding_agent.cli.LLMClient") as mock_cls:
            mock_cls.return_value.verify_connection.side_effect = ConnectionError("fail")
            runner = CliRunner()
            result = runner.invoke(main, [])
            # Config loaded successfully (shown before connection error)
            assert "Loaded config" in result.output


class TestPythonModule:
    """Verify python -m coding_agent support."""

    def test_main_module_exists(self):
        """AC #5: __main__.py exists for python -m support."""
        project_root = Path(__file__).parent.parent
        assert (project_root / "src" / "coding_agent" / "__main__.py").exists()

    def test_python_m_help(self):
        """AC #5: python -m coding_agent --help works and matches CLI output."""
        result = subprocess.run(
            [sys.executable, "-m", "coding_agent", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--model" in result.stdout
        assert "--api-base" in result.stdout


class TestREPLLoop:
    """Story 2.1: Interactive REPL loop with prompt-toolkit."""

    def test_exit_command_ends_session(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """AC #3: 'exit' command ends session gracefully."""
        mock_prompt_session.prompt.side_effect = ["exit"]
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0

    def test_quit_command_ends_session(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """AC #3: 'quit' command ends session gracefully."""
        mock_prompt_session.prompt.side_effect = ["quit"]
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0

    def test_exit_case_insensitive(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """AC #3: Exit commands are case-insensitive."""
        mock_prompt_session.prompt.side_effect = ["EXIT"]
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0

    def test_ctrl_d_ends_session(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """AC #3: Ctrl+D (EOFError) ends session gracefully."""
        mock_prompt_session.prompt.side_effect = EOFError()
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0

    def test_ctrl_c_shows_hint_and_continues(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """AC #3: Ctrl+C shows hint message and continues the loop."""
        mock_prompt_session.prompt.side_effect = [KeyboardInterrupt(), "exit"]
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert "Ctrl+D" in result.output

    def test_empty_input_skipped(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """Empty input is skipped without sending to LLM."""
        mock_prompt_session.prompt.side_effect = ["", "   ", "exit"]
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        mock_llm_client.return_value.send_message_stream.assert_not_called()

    def test_user_message_sent_to_llm(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """AC #1, #2: User message is sent to LLM."""
        mock_prompt_session.prompt.side_effect = ["Hello AI", "exit"]
        mock_llm_client.return_value.send_message_stream.return_value = iter(["Hi there!"])
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hi there!"
        mock_llm_client.return_value.last_response = mock_response

        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        mock_llm_client.return_value.send_message_stream.assert_called_once()
        # Verify the messages list contains the user message
        call_args = mock_llm_client.return_value.send_message_stream.call_args[0][0]
        user_msgs = [m for m in call_args if m["role"] == "user"]
        assert any("Hello AI" in m["content"] for m in user_msgs)

    def test_response_streamed_to_output(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """AC #2: Response is streamed back in real-time."""
        mock_prompt_session.prompt.side_effect = ["test", "exit"]
        mock_llm_client.return_value.send_message_stream.return_value = iter(["Hello", " world"])
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello world"
        mock_llm_client.return_value.last_response = mock_response

        runner = CliRunner()
        result = runner.invoke(main, [])
        assert "Hello world" in result.output

    def test_connection_error_during_chat_continues_repl(
        self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer
    ):
        """LLM connection error during chat shows error and continues REPL."""
        mock_prompt_session.prompt.side_effect = ["test", "exit"]
        mock_llm_client.return_value.send_message_stream.side_effect = [
            ConnectionError("Cannot connect to LiteLLM server."),
            iter([]),  # Won't be called since next input is "exit"
        ]

        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        mock_renderer.return_value.print_error.assert_called_with("Cannot connect to LiteLLM server.")

    def test_streaming_interrupted_shows_indicator(
        self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer
    ):
        """Visual indicator shown when streaming output is incomplete due to error."""
        mock_prompt_session.prompt.side_effect = ["test", "exit"]

        def failing_stream(messages):
            yield "partial output"
            raise ConnectionError("Connection lost")

        mock_llm_client.return_value.send_message_stream.side_effect = [
            failing_stream(None),
            iter([]),
        ]

        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        mock_renderer.return_value.print_error.assert_any_call("[streaming interrupted]")

    def test_messages_accumulate_history(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """Messages list accumulates conversation history across turns."""
        mock_prompt_session.prompt.side_effect = ["first message", "second message", "exit"]

        # Track messages snapshots at each call
        messages_snapshots = []

        mock_response_1 = MagicMock()
        mock_response_1.choices = [MagicMock()]
        mock_response_1.choices[0].message.content = "response 1"

        mock_response_2 = MagicMock()
        mock_response_2.choices = [MagicMock()]
        mock_response_2.choices[0].message.content = "response 2"

        call_count = 0

        def stream_side_effect(messages):
            nonlocal call_count
            call_count += 1
            # Snapshot the messages at call time (list is mutable)
            messages_snapshots.append([m.copy() for m in messages])
            if call_count == 1:
                mock_llm_client.return_value.last_response = mock_response_1
                return iter(["response 1"])
            else:
                mock_llm_client.return_value.last_response = mock_response_2
                return iter(["response 2"])

        mock_llm_client.return_value.send_message_stream.side_effect = stream_side_effect

        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert len(messages_snapshots) == 2

        # First call: system + user("first message")
        first_roles = [m["role"] for m in messages_snapshots[0]]
        assert first_roles == ["system", "user"]

        # Second call: system + user("first message") + assistant("response 1") + user("second message")
        second_roles = [m["role"] for m in messages_snapshots[1]]
        assert second_roles == ["system", "user", "assistant", "user"]
        assert messages_snapshots[1][2]["content"] == "response 1"

    def test_system_prompt_included(self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer):
        """A system prompt is included in the messages sent to LLM."""
        mock_prompt_session.prompt.side_effect = ["hello", "exit"]
        mock_llm_client.return_value.send_message_stream.return_value = iter(["hi"])
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "hi"
        mock_llm_client.return_value.last_response = mock_response

        runner = CliRunner()
        runner.invoke(main, [])
        call_args = mock_llm_client.return_value.send_message_stream.call_args[0][0]
        assert call_args[0]["role"] == "system"

    def test_streamed_response_rendered_as_markdown_after_streaming(
        self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer
    ):
        """Renders complete streamed response after raw streaming completes."""
        mock_prompt_session.prompt.side_effect = ["test", "exit"]
        mock_llm_client.return_value.send_message_stream.return_value = iter(["Hello", " world"])
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello world"
        mock_llm_client.return_value.last_response = mock_response

        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code == 0
        mock_renderer.return_value.render_streaming_markdown.assert_called_once_with("Hello world")

    def test_chat_error_uses_renderer_print_error(
        self, mock_config, mock_llm_client, mock_prompt_session, mock_renderer
    ):
        """Errors during chat are displayed via renderer.print_error()."""
        mock_prompt_session.prompt.side_effect = ["test", "exit"]
        mock_llm_client.return_value.send_message_stream.side_effect = ConnectionError("Cannot connect")

        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code == 0
        mock_renderer.return_value.print_error.assert_called_with("Cannot connect")
