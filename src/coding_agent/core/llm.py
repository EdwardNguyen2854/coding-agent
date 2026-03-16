"""LiteLLM client wrapper - connectivity verification and LLM communication."""

import json
import logging
import re
import uuid
from collections.abc import Generator
from dataclasses import dataclass, field

import litellm

_log = logging.getLogger(__name__)


def _is_minimax_openrouter(model: str) -> bool:
    """True when MiniMax is accessed via OpenRouter (which does not normalize tool-call format)."""
    m = model.lower()
    return "openrouter" in m and "minimax" in m


def _is_minimax(model: str) -> bool:
    """True for any MiniMax model (OpenRouter or otherwise)."""
    return "minimax" in model.lower()


def _parse_minimax_json_tool_calls(content: str) -> list[dict]:
    """Parse MiniMax JSON tool-call format from message content.

    MiniMax (via Ollama or similar) returns tool calls as JSON objects in content:
        {"name": "fn_name", "arguments": {...}}
    or as a JSON array:
        [{"name": "fn_name", "arguments": {...}}, ...]
    or as multiple space/newline-separated JSON objects:
        {"name": "fn1", ...} {"name": "fn2", ...}
    """
    tool_calls = []
    content = content.strip()

    def _append(item: dict) -> None:
        if isinstance(item, dict) and "name" in item:
            tool_calls.append({
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": item["name"],
                "arguments": item.get("arguments", {}),
            })

    # Try parsing as a single value (object or array) first
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            _append(parsed)
        elif isinstance(parsed, list):
            for item in parsed:
                _append(item)
        return tool_calls
    except json.JSONDecodeError:
        pass

    # Fall back to scanning for JSON objects anywhere in the content
    # (MiniMax sometimes prefixes tool calls with explanatory text)
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(content):
        # Advance to the next '{' or '['
        next_brace = content.find("{", idx)
        next_bracket = content.find("[", idx)
        candidates = [p for p in (next_brace, next_bracket) if p != -1]
        if not candidates:
            break
        idx = min(candidates)
        try:
            obj, end_idx = decoder.raw_decode(content, idx)
            if isinstance(obj, dict):
                _append(obj)
            elif isinstance(obj, list):
                for item in obj:
                    _append(item)
            idx = end_idx
        except json.JSONDecodeError:
            idx += 1

    return tool_calls


def _parse_minimax_tool_call_tag(content: str) -> list[dict]:
    """Parse MiniMax [TOOL_CALL] tag format.

    MiniMax (cloud) sometimes returns tool calls as:
        [TOOL_CALL] {tool => "fn_name", args => { --key1 "val1" --key2 "val2" }} [/TOOL_CALL]
    """
    tool_calls = []
    blocks = re.findall(r"\[TOOL_CALL\](.*?)\[/TOOL_CALL\]", content, re.DOTALL)
    for block in blocks:
        name_m = re.search(r'tool\s*=>\s*"([^"]+)"', block)
        if not name_m:
            continue
        name = name_m.group(1)
        params: dict = {}
        for pm in re.finditer(r'--(\w+)\s+"((?:[^"\\]|\\.)*)"', block, re.DOTALL):
            key = pm.group(1)
            raw_val = pm.group(2)
            try:
                params[key] = json.loads(f'"{raw_val}"')
            except json.JSONDecodeError:
                params[key] = raw_val
        tool_calls.append({
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "name": name,
            "arguments": params,
        })
    return tool_calls


def _parse_minimax_tool_calls(content: str) -> list[dict]:
    """Parse MiniMax XML tool-call format from message content.

    MiniMax returns tool calls as XML when accessed via OpenRouter:
        <minimax:tool_call>
        <invoke name="fn_name">
        <parameter name="key">value</parameter>
        </invoke>
        </minimax:tool_call>
    """
    tool_calls = []
    blocks = re.findall(r"<minimax:tool_call>(.*?)</minimax:tool_call>", content, re.DOTALL)
    for block in blocks:
        name_m = re.search(r'<invoke name="([^"]+)"', block)
        if not name_m:
            continue
        name = name_m.group(1)
        params: dict = {}
        for pm in re.finditer(r'<parameter name="([^"]+)">(.*?)</parameter>', block, re.DOTALL):
            val = pm.group(2).strip()
            try:
                params[pm.group(1)] = json.loads(val)
            except json.JSONDecodeError:
                params[pm.group(1)] = val
        tool_calls.append({
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "name": name,
            "arguments": params,
        })
    return tool_calls


class ModelRejectionError(ConnectionError):
    """Raised when the model rejects the request, e.g. due to unsupported tool format."""

from coding_agent.config.config import AgentConfig, ModelCapabilities, get_model_capabilities, is_ollama_model, set_model_capabilities
from coding_agent.tools import get_openai_tools


@dataclass
class StreamToken:
    """A single streamed token, tagged by type."""

    text: str
    is_thinking: bool = False


def _is_claude_model(model: str) -> bool:
    """True when the model is a Claude/Anthropic model that supports extended thinking."""
    m = model.lower()
    return "claude" in m or "anthropic" in m


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
        self.thinking_budget_tokens = config.thinking_budget_tokens
        self.last_response = None
        self.last_llm_response: LLMResponse | None = None
        self._capabilities: ModelCapabilities | None = None

    def set_capabilities(self, caps: ModelCapabilities) -> None:
        """Set the model capabilities."""
        self._capabilities = caps

    def get_capabilities(self) -> ModelCapabilities | None:
        """Get the model capabilities."""
        return self._capabilities

    def _get_sampling_params(self) -> dict:
        """Get sampling parameters based on model capabilities.

        Omits parameters entirely when the model doesn't support them —
        sending any value (even a neutral default) causes a BadRequestError
        on models that reject these parameters.
        """
        params = {}
        caps = self._capabilities
        if caps is None or caps.temperature_supported:
            params["temperature"] = self.temperature
        if caps is None or caps.top_p_supported:
            params["top_p"] = self.top_p
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
            raise ModelRejectionError(
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

        Detects model capabilities first so that unsupported parameters
        (temperature, top_p) are not sent to models that reject them.
        Then sends a lightweight test request to confirm the server is
        reachable and authentication is valid.

        Raises:
            ConnectionError: With differentiated messages for connectivity,
                authentication, timeout, and server errors.
        """
        caps = detect_model_capabilities(self)
        self.set_capabilities(caps)

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

    def send_message_stream(self, messages: list[dict], tools: list[dict] | None = None) -> Generator[StreamToken, None, LLMResponse]:
        """Stream a completion response, yielding StreamToken objects.

        Yields StreamToken instances tagged as either regular content or thinking
        (for models that support extended reasoning such as Claude). After the
        generator is exhausted, the return value (accessible via
        StopIteration.value) is an LLMResponse containing the full text and any
        tool_calls.

        The full reassembled ModelResponse is also available via self.last_response.

        Raises:
            ConnectionError: With differentiated messages for connectivity,
                authentication, timeout, and server errors.
        """
        self.last_response = None
        chunks = []
        sampling_params = self._get_sampling_params()

        extra_params: dict = {}
        if self.thinking_budget_tokens and _is_claude_model(self.model or ""):
            extra_params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget_tokens,
            }

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
                **extra_params,
            )
            for chunk in response_stream:
                chunks.append(chunk)
                delta = chunk.choices[0].delta

                # Extended thinking blocks (Claude)
                thinking_blocks = getattr(delta, "thinking_blocks", None)
                if thinking_blocks:
                    for block in thinking_blocks:
                        if isinstance(block, dict):
                            text = block.get("thinking", "")
                        else:
                            text = getattr(block, "thinking", "")
                        if text:
                            yield StreamToken(text=text, is_thinking=True)

                if delta.content:
                    yield StreamToken(text=delta.content)
            self.last_response = litellm.stream_chunk_builder(chunks)
        except Exception as e:
            self._handle_llm_error(e)

        # Build response from assembled result
        self.last_llm_response = None
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
            elif _is_minimax(self.model or "") and message.content:
                # Try parsers in order: [TOOL_CALL] tag, JSON (Ollama), XML (OpenRouter)
                parsed = _parse_minimax_tool_call_tag(message.content)
                if not parsed:
                    parsed = _parse_minimax_json_tool_calls(message.content)
                if not parsed and _is_minimax_openrouter(self.model or ""):
                    parsed = _parse_minimax_tool_calls(message.content)
                result.tool_calls.extend(parsed)
        self.last_llm_response = result
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
    except Exception as e:
        _log.debug("Unexpected error detecting model capabilities for %r, assuming unsupported: %s", model, e)
        caps = ModelCapabilities(temperature_supported=False, top_p_supported=False)

    set_model_capabilities(model, caps)
    return caps
