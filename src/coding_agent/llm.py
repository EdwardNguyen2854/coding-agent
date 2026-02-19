"""LiteLLM client wrapper - connectivity verification and LLM communication."""

import json
import traceback
from collections.abc import Generator
from dataclasses import dataclass, field

import litellm

from coding_agent.config import AgentConfig
from coding_agent.tools import get_openai_tools


@dataclass
class LLMResponse:
    """Assembled response from streaming LLM completion."""

    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)


class LLMClient:
    """LiteLLM client for model communication."""

    def __init__(self, config: AgentConfig) -> None:
        self.model = config.model
        self.api_base = config.api_base
        self.api_key = config.api_key
        self.temperature = config.temperature
        self.max_output_tokens = config.max_output_tokens
        self.top_p = config.top_p
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
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        raise ConnectionError(
            f"Unexpected error connecting to LiteLLM server.\n\n"
            f"  Server: {self.api_base}\n"
            f"  Error: {type(error).__name__}: {error}\n\n"
            f"Full traceback:\n{''.join(tb)}"
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
                temperature=self.temperature,
                top_p=self.top_p,
            )
        except Exception as e:
            self._handle_llm_error(e)

    def send_message_stream(self, messages: list[dict]) -> Generator[str, None, LLMResponse]:
        """Stream a completion response, yielding text deltas.

        Yields text content as it arrives. After the generator is exhausted,
        the return value (accessible via StopIteration.value) is an LLMResponse
        containing the full text and any tool_calls.

        The full reassembled ModelResponse is also available via self.last_response.

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
                tools=get_openai_tools(),
                temperature=self.temperature,
                max_tokens=self.max_output_tokens,
                top_p=self.top_p,
            )
            for chunk in response_stream:
                chunks.append(chunk)
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
            self.last_response = litellm.stream_chunk_builder(chunks)
        except Exception as e:
            self._handle_llm_error(e)

        # Build response from assembled result
        result = LLMResponse()
        if self.last_response:
            message = self.last_response.choices[0].message
            result.content = message.content or ""
            if message.tool_calls:
                for tc in message.tool_calls:
                    arguments = tc.function.arguments
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            arguments = {}
                    result.tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": arguments,
                    })
        return result
