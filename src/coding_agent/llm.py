"""LiteLLM client wrapper - connectivity verification and LLM communication."""

from collections.abc import Generator

import litellm

from coding_agent.config import AgentConfig


class LLMClient:
    """LiteLLM client for model communication."""

    def __init__(self, config: AgentConfig) -> None:
        self.model = config.model
        self.api_base = config.api_base
        self.api_key = config.api_key
        self.last_response = None

    def _handle_llm_error(self, error: Exception) -> None:
        """Convert exceptions from LiteLLM calls to ConnectionError with clear messages.

        Handles known LiteLLM exception types (AuthenticationError, APIConnectionError,
        Timeout, APIError) with specific messages, and falls back to a generic message
        for unexpected exception types.

        Raises:
            ConnectionError: Always. With differentiated messages for connectivity,
                authentication, timeout, server errors, and unexpected failures.
        """
        if isinstance(error, litellm.AuthenticationError):
            raise ConnectionError(
                f"Authentication failed connecting to LiteLLM server.\n\n"
                f"  Server: {self.api_base}\n"
                f"  Error: {error.message}\n\n"
                f"Check your api_key in ~/.coding-agent/config.yaml"
            ) from None
        if isinstance(error, litellm.APIConnectionError):
            raise ConnectionError(
                f"Cannot connect to LiteLLM server.\n\n"
                f"  Server: {self.api_base}\n"
                f"  Error: {error.message}\n\n"
                f"Suggestions:\n"
                f"  1. Verify the server is running at {self.api_base}\n"
                f"  2. Check your network/firewall settings\n"
                f"  3. Verify api_base in ~/.coding-agent/config.yaml"
            ) from None
        if isinstance(error, litellm.Timeout):
            raise ConnectionError(
                f"Connection to LiteLLM server timed out.\n\n"
                f"  Server: {self.api_base}\n\n"
                f"The server may be overloaded or unreachable. "
                f"Check your network connection."
            ) from None
        if isinstance(error, litellm.APIError):
            raise ConnectionError(
                f"LiteLLM request failed (status {error.status_code}).\n\n"
                f"  Server: {self.api_base}\n"
                f"  Error: {error.message}\n\n"
                f"Check your LiteLLM server configuration and logs."
            ) from None
        raise ConnectionError(
            f"Unexpected error connecting to LiteLLM server.\n\n"
            f"  Server: {self.api_base}\n"
            f"  Error: {type(error).__name__}: {error}"
        ) from None

    def verify_connection(self) -> None:
        """Verify connectivity to LiteLLM server.

        Sends a lightweight test request to confirm the server is reachable
        and authentication is valid.

        Raises:
            ConnectionError: With differentiated messages for connectivity,
                authentication, timeout, and server errors.
        """
        try:
            litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                api_base=self.api_base,
                api_key=self.api_key,
                max_tokens=1,
                timeout=10,
            )
        except Exception as e:
            self._handle_llm_error(e)

    def send_message_stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """Stream a completion response, yielding text deltas.

        Yields text content as it arrives. After the generator is exhausted,
        the full reassembled ModelResponse is available via self.last_response.

        Raises:
            ConnectionError: With differentiated messages for connectivity,
                authentication, timeout, and server errors.
        """
        self.last_response = None
        chunks = []
        try:
            response_stream = litellm.completion(
                model=self.model,
                messages=messages,
                api_base=self.api_base,
                api_key=self.api_key,
                stream=True,
                timeout=300,
            )
            for chunk in response_stream:
                chunks.append(chunk)
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
            self.last_response = litellm.stream_chunk_builder(chunks)
        except Exception as e:
            self._handle_llm_error(e)
