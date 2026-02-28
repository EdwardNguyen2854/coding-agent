"""Tests for slash command system."""

from unittest.mock import MagicMock, patch

import pytest

from coding_agent.ui.slash_commands import (
    AT_COMMANDS,
    BANG_COMMANDS,
    COMMANDS,
    CommandPrefix,
    HASH_COMMANDS,
    SLASH_COMMANDS,
    cmd_exit,
    cmd_help,
    cmd_init,
    execute_command,
    is_command,
    is_slash_command,
    parse_command,
    register_skills,
)


@pytest.fixture()
def mock_conversation():
    """Mock ConversationManager."""
    mock = MagicMock()
    return mock


@pytest.fixture()
def mock_session_manager():
    """Mock SessionManager."""
    mock = MagicMock()
    mock.list.return_value = []
    return mock


@pytest.fixture()
def mock_renderer():
    """Mock Renderer."""
    mock = MagicMock()
    return mock


@pytest.fixture()
def mock_llm_client():
    """Mock LLMClient."""
    mock = MagicMock()
    mock.model = "litellm/gpt-4o"
    return mock


class TestIsCommand:
    """Tests for is_command function."""

    def test_slash_command_returns_true(self):
        """Slash commands return True."""
        assert is_command("/help") is True
        assert is_command("/model gpt-4") is True
        assert is_command("/exit") is True

    def test_at_command_returns_true(self):
        """@ commands return True."""
        assert is_command("@default") is True
        assert is_command("@code task") is True

    def test_hash_command_returns_true(self):
        """# commands return True."""
        assert is_command("#symbol foo") is True
        assert is_command("#file bar") is True

    def test_bang_command_returns_true(self):
        """! commands return True."""
        assert is_command("!run ls") is True
        assert is_command("!test") is True

    def test_regular_text_returns_false(self):
        """Regular text returns False."""
        assert is_command("hello") is False
        assert is_command("hello world") is False

    def test_empty_string_returns_false(self):
        """Empty string returns False."""
        assert is_command("") is False
        assert is_command("   ") is False


class TestIsSlashCommand:
    """Tests for is_slash_command function (backward compatibility)."""

    def test_slash_command_returns_true(self):
        """Slash commands return True."""
        assert is_slash_command("/help") is True
        assert is_slash_command("/model gpt-4") is True
        assert is_slash_command("/exit") is True

    def test_regular_text_returns_false(self):
        """Regular text returns False."""
        assert is_slash_command("hello") is False
        assert is_slash_command("hello world") is False

    def test_empty_string_returns_false(self):
        """Empty string returns False."""
        assert is_slash_command("") is False
        assert is_slash_command("   ") is False

    def test_other_prefixes_return_false(self):
        """Other prefixes return False for is_slash_command."""
        assert is_slash_command("@default") is False
        assert is_slash_command("#symbol foo") is False
        assert is_slash_command("!run ls") is False


class TestParseCommand:
    """Tests for parse_command function."""

    def test_simple_slash_command(self):
        """Parse simple slash command without args."""
        prefix, cmd, args = parse_command("/help")
        assert prefix == CommandPrefix.SLASH
        assert cmd == "help"
        assert args == ""

    def test_slash_command_with_args(self):
        """Parse slash command with args."""
        prefix, cmd, args = parse_command("/model litellm/gpt-4o")
        assert prefix == CommandPrefix.SLASH
        assert cmd == "model"
        assert args == "litellm/gpt-4o"

    def test_at_command(self):
        """Parse @ command."""
        prefix, cmd, args = parse_command("@default")
        assert prefix == CommandPrefix.AT
        assert cmd == "default"
        assert args == ""

    def test_at_command_with_args(self):
        """Parse @ command with args."""
        prefix, cmd, args = parse_command("@code fix the bug")
        assert prefix == CommandPrefix.AT
        assert cmd == "code"
        assert args == "fix the bug"

    def test_hash_command(self):
        """Parse # command."""
        prefix, cmd, args = parse_command("#symbol MyClass")
        assert prefix == CommandPrefix.HASH
        assert cmd == "symbol"
        assert args == "MyClass"

    def test_bang_command(self):
        """Parse ! command."""
        prefix, cmd, args = parse_command("!run ls -la")
        assert prefix == CommandPrefix.BANG
        assert cmd == "run"
        assert args == "ls -la"

    def test_case_insensitive(self):
        """Commands are case insensitive."""
        prefix, cmd, args = parse_command("/HELP")
        assert prefix == CommandPrefix.SLASH
        assert cmd == "help"

    def test_whitespace_handling(self):
        """Whitespace is handled correctly."""
        prefix, cmd, args = parse_command("  /help  ")
        assert prefix == CommandPrefix.SLASH
        assert cmd == "help"
        assert args == ""

    def test_non_command_returns_none_prefix(self):
        """Non-command text returns None prefix."""
        prefix, cmd, args = parse_command("hello world")
        assert prefix is None
        assert cmd == ""
        assert args == ""

    def test_multiple_args(self):
        """Multiple args are captured."""
        prefix, cmd, args = parse_command("/model arg1 arg2")
        assert prefix == CommandPrefix.SLASH
        assert cmd == "model"
        assert args == "arg1 arg2"


class TestCommandRegistries:
    """Tests for command registries."""

    def test_slash_commands_exist(self):
        """SLASH_COMMANDS contains expected commands."""
        assert "help" in SLASH_COMMANDS
        assert "exit" in SLASH_COMMANDS
        assert "model" in SLASH_COMMANDS

    def test_at_commands_exist(self):
        """AT_COMMANDS contains expected commands."""
        assert "default" in AT_COMMANDS
        assert "code" in AT_COMMANDS
        assert "review" in AT_COMMANDS
        assert "analyze" in AT_COMMANDS

    def test_hash_commands_exist(self):
        """HASH_COMMANDS contains expected commands."""
        assert "symbol" in HASH_COMMANDS
        assert "file" in HASH_COMMANDS

    def test_bang_commands_exist(self):
        """BANG_COMMANDS contains expected commands."""
        assert "run" in BANG_COMMANDS
        assert "test" in BANG_COMMANDS
        assert "lint" in BANG_COMMANDS
        assert "tidy" in BANG_COMMANDS


class TestExecuteCommand:
    """Tests for execute_command function."""

    def test_execute_slash_command(self, mock_conversation, mock_session_manager, mock_renderer):
        """Execute slash command successfully."""
        result = execute_command("/help", mock_conversation, mock_session_manager, mock_renderer)
        assert result is True
        mock_renderer.console.print.assert_called()

    def test_execute_at_command(self, mock_conversation, mock_session_manager, mock_renderer):
        """Execute @ command."""
        result = execute_command("@default", mock_conversation, mock_session_manager, mock_renderer, agent=MagicMock())
        assert result is True

    def test_execute_hash_command(self, mock_conversation, mock_session_manager, mock_renderer):
        """Execute # command."""
        result = execute_command("#symbol MyClass", mock_conversation, mock_session_manager, mock_renderer, agent=MagicMock())
        assert result is True

    def test_execute_bang_command(self, mock_conversation, mock_session_manager, mock_renderer):
        """Execute ! command."""
        result = execute_command("!test", mock_conversation, mock_session_manager, mock_renderer, agent=MagicMock())
        assert result is True

    def test_unknown_command_shows_error(self, mock_conversation, mock_session_manager, mock_renderer):
        """Unknown command shows error."""
        result = execute_command("/nonexistent", mock_conversation, mock_session_manager, mock_renderer)
        assert result is True
        mock_renderer.print_error.assert_called()

    def test_non_command_returns_none(self, mock_conversation, mock_session_manager, mock_renderer):
        """Non-command text returns None."""
        result = execute_command("hello world", mock_conversation, mock_session_manager, mock_renderer)
        assert result is None

    def test_unknown_command_shows_error_with_llm(self, mock_conversation, mock_session_manager, mock_renderer, mock_llm_client):
        """Unknown command shows error message."""
        result = execute_command(
            "/unknown",
            mock_conversation,
            mock_session_manager,
            mock_renderer,
            mock_llm_client,
        )
        assert result is True  # Session continues

    def test_command_requires_arg_when_needed(self, mock_conversation, mock_session_manager, mock_renderer, mock_llm_client):
        """Command requiring arg shows error when arg missing."""
        result = execute_command(
            "/model",
            mock_conversation,
            mock_session_manager,
            mock_renderer,
            mock_llm_client,
        )
        assert result is True


class TestHelpCommand:
    """Tests for help command."""

    def test_cmd_help_displays_help(self, mock_conversation, mock_session_manager, mock_renderer):
        """Help command shows help text."""
        result = cmd_help("", mock_conversation, mock_session_manager, mock_renderer)
        assert result is True


class TestExitCommand:
    """Tests for exit command."""

    def test_cmd_exit_returns_false(self, mock_conversation, mock_session_manager, mock_renderer):
        """Exit command returns False to signal session end."""
        result = cmd_exit("", mock_conversation, mock_session_manager, mock_renderer)
        assert result is False


class TestModelCommand:
    """Tests for /model command."""

    def test_model_command_registered(self):
        """Model command is registered in COMMANDS."""
        assert "model" in COMMANDS

    def test_model_command_requires_arg(self):
        """Model command requires an argument."""
        from coding_agent.ui.slash_commands import COMMANDS

        assert COMMANDS["model"].arg_required is True

    def test_valid_model_switch(self, mock_conversation, mock_session_manager, mock_renderer, mock_llm_client):
        """Switching to valid model shows confirmation."""
        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = MagicMock()

            result = execute_command(
                "/model litellm/gpt-4o",
                mock_conversation,
                mock_session_manager,
                mock_renderer,
                mock_llm_client,
            )

            assert result is True
            assert mock_llm_client.model == "litellm/gpt-4o"

    def test_invalid_model_shows_error(self, mock_conversation, mock_session_manager, mock_renderer, mock_llm_client):
        """Invalid model shows error and keeps current model."""
        with patch("litellm.completion") as mock_completion:
            mock_completion.side_effect = Exception("Invalid model")

            result = execute_command(
                "/model invalid-model",
                mock_conversation,
                mock_session_manager,
                mock_renderer,
                mock_llm_client,
            )

            assert result is True
            # Model should not change
            assert mock_llm_client.model == "litellm/gpt-4o"

    def test_model_switch_preserves_conversation(self, mock_conversation, mock_session_manager, mock_renderer, mock_llm_client):
        """Model switching does not clear conversation history."""
        mock_conversation.get_messages.return_value = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = MagicMock()

            execute_command(
                "/model litellm/gpt-4o",
                mock_conversation,
                mock_session_manager,
                mock_renderer,
                mock_llm_client,
            )

            # Verify conversation was NOT cleared (history preserved)
            mock_conversation.clear.assert_not_called()


class TestInitCommand:
    """Tests for /init command."""

    def test_init_command_registered(self):
        """Init command is registered in COMMANDS."""
        assert "init" in COMMANDS

    def test_creates_agents_md(self, tmp_path, mock_conversation, mock_session_manager, mock_renderer):
        """Init creates AGENTS.md when it does not exist."""
        with patch("coding_agent.ui.slash_commands.find_git_root", return_value=tmp_path):
            result = cmd_init("", mock_conversation, mock_session_manager, mock_renderer)

        assert result is True
        agents_md = tmp_path / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        assert "AGENTS.md" in content

    def test_init_fails_if_file_exists(self, tmp_path, mock_conversation, mock_session_manager, mock_renderer):
        """Init shows error when AGENTS.md already exists."""
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("existing content")

        with patch("coding_agent.ui.slash_commands.find_git_root", return_value=tmp_path):
            result = cmd_init("", mock_conversation, mock_session_manager, mock_renderer)

        assert result is True
        mock_renderer.print_error.assert_called_once()
        # Original content should be preserved
        assert agents_md.read_text() == "existing content"

    def test_init_uses_cwd_when_no_git_root(self, tmp_path, mock_conversation, mock_session_manager, mock_renderer):
        """Init falls back to cwd when no git root is found."""
        with patch("coding_agent.ui.slash_commands.find_git_root", return_value=None):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                result = cmd_init("", mock_conversation, mock_session_manager, mock_renderer)

        assert result is True
        assert (tmp_path / "AGENTS.md").exists()


class TestRegisterSkills:
    """Tests for register_skills function."""

    def test_skills_registered_as_commands(self, mock_conversation, mock_session_manager, mock_renderer):
        """Skills from SKILL.md are registered in COMMANDS."""
        mock_agent = MagicMock()
        
        # Import Skill class to create proper mock
        from coding_agent.config.skills import Skill
        skills = {"myskill": Skill(name="myskill", description="Do something useful.", instructions="Do something useful.")}

        original_keys = set(COMMANDS.keys())
        registered = []
        try:
            registered = register_skills(skills, mock_agent)
            assert "myskill" in COMMANDS
            assert "myskill" in registered
        finally:
            for name in registered:
                COMMANDS.pop(name, None)

    def test_skill_command_runs_agent(self, mock_conversation, mock_session_manager, mock_renderer):
        """Invoking a skill command calls agent.run with skill content."""
        mock_agent = MagicMock()
        
        # Import Skill class to create proper mock
        from coding_agent.config.skills import Skill
        skills = {"testskill": Skill(name="testskill", description="Test skill", instructions="Test skill instructions.")}

        registered = register_skills(skills, mock_agent)
        try:
            result = execute_command(
                "/testskill",
                mock_conversation,
                mock_session_manager,
                mock_renderer,
                agent=mock_agent,
            )
            assert result is True
            mock_agent.run.assert_called_once()
            call_args = mock_agent.run.call_args[0][0]
            assert "Test skill instructions." in call_args
        finally:
            for name in registered:
                COMMANDS.pop(name, None)

    def test_skill_command_appends_user_args(self, mock_conversation, mock_session_manager, mock_renderer):
        """Extra args passed to a skill are appended to the prompt."""
        mock_agent = MagicMock()
        
        # Import Skill class to create proper mock
        from coding_agent.config.skills import Skill
        skills = {"checkskill": Skill(name="checkskill", description="Check skill", instructions="Base instructions.")}

        registered = register_skills(skills, mock_agent)
        try:
            execute_command(
                "/checkskill focus on security",
                mock_conversation,
                mock_session_manager,
                mock_renderer,
                agent=mock_agent,
            )
            call_args = mock_agent.run.call_args[0][0]
            assert "Base instructions." in call_args
            assert "focus on security" in call_args
        finally:
            for name in registered:
                COMMANDS.pop(name, None)

    def test_empty_skill_name_skipped(self, mock_conversation, mock_session_manager, mock_renderer):
        """Skills with empty names are not registered."""
        mock_agent = MagicMock()
        
        # Import Skill class to create proper mock
        from coding_agent.config.skills import Skill
        skills = {"": Skill(name="", description="", instructions="Some content.")}

        registered = register_skills(skills, mock_agent)
        assert "" not in COMMANDS
        assert registered == []
