"""Conversation management for LLM context."""

import json
from typing import Any


class ConversationManager:
    """Manages message history for LLM context."""

    def __init__(self, system_prompt: str) -> None:
        """Initialize with system prompt (never dropped)."""
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

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
        total = 0
        for m in self._messages:
            content = m.get("content") or ""
            total += len(content) // 4
        return total

    def clear(self) -> None:
        """Clear all non-system messages (called on session end)."""
        system_prompt = self._messages[0]["content"] if self._messages else ""
        self._messages = [{"role": "system", "content": system_prompt}]
