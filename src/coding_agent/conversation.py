"""Conversation management for LLM context."""

import json
import logging
from typing import Any

import litellm

_log = logging.getLogger(__name__)

_MAX_TOOL_OUTPUT_CHARS = 1000
_MAX_TOOL_RESULT_PREVIEW = 300
_TOOL_CALL_TOKEN_OVERHEAD = 50


class ConversationManager:
    """Manages message history for LLM context."""

    def __init__(self, system_prompt: str, model: str = "gpt-4") -> None:
        """Initialize with system prompt (never dropped).

        Args:
            system_prompt: The system prompt to use
            model: The model to use for token counting (default: gpt-4)
        """
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        self._model = model
        self._token_cache: int | None = None

    def _invalidate_cache(self) -> None:
        """Invalidate the token count cache."""
        self._token_cache = None

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the conversation history.

        Args:
            role: One of "user", "assistant", "tool"
            content: The message content
            **kwargs: Additional fields (e.g. tool_calls, tool_call_id)
        """
        message: dict[str, Any] = {"role": role, "content": content}
        message.update(kwargs)
        self._messages.append(message)
        self._invalidate_cache()

    def add_assistant_tool_call(self, content: str, tool_calls: list[dict]) -> None:
        """Add an assistant message that includes native tool_calls.

        Args:
            content: Text content from the assistant (may be empty)
            tool_calls: List of tool call dicts with id, name, arguments
        """
        message: dict[str, Any] = {
            "role": "assistant",
            "content": content or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"] if isinstance(tc["arguments"], str)
                        else json.dumps(tc["arguments"]),
                    },
                }
                for tc in tool_calls
            ],
        }
        self._messages.append(message)
        self._invalidate_cache()

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """Add a tool result message.

        Args:
            tool_call_id: The ID of the tool call this is responding to
            content: The tool execution result
        """
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })
        self._invalidate_cache()

    def get_messages(self) -> list[dict[str, Any]]:
        """Return all messages for LLM API."""
        return self._messages.copy()

    def get_messages_simplified(self) -> list[dict[str, Any]]:
        """Return messages with tool call/result pairs flattened to plain text.

        Converts assistant messages with tool_calls and role=tool messages into
        plain assistant text, for use with models that don't support tool calling.
        """
        simplified: list[dict[str, Any]] = []
        i = 0
        while i < len(self._messages):
            msg = self._messages[i]
            role = msg.get("role")
            if role == "assistant" and msg.get("tool_calls"):
                parts = [msg.get("content") or ""]
                for tc in msg.get("tool_calls", []):
                    fn = tc.get("function", {})
                    parts.append(f"[Tool: {fn.get('name', '?')}({fn.get('arguments', '')})]")
                # Absorb following tool result messages
                while i + 1 < len(self._messages) and self._messages[i + 1].get("role") == "tool":
                    i += 1
                    tool_content = self._messages[i].get("content", "")
                    if tool_content:
                        parts.append(f"[Result: {tool_content[:_MAX_TOOL_RESULT_PREVIEW]}]")
                simplified.append({
                    "role": "assistant",
                    "content": "\n".join(p for p in parts if p) or "[Tool call]",
                })
            elif role == "tool":
                pass  # Orphaned tool result — skip
            else:
                simplified.append({k: v for k, v in msg.items()})
            i += 1
        return simplified

    def truncate_if_needed(self, max_tokens: int = 128000) -> None:
        """Truncate conversation history to prevent context overflow.

        Strategy:
        1. First: Prune old tool outputs (reduce content length)
        2. Then: Remove oldest user/assistant message pairs
        3. Never: Remove system prompt

        Args:
            max_tokens: Maximum estimated tokens before truncation (default: 128K)
        """
        prev_estimate = -1
        while True:
            estimate = self._estimate_tokens()
            if estimate <= max_tokens or estimate == prev_estimate:
                break
            prev_estimate = estimate
            # Step 1: Try to prune tool outputs first
            if self._prune_oldest_tool_output():
                continue
            # Step 2: Remove oldest message pair (user + assistant + their tool results)
            if not self._remove_oldest_message_pair():
                break  # Nothing more to remove

    def _prune_oldest_tool_output(self) -> bool:
        """Prune the oldest tool output content to reduce tokens.

        Returns:
            True if a tool output was pruned, False if none found.
        """
        for i, msg in enumerate(self._messages):
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if content and len(content) > _MAX_TOOL_OUTPUT_CHARS:
                    msg["content"] = content[:_MAX_TOOL_OUTPUT_CHARS] + "\n...[truncated]"
                    return True
        return False

    def _remove_oldest_message_pair(self) -> bool:
        """Remove the oldest user/assistant message pair and associated tool results.

        Returns:
            True if a pair was removed, False if nothing to remove.
        """
        non_system = [i for i, m in enumerate(self._messages) if m["role"] != "system"]
        if not non_system:
            return False

        oldest_idx = non_system[0]
        remove_indices: set[int] = {oldest_idx}

        # If oldest is assistant, also remove following tool results
        if self._messages[oldest_idx].get("role") == "assistant":
            for i in range(oldest_idx + 1, len(self._messages)):
                if self._messages[i].get("role") == "tool":
                    remove_indices.add(i)
                else:
                    break

        # Remove in reverse order to maintain indices
        for idx in sorted(remove_indices, reverse=True):
            del self._messages[idx]

        return True

    def _estimate_tokens(self) -> int:
        """Estimate total tokens using litellm.token_counter() with fallback.

        Returns:
            Estimated token count
        """
        try:
            # Try to use litellm's token counter for accuracy
            return litellm.token_counter(model=self._model, messages=self._messages)
        except Exception:
            # Fallback to character heuristic if litellm unavailable
            return self._estimate_tokens_heuristic()

    def _estimate_tokens_heuristic(self) -> int:
        """Estimate tokens using character heuristic (len/4).

        Returns:
            Estimated token count
        """
        total = 0
        for m in self._messages:
            content = m.get("content") or ""
            total += len(content) // 4
            # Add overhead for tool_calls
            if m.get("tool_calls"):
                total += _TOOL_CALL_TOKEN_OVERHEAD
        return total

    def clear(self) -> None:
        """Clear all non-system messages (called on session end)."""
        system_prompt = self._messages[0]["content"] if self._messages else ""
        self._messages = [{"role": "system", "content": system_prompt}]
        self._invalidate_cache()

    @property
    def token_count(self) -> int:
        """Return current estimated token count (cached between mutations)."""
        if self._token_cache is None:
            self._token_cache = self._estimate_tokens()
        return self._token_cache
