"""Tests for LLM client connectivity verification and streaming."""

from unittest.mock import MagicMock, patch

import litellm
import pytest

import coding_agent.config.config as _config_module
from coding_agent.config import AgentConfig
from coding_agent.config.config import ModelCapabilities
from coding_agent.core.llm import LLMClient, _is_minimax_openrouter, _parse_minimax_tool_calls


@pytest.fixture(autouse=True)
def clear_capabilities_cache():
    """Clear the model capabilities cache before and after each test to prevent cross-test pollution."""
    _config_module._model_capabilities_cache.clear()
    yield
    _config_module._model_capabilities_cache.clear()


@pytest.fixture()
def config():
    """Provide a valid AgentConfig for tests."""
    return AgentConfig(model="litellm/gpt-4o", api_base="http://localhost:4000")


@pytest.fixture()
def config_with_key():
    """Provide a valid AgentConfig with API key for tests."""
    return AgentConfig(
        model="litellm/gpt-4o",
        api_base="http://localhost:4000",
        api_key="sk-secret-key-12345",
    )


class TestLLMClientInit:
    """Verify LLMClient stores config values correctly."""

    def test_stores_model(self, config):
        client = LLMClient(config)
        assert client.model == "litellm/gpt-4o"

    def test_stores_api_base(self, config):
        client = LLMClient(config)
        assert client.api_base == "http://localhost:4000"

    def test_stores_api_key(self, config_with_key):
        client = LLMClient(config_with_key)
        assert client.api_key == "sk-secret-key-12345"

    def test_stores_none_api_key(self, config):
        client = LLMClient(config)
        assert client.api_key is None


class TestVerifyConnectionSuccess:
    """AC #1: Successful connectivity verification."""

    @patch("coding_agent.core.llm.litellm.completion")
    def test_returns_without_error(self, mock_completion, config):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config)
        client.verify_connection()  # Should not raise

    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_correct_model(self, mock_completion, config):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "litellm/gpt-4o"

    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_correct_api_base(self, mock_completion, config):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["api_base"] == "http://localhost:4000"

    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_api_key(self, mock_completion, config_with_key):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config_with_key)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["api_key"] == "sk-secret-key-12345"

    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_none_api_key(self, mock_completion, config):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["api_key"] is None

    @patch("coding_agent.core.llm.litellm.completion")
    def test_uses_max_tokens_1(self, mock_completion, config):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["max_tokens"] == 1

    @patch("coding_agent.core.llm.litellm.completion")
    def test_uses_short_timeout(self, mock_completion, config):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["timeout"] == 10

    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_temperature(self, mock_completion, config):
        """AC: temperature is passed to LiteLLM."""
        mock_completion.return_value = MagicMock()
        config.temperature = 0.7
        client = LLMClient(config)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["temperature"] == 0.7

    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_top_p(self, mock_completion, config):
        """AC: top_p is passed to LiteLLM."""
        mock_completion.return_value = MagicMock()
        config.top_p = 0.9
        client = LLMClient(config)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["top_p"] == 0.9


class TestVerifyConnectionUnreachable:
    """AC #2: Unreachable server produces clear error with URL and suggestions."""

    @patch("coding_agent.core.llm.litellm.completion")
    def test_raises_connection_error(self, mock_completion, config):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_error_contains_server_url(self, mock_completion, config):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="http://localhost:4000"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_error_contains_cannot_connect(self, mock_completion, config):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="Cannot connect"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_error_contains_suggestions(self, mock_completion, config):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="Verify the server is running"):
            client.verify_connection()


class TestOllamaConnectionError:
    """Ollama-specific APIConnectionError gives actionable hints."""

    @pytest.fixture()
    def ollama_config(self):
        return AgentConfig(model="ollama_chat/llama3.2")

    @patch("coding_agent.core.llm.litellm.completion")
    def test_ollama_error_mentions_ollama_serve(self, mock_completion, ollama_config):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="ollama_chat/llama3.2",
            llm_provider="ollama",
        )
        client = LLMClient(ollama_config)
        with pytest.raises(ConnectionError, match="ollama serve"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_ollama_error_mentions_ollama_pull(self, mock_completion, ollama_config):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="ollama_chat/llama3.2",
            llm_provider="ollama",
        )
        client = LLMClient(ollama_config)
        with pytest.raises(ConnectionError, match="ollama pull llama3.2"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_ollama_error_does_not_mention_litellm(self, mock_completion, ollama_config):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="ollama_chat/llama3.2",
            llm_provider="ollama",
        )
        client = LLMClient(ollama_config)
        with pytest.raises(ConnectionError) as exc_info:
            client.verify_connection()
        assert "LiteLLM server" not in str(exc_info.value)

    @patch("coding_agent.core.llm.litellm.completion")
    def test_non_ollama_error_does_not_mention_ollama(self, mock_completion, config):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError) as exc_info:
            client.verify_connection()
        assert "ollama serve" not in str(exc_info.value)


class TestVerifyConnectionAuthError:
    """AC #3: Auth error is distinguishable from connectivity failure."""

    @patch("coding_agent.core.llm.litellm.completion")
    def test_raises_connection_error(self, mock_completion, config_with_key):
        mock_completion.side_effect = litellm.AuthenticationError(
            message="Invalid API key",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_error_contains_authentication_failed(self, mock_completion, config_with_key):
        mock_completion.side_effect = litellm.AuthenticationError(
            message="Invalid API key",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError, match="Authentication failed"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_error_distinguishable_from_connectivity(self, mock_completion, config_with_key):
        """Auth error message must NOT contain 'Cannot connect' to be distinguishable."""
        mock_completion.side_effect = litellm.AuthenticationError(
            message="Invalid API key",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError) as exc_info:
            client.verify_connection()
        assert "Cannot connect" not in str(exc_info.value)
        assert "Authentication failed" in str(exc_info.value)

    @patch("coding_agent.core.llm.litellm.completion")
    def test_error_contains_server_url(self, mock_completion, config_with_key):
        mock_completion.side_effect = litellm.AuthenticationError(
            message="Invalid API key",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError, match="http://localhost:4000"):
            client.verify_connection()


class TestVerifyConnectionTimeout:
    """Timeout produces clear error."""

    @patch("coding_agent.core.llm.litellm.completion")
    def test_raises_connection_error(self, mock_completion, config):
        mock_completion.side_effect = litellm.Timeout(
            message="Request timed out",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="timed out"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_error_contains_server_url(self, mock_completion, config):
        mock_completion.side_effect = litellm.Timeout(
            message="Request timed out",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="http://localhost:4000"):
            client.verify_connection()


class TestVerifyConnectionServerError:
    """Generic API error produces clear error."""

    @patch("coding_agent.core.llm.litellm.completion")
    def test_raises_connection_error(self, mock_completion, config):
        mock_completion.side_effect = litellm.APIError(
            status_code=500,
            message="Internal server error",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="request failed"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_error_contains_status_code(self, mock_completion, config):
        mock_completion.side_effect = litellm.APIError(
            status_code=503,
            message="Service unavailable",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="503"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_client_error_caught(self, mock_completion, config):
        """400-level errors (e.g., bad model name) are caught by APIError fallback."""
        mock_completion.side_effect = litellm.APIError(
            status_code=400,
            message="Bad request - invalid model",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="400"):
            client.verify_connection()


class TestVerifyConnectionBadRequestError:
    """BadRequestError (e.g. provider rejects message format) is handled cleanly."""

    @patch("coding_agent.core.llm.litellm.completion")
    def test_bad_request_raises_connection_error(self, mock_completion, config):
        mock_completion.side_effect = litellm.BadRequestError(
            message="Unrecognized chat message.",
            model="openrouter/stepfun/step-3.5-flash:free",
            llm_provider="openrouter",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="rejected the request"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_bad_request_message_contains_hint(self, mock_completion, config):
        mock_completion.side_effect = litellm.BadRequestError(
            message="Unrecognized chat message.",
            model="openrouter/stepfun/step-3.5-flash:free",
            llm_provider="openrouter",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="/model"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_bad_request_no_traceback_in_message(self, mock_completion, config):
        mock_completion.side_effect = litellm.BadRequestError(
            message="Unrecognized chat message.",
            model="openrouter/stepfun/step-3.5-flash:free",
            llm_provider="openrouter",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError) as exc_info:
            client.verify_connection()
        assert "Traceback" not in str(exc_info.value)


class TestVerifyConnectionUnexpectedException:
    """Unexpected exceptions are caught gracefully without leaking tracebacks."""

    @patch("coding_agent.core.llm.litellm.completion")
    def test_unexpected_error_raises_connection_error(self, mock_completion, config):
        mock_completion.side_effect = RuntimeError("something completely unexpected")
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="Unexpected error"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_unexpected_error_contains_server_url(self, mock_completion, config):
        mock_completion.side_effect = ValueError("bad value")
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="http://localhost:4000"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_unexpected_error_includes_exception_type(self, mock_completion, config):
        mock_completion.side_effect = KeyError("missing_key")
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="KeyError"):
            client.verify_connection()

    @patch("coding_agent.core.llm.litellm.completion")
    def test_unexpected_error_no_traceback_in_message(self, mock_completion, config):
        mock_completion.side_effect = RuntimeError("boom")
        client = LLMClient(config)
        with pytest.raises(ConnectionError) as exc_info:
            client.verify_connection()
        assert "Traceback" not in str(exc_info.value)


class TestVerifyConnectionApiKeySecurity:
    """NFR7: API key never appears in error messages."""

    @patch("coding_agent.core.llm.litellm.completion")
    def test_api_key_not_in_connection_error(self, mock_completion, config_with_key):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError) as exc_info:
            client.verify_connection()
        assert "sk-secret-key-12345" not in str(exc_info.value)

    @patch("coding_agent.core.llm.litellm.completion")
    def test_api_key_not_in_auth_error(self, mock_completion, config_with_key):
        mock_completion.side_effect = litellm.AuthenticationError(
            message="Invalid API key",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError) as exc_info:
            client.verify_connection()
        assert "sk-secret-key-12345" not in str(exc_info.value)

    @patch("coding_agent.core.llm.litellm.completion")
    def test_api_key_not_in_timeout_error(self, mock_completion, config_with_key):
        mock_completion.side_effect = litellm.Timeout(
            message="Request timed out",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError) as exc_info:
            client.verify_connection()
        assert "sk-secret-key-12345" not in str(exc_info.value)

    @patch("coding_agent.core.llm.litellm.completion")
    def test_api_key_not_in_server_error(self, mock_completion, config_with_key):
        mock_completion.side_effect = litellm.APIError(
            status_code=500,
            message="Internal server error",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError) as exc_info:
            client.verify_connection()
        assert "sk-secret-key-12345" not in str(exc_info.value)

    @patch("coding_agent.core.llm.litellm.completion")
    def test_api_key_not_in_unexpected_error(self, mock_completion, config_with_key):
        mock_completion.side_effect = RuntimeError("unexpected")
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError) as exc_info:
            client.verify_connection()
        assert "sk-secret-key-12345" not in str(exc_info.value)


# --- Streaming Tests (Story 2.1) ---


def _make_stream_chunks(texts):
    """Create mock streaming chunks from a list of text deltas."""
    chunks = []
    for text in texts:
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = text
        chunks.append(chunk)
    return chunks


@pytest.fixture()
def sample_messages():
    """Provide sample conversation messages for streaming tests."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
    ]


class TestSendMessageStreamSuccess:
    """AC #2: Streaming returns text deltas in real-time."""

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_yields_text_deltas_in_order(self, mock_completion, mock_builder, config, sample_messages):
        chunks = _make_stream_chunks(["Hello", " world", "!"])
        mock_completion.return_value = iter(chunks)
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        deltas = list(client.send_message_stream(sample_messages))
        assert deltas == ["Hello", " world", "!"]

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_skips_none_deltas(self, mock_completion, mock_builder, config, sample_messages):
        """Chunks with None content (e.g., role-only chunks) are skipped."""
        chunks = _make_stream_chunks([None, "Hello", None, " world"])
        mock_completion.return_value = iter(chunks)
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        deltas = list(client.send_message_stream(sample_messages))
        assert deltas == ["Hello", " world"]

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_calls_stream_chunk_builder(self, mock_completion, mock_builder, config, sample_messages):
        chunks = _make_stream_chunks(["Hi"])
        mock_completion.return_value = iter(chunks)
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        mock_builder.assert_called_once()
        # The chunks list passed to builder should contain all chunks
        assert len(mock_builder.call_args[0][0]) == 1

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_full_response_available_after_streaming(self, mock_completion, mock_builder, config, sample_messages):
        chunks = _make_stream_chunks(["Hello", " world"])
        mock_completion.return_value = iter(chunks)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello world"
        mock_builder.return_value = mock_response

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        assert client.last_response == mock_response


class TestSendMessageStreamParams:
    """Verify correct parameters are passed to litellm.completion."""

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_correct_model(self, mock_completion, mock_builder, config, sample_messages):
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "litellm/gpt-4o"

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_correct_api_base(self, mock_completion, mock_builder, config, sample_messages):
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["api_base"] == "http://localhost:4000"

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_api_key(self, mock_completion, mock_builder, config_with_key, sample_messages):
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()

        client = LLMClient(config_with_key)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["api_key"] == "sk-secret-key-12345"

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_stream_true(self, mock_completion, mock_builder, config, sample_messages):
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["stream"] is True

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_messages(self, mock_completion, mock_builder, config, sample_messages):
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["messages"] == sample_messages

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_timeout(self, mock_completion, mock_builder, config, sample_messages):
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["timeout"] == 300

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_temperature_stream(self, mock_completion, mock_builder, config, sample_messages):
        """AC: temperature is passed to LiteLLM in streaming."""
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()
        config.temperature = 0.7

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["temperature"] == 0.7

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_max_tokens_stream(self, mock_completion, mock_builder, config, sample_messages):
        """AC: max_output_tokens is passed to LiteLLM in streaming."""
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()
        config.max_output_tokens = 8192

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["max_tokens"] == 8192

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_passes_top_p_stream(self, mock_completion, mock_builder, config, sample_messages):
        """AC: top_p is passed to LiteLLM in streaming."""
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()
        config.top_p = 0.9

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["top_p"] == 0.9


class TestSendMessageStreamErrors:
    """Streaming errors produce clear ConnectionError messages."""

    @patch("coding_agent.core.llm.litellm.completion")
    def test_connection_error(self, mock_completion, config, sample_messages):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="Cannot connect"):
            list(client.send_message_stream(sample_messages))

    @patch("coding_agent.core.llm.litellm.completion")
    def test_auth_error(self, mock_completion, config_with_key, sample_messages):
        mock_completion.side_effect = litellm.AuthenticationError(
            message="Invalid API key",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError, match="Authentication failed"):
            list(client.send_message_stream(sample_messages))

    @patch("coding_agent.core.llm.litellm.completion")
    def test_timeout_error(self, mock_completion, config, sample_messages):
        mock_completion.side_effect = litellm.Timeout(
            message="Request timed out",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="timed out"):
            list(client.send_message_stream(sample_messages))

    @patch("coding_agent.core.llm.litellm.completion")
    def test_api_error(self, mock_completion, config, sample_messages):
        mock_completion.side_effect = litellm.APIError(
            status_code=500,
            message="Internal server error",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="request failed"):
            list(client.send_message_stream(sample_messages))

    @patch("coding_agent.core.llm.litellm.completion")
    def test_unexpected_error(self, mock_completion, config, sample_messages):
        mock_completion.side_effect = RuntimeError("something unexpected")
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="Unexpected error"):
            list(client.send_message_stream(sample_messages))


class TestSendMessageStreamMidStreamError:
    """Mid-stream errors (during chunk iteration) are handled gracefully."""

    @patch("coding_agent.core.llm.litellm.completion")
    def test_mid_stream_connection_error(self, mock_completion, config, sample_messages):
        """Error raised during chunk iteration (not at call time)."""
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "partial"

        def failing_iterator():
            yield chunk1
            raise litellm.APIConnectionError(
                message="Connection lost",
                model="litellm/gpt-4o",
                llm_provider="openai",
            )

        mock_completion.return_value = failing_iterator()
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="Cannot connect"):
            list(client.send_message_stream(sample_messages))

    @patch("coding_agent.core.llm.litellm.completion")
    def test_mid_stream_error_resets_last_response(self, mock_completion, config, sample_messages):
        """last_response stays None when mid-stream error occurs."""
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "partial"

        def failing_iterator():
            yield chunk1
            raise litellm.Timeout(
                message="Timed out",
                model="litellm/gpt-4o",
                llm_provider="openai",
            )

        mock_completion.return_value = failing_iterator()
        client = LLMClient(config)
        with pytest.raises(ConnectionError):
            list(client.send_message_stream(sample_messages))
        assert client.last_response is None

    @patch("coding_agent.core.llm.litellm.completion")
    def test_mid_stream_unexpected_error(self, mock_completion, config, sample_messages):
        """Unexpected exception during chunk iteration is caught."""
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "data"

        def failing_iterator():
            yield chunk1
            raise RuntimeError("stream broke")

        mock_completion.return_value = failing_iterator()
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="Unexpected error"):
            list(client.send_message_stream(sample_messages))


class TestSendMessageStreamApiKeySecurity:
    """NFR7: API key never appears in streaming error messages."""

    @patch("coding_agent.core.llm.litellm.completion")
    def test_api_key_not_in_connection_error(self, mock_completion, config_with_key, sample_messages):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError) as exc_info:
            list(client.send_message_stream(sample_messages))
        assert "sk-secret-key-12345" not in str(exc_info.value)

    @patch("coding_agent.core.llm.litellm.completion")
    def test_api_key_not_in_auth_error(self, mock_completion, config_with_key, sample_messages):
        mock_completion.side_effect = litellm.AuthenticationError(
            message="Invalid API key",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError) as exc_info:
            list(client.send_message_stream(sample_messages))
        assert "sk-secret-key-12345" not in str(exc_info.value)

    @patch("coding_agent.core.llm.litellm.completion")
    def test_api_key_not_in_timeout_error(self, mock_completion, config_with_key, sample_messages):
        mock_completion.side_effect = litellm.Timeout(
            message="Request timed out",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError) as exc_info:
            list(client.send_message_stream(sample_messages))
        assert "sk-secret-key-12345" not in str(exc_info.value)

    @patch("coding_agent.core.llm.litellm.completion")
    def test_api_key_not_in_api_error(self, mock_completion, config_with_key, sample_messages):
        mock_completion.side_effect = litellm.APIError(
            status_code=500,
            message="Internal server error",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError) as exc_info:
            list(client.send_message_stream(sample_messages))
        assert "sk-secret-key-12345" not in str(exc_info.value)

    @patch("coding_agent.core.llm.litellm.completion")
    def test_api_key_not_in_unexpected_error(self, mock_completion, config_with_key, sample_messages):
        mock_completion.side_effect = RuntimeError("unexpected")
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError) as exc_info:
            list(client.send_message_stream(sample_messages))
        assert "sk-secret-key-12345" not in str(exc_info.value)


class TestSamplingParamsUnsupported:
    """Unsupported temperature/top_p params are omitted, not sent with fallback values."""

    def test_temperature_omitted_when_unsupported(self, config):
        """temperature key must be absent when caps say unsupported."""
        client = LLMClient(config)
        client.set_capabilities(ModelCapabilities(temperature_supported=False, top_p_supported=True))
        params = client._get_sampling_params()
        assert "temperature" not in params

    def test_top_p_omitted_when_unsupported(self, config):
        """top_p key must be absent when caps say unsupported."""
        client = LLMClient(config)
        client.set_capabilities(ModelCapabilities(temperature_supported=True, top_p_supported=False))
        params = client._get_sampling_params()
        assert "top_p" not in params

    def test_both_omitted_when_both_unsupported(self, config):
        """Neither temperature nor top_p sent when both are unsupported."""
        client = LLMClient(config)
        client.set_capabilities(ModelCapabilities(temperature_supported=False, top_p_supported=False))
        params = client._get_sampling_params()
        assert "temperature" not in params
        assert "top_p" not in params

    def test_both_included_when_caps_none(self, config):
        """Both params are included when capabilities are unknown (None)."""
        client = LLMClient(config)
        assert client.get_capabilities() is None
        params = client._get_sampling_params()
        assert "temperature" in params
        assert "top_p" in params

    @patch("coding_agent.core.llm.litellm.completion")
    def test_verify_connection_detects_caps_and_omits_unsupported(self, mock_completion, config):
        """verify_connection detects capabilities; models that reject params get none sent."""
        mock_completion.side_effect = litellm.BadRequestError(
            message="temperature not supported",
            model="litellm/gpt-4o",
            llm_provider="openai",
            response=MagicMock(status_code=400),
        )
        client = LLMClient(config)
        # Both detect and ping will fail with BadRequestError → ConnectionError
        with pytest.raises(ConnectionError):
            client.verify_connection()
        # Capabilities should have been detected and set as unsupported
        caps = client.get_capabilities()
        assert caps is not None
        assert caps.temperature_supported is False
        assert caps.top_p_supported is False

    @patch("coding_agent.core.llm.litellm.completion")
    def test_stream_omits_temperature_when_unsupported(self, mock_completion, config, sample_messages):
        """send_message_stream omits temperature when model capability says unsupported."""
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        with patch("coding_agent.core.llm.litellm.stream_chunk_builder", return_value=MagicMock()):
            client = LLMClient(config)
            client.set_capabilities(ModelCapabilities(temperature_supported=False, top_p_supported=True))
            list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert "temperature" not in call_kwargs

    @patch("coding_agent.core.llm.litellm.completion")
    def test_stream_omits_top_p_when_unsupported(self, mock_completion, config, sample_messages):
        """send_message_stream omits top_p when model capability says unsupported."""
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        with patch("coding_agent.core.llm.litellm.stream_chunk_builder", return_value=MagicMock()):
            client = LLMClient(config)
            client.set_capabilities(ModelCapabilities(temperature_supported=True, top_p_supported=False))
            list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert "top_p" not in call_kwargs


class TestIsMinimaxOpenrouter:
    """Unit tests for _is_minimax_openrouter helper."""

    def test_matches_minimax_via_openrouter(self):
        assert _is_minimax_openrouter("openrouter/minimax/minimax-m2.5") is True

    def test_matches_minimax_m2_via_openrouter(self):
        assert _is_minimax_openrouter("openrouter/minimax/minimax-m2") is True

    def test_case_insensitive(self):
        assert _is_minimax_openrouter("OpenRouter/MiniMax/MiniMax-M2.5") is True

    def test_non_minimax_openrouter_model(self):
        assert _is_minimax_openrouter("openrouter/openai/gpt-4o") is False

    def test_minimax_without_openrouter(self):
        assert _is_minimax_openrouter("minimax/MiniMax-M2.5") is False

    def test_standard_openai_model(self):
        assert _is_minimax_openrouter("litellm/gpt-4o") is False

    def test_empty_string(self):
        assert _is_minimax_openrouter("") is False


class TestParseMinimaxToolCalls:
    """Unit tests for _parse_minimax_tool_calls XML parser."""

    def test_parses_single_tool_call(self):
        content = (
            "<minimax:tool_call>\n"
            '<invoke name="read_file">\n'
            '<parameter name="path">foo.py</parameter>\n'
            "</invoke>\n"
            "</minimax:tool_call>"
        )
        calls = _parse_minimax_tool_calls(content)
        assert len(calls) == 1
        assert calls[0]["name"] == "read_file"
        assert calls[0]["arguments"] == {"path": "foo.py"}
        assert calls[0]["id"].startswith("call_")

    def test_parses_multiple_parameters(self):
        content = (
            "<minimax:tool_call>\n"
            '<invoke name="run_shell">\n'
            '<parameter name="command">ls</parameter>\n'
            '<parameter name="cwd">/tmp</parameter>\n'
            "</invoke>\n"
            "</minimax:tool_call>"
        )
        calls = _parse_minimax_tool_calls(content)
        assert len(calls) == 1
        assert calls[0]["arguments"] == {"command": "ls", "cwd": "/tmp"}

    def test_parses_json_parameter_values(self):
        content = (
            "<minimax:tool_call>\n"
            '<invoke name="write_file">\n'
            '<parameter name="lines">["a", "b"]</parameter>\n'
            "</invoke>\n"
            "</minimax:tool_call>"
        )
        calls = _parse_minimax_tool_calls(content)
        assert calls[0]["arguments"]["lines"] == ["a", "b"]

    def test_parses_multiple_tool_calls(self):
        content = (
            "<minimax:tool_call>\n"
            '<invoke name="tool_a">\n'
            '<parameter name="x">1</parameter>\n'
            "</invoke>\n"
            "</minimax:tool_call>\n"
            "<minimax:tool_call>\n"
            '<invoke name="tool_b">\n'
            '<parameter name="y">2</parameter>\n'
            "</invoke>\n"
            "</minimax:tool_call>"
        )
        calls = _parse_minimax_tool_calls(content)
        assert len(calls) == 2
        assert calls[0]["name"] == "tool_a"
        assert calls[1]["name"] == "tool_b"

    def test_returns_empty_for_no_tool_calls(self):
        assert _parse_minimax_tool_calls("Just some text, no tool calls here.") == []

    def test_skips_block_without_invoke(self):
        content = "<minimax:tool_call>no invoke tag here</minimax:tool_call>"
        assert _parse_minimax_tool_calls(content) == []

    def test_unique_ids_per_call(self):
        content = (
            "<minimax:tool_call>\n"
            '<invoke name="tool_a"><parameter name="x">1</parameter></invoke>\n'
            "</minimax:tool_call>\n"
            "<minimax:tool_call>\n"
            '<invoke name="tool_b"><parameter name="y">2</parameter></invoke>\n'
            "</minimax:tool_call>"
        )
        calls = _parse_minimax_tool_calls(content)
        assert calls[0]["id"] != calls[1]["id"]


class TestMinimaxOpenRouterFallback:
    """send_message_stream falls back to XML parsing for MiniMax-via-OpenRouter."""

    def _make_minimax_config(self):
        return AgentConfig(
            model="openrouter/minimax/minimax-m2.5",
            api_base="https://openrouter.ai/api/v1",
        )

    def _make_mock_response(self, content: str):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = content
        mock_response.choices[0].message.tool_calls = None
        return mock_response

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_parses_xml_tool_call_when_tool_calls_absent(self, mock_completion, mock_builder, sample_messages):
        xml_content = (
            "<minimax:tool_call>\n"
            '<invoke name="read_file">\n'
            '<parameter name="path">foo.py</parameter>\n'
            "</invoke>\n"
            "</minimax:tool_call>"
        )
        mock_completion.return_value = iter(_make_stream_chunks([xml_content]))
        mock_builder.return_value = self._make_mock_response(xml_content)

        client = LLMClient(self._make_minimax_config())
        gen = client.send_message_stream(sample_messages)
        list(gen)
        try:
            gen.send(None)
        except StopIteration as exc:
            result = exc.value
        else:
            result = client.last_response  # won't reach; use generator return
            result = None

        # Drive the generator to get the return value
        gen2 = client.send_message_stream(sample_messages)
        mock_completion.return_value = iter(_make_stream_chunks([xml_content]))
        mock_builder.return_value = self._make_mock_response(xml_content)
        try:
            while True:
                next(gen2)
        except StopIteration as exc:
            result = exc.value

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "read_file"
        assert result.tool_calls[0]["arguments"] == {"path": "foo.py"}

    @patch("coding_agent.core.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.core.llm.litellm.completion")
    def test_xml_fallback_not_triggered_for_non_minimax(self, mock_completion, mock_builder, config, sample_messages):
        """Non-MiniMax models with empty tool_calls and XML-like content are unaffected."""
        xml_content = (
            "<minimax:tool_call>"
            '<invoke name="read_file"><parameter name="path">foo.py</parameter></invoke>'
            "</minimax:tool_call>"
        )
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = xml_content
        mock_response.choices[0].message.tool_calls = None
        mock_completion.return_value = iter(_make_stream_chunks([xml_content]))
        mock_builder.return_value = mock_response

        client = LLMClient(config)  # model = litellm/gpt-4o
        try:
            gen = client.send_message_stream(sample_messages)
            while True:
                next(gen)
        except StopIteration as exc:
            result = exc.value

        assert result.tool_calls == []
