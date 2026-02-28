"""LiteLLM client wrapper - connectivity verification and LLM communication."""

import json
from collections.abc import Generator
from dataclasses import dataclass, field

import litellm

from coding_agent.config.config import AgentConfig, ModelCapabilities, get_model_capabilities, is_ollama_model, set_model_capabilities
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
        self._capabilities: ModelCapabilities | None = None

    def set_capabilities(self, caps: ModelCapabilities) -> None:
        """Set the model capabilities."""
        self._capabilities = caps

    def get_capabilities(self) -> ModelCapabilities | None:
        """Get the model capabilities."""
        return self._capabilities

    def _get_sampling_params(self) -> dict:
        """Get sampling parameters based on model capabilities."""
        params = {}
        caps = self._capabilities
        if caps is None or caps.temperature_supported:
            params["temperature"] = self.temperature
        else:
            params["temperature"] = 0.0
        if caps is None or caps.top_p_supported:
            params["top_p"] = self.top_p
        else:
            params["top_p"] = 1.0
        return params

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
            if is_ollama_model(self.model):
                model_name = self.model.split("/", 1)[-1]
                raise ConnectionError(
                    f"Cannot connect to Ollama.\n\n"
                    f"  Server: {self.api_base}\n\n"
                    f"Suggestions:\n"
                    f"  1. Start Ollama:     ollama serve\n"
                    f"  2. Pull the model:   ollama pull {model_name}\n"
                    f"  3. Verify api_base in ~/.coding-agent/config.yaml"
                ) from None
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
        if isinstance(error, litellm.BadRequestError):
            raise ConnectionError(
                f"Model rejected the request.\n\n"
                f"  Server: {self.api_base}\n"
                f"  Error: {error}\n\n"
                f"The model may not support tool calls or this message format.\n"
                f"Try switching models with /model <name>."
            ) from None
        raise ConnectionError(
            f"Unexpected error from LiteLLM.\n\n"
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
            params = self._get_sampling_params()
            litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                api_base=self.api_base,
                api_key=self.api_key,
                max_tokens=1,
                timeout=10,
                **params,
            )
        except Exception as e:
            self._handle_llm_error(e)

    def send_message_stream(self, messages: list[dict], tools: list[dict] | None = None) -> Generator[str, None, LLMResponse]:
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
        sampling_params = self._get_sampling_params()
        try:
            response_stream = litellm.completion(
                model=self.model,
                messages=messages,
                api_base=self.api_base,
                api_key=self.api_key,
                stream=True,
                timeout=300,
                tools=tools,
                max_tokens=self.max_output_tokens,
                **sampling_params,
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


def detect_model_capabilities(client: "LLMClient") -> ModelCapabilities:
    """Detect if a model supports temperature and top_p parameters.

    Makes a minimal request with temperature=0.5, top_p=0.9 to test support.

    Args:
        client: LLMClient instance to test

    Returns:
        ModelCapabilities indicating which parameters are supported
    """
    model = client.model

    cached = get_model_capabilities(model)
    if cached:
        return cached

    try:
        litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            api_base=client.api_base,
            api_key=client.api_key,
            max_tokens=1,
            temperature=0.5,
            top_p=0.9,
            timeout=10,
        )
        caps = ModelCapabilities(temperature_supported=True, top_p_supported=True)
    except litellm.BadRequestError:
        caps = ModelCapabilities(temperature_supported=False, top_p_supported=False)
    except Exception:
        caps = ModelCapabilities(temperature_supported=False, top_p_supported=False)

    set_model_capabilities(model, caps)
    return caps
