"""Tests for LLM client connectivity verification and streaming."""

from unittest.mock import MagicMock, patch

import litellm
import pytest

from coding_agent.config import AgentConfig
from coding_agent.llm import LLMClient


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

    @patch("coding_agent.llm.litellm.completion")
    def test_returns_without_error(self, mock_completion, config):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config)
        client.verify_connection()  # Should not raise

    @patch("coding_agent.llm.litellm.completion")
    def test_passes_correct_model(self, mock_completion, config):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "litellm/gpt-4o"

    @patch("coding_agent.llm.litellm.completion")
    def test_passes_correct_api_base(self, mock_completion, config):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["api_base"] == "http://localhost:4000"

    @patch("coding_agent.llm.litellm.completion")
    def test_passes_api_key(self, mock_completion, config_with_key):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config_with_key)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["api_key"] == "sk-secret-key-12345"

    @patch("coding_agent.llm.litellm.completion")
    def test_passes_none_api_key(self, mock_completion, config):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["api_key"] is None

    @patch("coding_agent.llm.litellm.completion")
    def test_uses_max_tokens_1(self, mock_completion, config):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["max_tokens"] == 1

    @patch("coding_agent.llm.litellm.completion")
    def test_uses_short_timeout(self, mock_completion, config):
        mock_completion.return_value = MagicMock()
        client = LLMClient(config)
        client.verify_connection()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["timeout"] == 10


class TestVerifyConnectionUnreachable:
    """AC #2: Unreachable server produces clear error with URL and suggestions."""

    @patch("coding_agent.llm.litellm.completion")
    def test_raises_connection_error(self, mock_completion, config):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError):
            client.verify_connection()

    @patch("coding_agent.llm.litellm.completion")
    def test_error_contains_server_url(self, mock_completion, config):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="http://localhost:4000"):
            client.verify_connection()

    @patch("coding_agent.llm.litellm.completion")
    def test_error_contains_cannot_connect(self, mock_completion, config):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="Cannot connect"):
            client.verify_connection()

    @patch("coding_agent.llm.litellm.completion")
    def test_error_contains_suggestions(self, mock_completion, config):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="Verify the server is running"):
            client.verify_connection()


class TestVerifyConnectionAuthError:
    """AC #3: Auth error is distinguishable from connectivity failure."""

    @patch("coding_agent.llm.litellm.completion")
    def test_raises_connection_error(self, mock_completion, config_with_key):
        mock_completion.side_effect = litellm.AuthenticationError(
            message="Invalid API key",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError):
            client.verify_connection()

    @patch("coding_agent.llm.litellm.completion")
    def test_error_contains_authentication_failed(self, mock_completion, config_with_key):
        mock_completion.side_effect = litellm.AuthenticationError(
            message="Invalid API key",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError, match="Authentication failed"):
            client.verify_connection()

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
    def test_raises_connection_error(self, mock_completion, config):
        mock_completion.side_effect = litellm.Timeout(
            message="Request timed out",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="timed out"):
            client.verify_connection()

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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


class TestVerifyConnectionUnexpectedException:
    """Unexpected exceptions are caught gracefully."""

    @patch("coding_agent.llm.litellm.completion")
    def test_unexpected_error_raises_connection_error(self, mock_completion, config):
        mock_completion.side_effect = RuntimeError("something completely unexpected")
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="Unexpected error"):
            client.verify_connection()

    @patch("coding_agent.llm.litellm.completion")
    def test_unexpected_error_contains_server_url(self, mock_completion, config):
        mock_completion.side_effect = ValueError("bad value")
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="http://localhost:4000"):
            client.verify_connection()

    @patch("coding_agent.llm.litellm.completion")
    def test_unexpected_error_includes_exception_type(self, mock_completion, config):
        mock_completion.side_effect = KeyError("missing_key")
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="KeyError"):
            client.verify_connection()


class TestVerifyConnectionApiKeySecurity:
    """NFR7: API key never appears in error messages."""

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.llm.litellm.completion")
    def test_yields_text_deltas_in_order(self, mock_completion, mock_builder, config, sample_messages):
        chunks = _make_stream_chunks(["Hello", " world", "!"])
        mock_completion.return_value = iter(chunks)
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        deltas = list(client.send_message_stream(sample_messages))
        assert deltas == ["Hello", " world", "!"]

    @patch("coding_agent.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.llm.litellm.completion")
    def test_skips_none_deltas(self, mock_completion, mock_builder, config, sample_messages):
        """Chunks with None content (e.g., role-only chunks) are skipped."""
        chunks = _make_stream_chunks([None, "Hello", None, " world"])
        mock_completion.return_value = iter(chunks)
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        deltas = list(client.send_message_stream(sample_messages))
        assert deltas == ["Hello", " world"]

    @patch("coding_agent.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.llm.litellm.completion")
    def test_calls_stream_chunk_builder(self, mock_completion, mock_builder, config, sample_messages):
        chunks = _make_stream_chunks(["Hi"])
        mock_completion.return_value = iter(chunks)
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        mock_builder.assert_called_once()
        # The chunks list passed to builder should contain all chunks
        assert len(mock_builder.call_args[0][0]) == 1

    @patch("coding_agent.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.llm.litellm.completion")
    def test_passes_correct_model(self, mock_completion, mock_builder, config, sample_messages):
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "litellm/gpt-4o"

    @patch("coding_agent.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.llm.litellm.completion")
    def test_passes_correct_api_base(self, mock_completion, mock_builder, config, sample_messages):
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["api_base"] == "http://localhost:4000"

    @patch("coding_agent.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.llm.litellm.completion")
    def test_passes_api_key(self, mock_completion, mock_builder, config_with_key, sample_messages):
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()

        client = LLMClient(config_with_key)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["api_key"] == "sk-secret-key-12345"

    @patch("coding_agent.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.llm.litellm.completion")
    def test_passes_stream_true(self, mock_completion, mock_builder, config, sample_messages):
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["stream"] is True

    @patch("coding_agent.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.llm.litellm.completion")
    def test_passes_messages(self, mock_completion, mock_builder, config, sample_messages):
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["messages"] == sample_messages

    @patch("coding_agent.llm.litellm.stream_chunk_builder")
    @patch("coding_agent.llm.litellm.completion")
    def test_passes_timeout(self, mock_completion, mock_builder, config, sample_messages):
        mock_completion.return_value = iter(_make_stream_chunks(["ok"]))
        mock_builder.return_value = MagicMock()

        client = LLMClient(config)
        list(client.send_message_stream(sample_messages))
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["timeout"] == 300


class TestSendMessageStreamErrors:
    """Streaming errors produce clear ConnectionError messages."""

    @patch("coding_agent.llm.litellm.completion")
    def test_connection_error(self, mock_completion, config, sample_messages):
        mock_completion.side_effect = litellm.APIConnectionError(
            message="Connection refused",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="Cannot connect"):
            list(client.send_message_stream(sample_messages))

    @patch("coding_agent.llm.litellm.completion")
    def test_auth_error(self, mock_completion, config_with_key, sample_messages):
        mock_completion.side_effect = litellm.AuthenticationError(
            message="Invalid API key",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError, match="Authentication failed"):
            list(client.send_message_stream(sample_messages))

    @patch("coding_agent.llm.litellm.completion")
    def test_timeout_error(self, mock_completion, config, sample_messages):
        mock_completion.side_effect = litellm.Timeout(
            message="Request timed out",
            model="litellm/gpt-4o",
            llm_provider="openai",
        )
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="timed out"):
            list(client.send_message_stream(sample_messages))

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
    def test_unexpected_error(self, mock_completion, config, sample_messages):
        mock_completion.side_effect = RuntimeError("something unexpected")
        client = LLMClient(config)
        with pytest.raises(ConnectionError, match="Unexpected error"):
            list(client.send_message_stream(sample_messages))


class TestSendMessageStreamMidStreamError:
    """Mid-stream errors (during chunk iteration) are handled gracefully."""

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
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

    @patch("coding_agent.llm.litellm.completion")
    def test_api_key_not_in_unexpected_error(self, mock_completion, config_with_key, sample_messages):
        mock_completion.side_effect = RuntimeError("unexpected")
        client = LLMClient(config_with_key)
        with pytest.raises(ConnectionError) as exc_info:
            list(client.send_message_stream(sample_messages))
        assert "sk-secret-key-12345" not in str(exc_info.value)
