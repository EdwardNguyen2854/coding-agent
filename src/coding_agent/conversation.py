"""Conversation management for LLM context."""

import json
from typing import Any

import litellm


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

    def get_messages(self) -> list[dict[str, Any]]:
        """Return all messages for LLM API."""
        return self._messages.copy()

    def truncate_if_needed(self, max_tokens: int = 128000) -> None:
        """Truncate conversation history to prevent context overflow.

        Strategy:
        1. First: Prune old tool outputs (reduce content length)
        2. Then: Remove oldest user/assistant message pairs
        3. Never: Remove system prompt

        Args:
            max_tokens: Maximum estimated tokens before truncation (default: 128K)
        """
        while self._estimate_tokens() > max_tokens:
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
                if content and len(content) > 1000:
                    # Truncate tool output to 1000 chars
                    msg["content"] = content[:1000] + "\n...[truncated]"
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
                total += 50  # Approximate overhead per tool call
        return total

    def clear(self) -> None:
        """Clear all non-system messages (called on session end)."""
        system_prompt = self._messages[0]["content"] if self._messages else ""
        self._messages = [{"role": "system", "content": system_prompt}]

    @property
    def token_count(self) -> int:
        """Return current estimated token count."""
        return self._estimate_tokens()
