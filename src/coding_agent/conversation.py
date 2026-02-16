"""Conversation management for LLM context."""

from typing import Any


class ConversationManager:
    """Manages message history for LLM context."""

    def __init__(self, system_prompt: str) -> None:
        """Initialize with system prompt (never dropped)."""
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history.

        Args:
            role: One of "user", "assistant", "tool"
            content: The message content
        """
        self._messages.append({"role": role, "content": content})

    def get_messages(self) -> list[dict[str, Any]]:
        """Return all messages for LLM API."""
        return self._messages.copy()

    def truncate_if_needed(self, max_tokens: int = 128000) -> None:
        """Drop oldest user/assistant pairs if estimated tokens exceed limit.

        Args:
            max_tokens: Maximum estimated tokens before truncation (default: 128K)
        """
        while self._estimate_tokens() > max_tokens:
            non_system = [i for i, m in enumerate(self._messages) if m["role"] != "system"]
            if not non_system:
                break
            oldest_idx = non_system[0]

            if self._messages[oldest_idx]["role"] == "assistant":
                remove_indices: set[int] = {oldest_idx}
                for i in range(oldest_idx + 1, len(self._messages)):
                    if self._messages[i]["role"] == "tool":
                        remove_indices.add(i)
                    else:
                        break
                for idx in sorted(remove_indices, reverse=True):
                    del self._messages[idx]
            else:
                del self._messages[oldest_idx]

    def _estimate_tokens(self) -> int:
        """Estimate total tokens using character heuristic (len/4)."""
        return sum(len(m["content"]) // 4 for m in self._messages)

    def clear(self) -> None:
        """Clear all non-system messages (called on session end)."""
        system_prompt = self._messages[0]["content"] if self._messages else ""
        self._messages = [{"role": "system", "content": system_prompt}]
