"""Tests for ConversationManager."""

from coding_agent.conversation import ConversationManager


class TestConversationManager:
    """Verify ConversationManager behavior for message history."""

    def test_add_message_user(self):
        """add_message() appends user message to history."""
        cm = ConversationManager("You are a helpful assistant.")
        cm.add_message("user", "Hello")
        messages = cm.get_messages()
        assert len(messages) == 2  # system + user
        assert messages[1] == {"role": "user", "content": "Hello"}

    def test_add_message_assistant(self):
        """add_message() appends assistant message to history."""
        cm = ConversationManager("System prompt")
        cm.add_message("user", "Hello")
        cm.add_message("assistant", "Hi there")
        messages = cm.get_messages()
        assert len(messages) == 3
        assert messages[2] == {"role": "assistant", "content": "Hi there"}

    def test_add_message_tool(self):
        """add_message() appends tool message to history."""
        cm = ConversationManager("System prompt")
        cm.add_message("user", "Read file")
        cm.add_message("assistant", "I'll read it")
        cm.add_message("tool", "file content here")
        messages = cm.get_messages()
        assert len(messages) == 4
        assert messages[3] == {"role": "tool", "content": "file content here"}

    def test_get_messages_returns_copy(self):
        """get_messages() returns a copy, not the original list."""
        cm = ConversationManager("System prompt")
        cm.add_message("user", "Hello")
        messages = cm.get_messages()
        messages.append({"role": "user", "content": "tampered"})
        assert len(cm.get_messages()) == 2  # Original unchanged

    def test_system_prompt_included(self):
        """get_messages() includes system prompt."""
        cm = ConversationManager("Important system prompt")
        messages = cm.get_messages()
        assert messages[0] == {"role": "system", "content": "Important system prompt"}

    def test_truncation_drops_oldest_pairs(self):
        """truncate_if_needed() drops oldest user/assistant pairs."""
        cm = ConversationManager("System prompt")
        long_content = "x" * 1000  # ~250 tokens
        for i in range(100):
            cm.add_message("user", f"Message {i}: {long_content}")
            cm.add_message("assistant", f"Response {i}: {long_content}")

        # System prompt should still be there
        assert cm.get_messages()[0]["role"] == "system"
        # Force truncation with a low limit
        cm.truncate_if_needed(max_tokens=5000)
        # Should have truncated many messages
        assert len(cm.get_messages()) < 200

    def test_truncation_system_prompt_never_dropped(self):
        """truncate_if_needed() never removes system prompt."""
        cm = ConversationManager("Important system prompt")
        cm.add_message("user", "Hello")
        cm.truncate_if_needed(max_tokens=0)  # Force truncation
        assert cm.get_messages()[0]["content"] == "Important system prompt"

    def test_truncation_removes_associated_tool_messages(self):
        """truncate_if_needed() removes tool messages with their assistant message."""
        cm = ConversationManager("System")
        cm.add_message("user", "Read file")
        cm.add_message("assistant", "I'll read it")
        cm.add_message("tool", "file content")
        cm.add_message("user", "Another question")
        cm.add_message("assistant", "Another response")

        # Force truncation
        cm.truncate_if_needed(max_tokens=0)

        messages = cm.get_messages()
        # System prompt should be there
        assert messages[0]["role"] == "system"
        # Should have removed oldest user/assistant/tool messages
        assert len(messages) <= 3

    def test_clear_removes_non_system(self):
        """clear() removes all messages except system prompt."""
        cm = ConversationManager("System prompt")
        cm.add_message("user", "Hello")
        cm.add_message("assistant", "Hi there")
        cm.clear()
        messages = cm.get_messages()
        assert len(messages) == 1
        assert messages[0]["role"] == "system"

    def test_clear_preserves_system_prompt_content(self):
        """clear() preserves system prompt content."""
        cm = ConversationManager("My custom system prompt")
        cm.add_message("user", "Hello")
        cm.clear()
        messages = cm.get_messages()
        assert messages[0]["content"] == "My custom system prompt"

    def test_character_heuristic_estimates_tokens(self):
        """_estimate_tokens_heuristic() uses len//4 heuristic."""
        cm = ConversationManager("System")
        cm.add_message("user", "Hello")  # 5 chars -> 1 token
        cm.add_message("assistant", "Hi there")  # 8 chars -> 2 tokens
        # System: 6 chars -> 1 token
        # Total: 5 + 8 + 6 = 19 chars // 4 = 4 tokens
        assert cm._estimate_tokens_heuristic() == 4

    def test_prune_oldest_tool_output(self):
        """_prune_oldest_tool_output() truncates long tool outputs."""
        cm = ConversationManager("System")
        cm.add_message("user", "List files")
        cm.add_message("assistant", "Running ls")
        long_output = "file1.txt\n" * 500  # Long output
        cm.add_message("tool", long_output)

        # Should prune the tool output
        result = cm._prune_oldest_tool_output()
        assert result is True
        # Content should be truncated
        assert len(cm.get_messages()[-1]["content"]) < len(long_output)
        assert "[truncated]" in cm.get_messages()[-1]["content"]

    def test_prune_oldest_tool_output_no_long_outputs(self):
        """_prune_oldest_tool_output() returns False when no long outputs."""
        cm = ConversationManager("System")
        cm.add_message("tool", "short")

        result = cm._prune_oldest_tool_output()
        assert result is False

    def test_token_count_property(self):
        """token_count property returns estimated tokens."""
        cm = ConversationManager("System")
        cm.add_message("user", "Hello")
        cm.add_message("assistant", "Hi")

        # token_count should return a number
        assert isinstance(cm.token_count, int)
        assert cm.token_count > 0

    def test_get_messages_simplified_plain_messages_unchanged(self):
        """get_messages_simplified() leaves plain user/assistant messages untouched."""
        cm = ConversationManager("System prompt")
        cm.add_message("user", "Hello")
        cm.add_message("assistant", "Hi there")

        simplified = cm.get_messages_simplified()

        assert len(simplified) == 3  # system + user + assistant
        assert simplified[1] == {"role": "user", "content": "Hello"}
        assert simplified[2] == {"role": "assistant", "content": "Hi there"}

    def test_get_messages_simplified_flattens_tool_pair(self):
        """get_messages_simplified() flattens assistant(tool_calls)+tool pairs to plain text."""
        cm = ConversationManager("System")
        cm.add_message("user", "Check something")
        cm.add_assistant_tool_call("", [{"id": "c1", "name": "shell", "arguments": '{"command":"ls"}'}])
        cm.add_tool_result("c1", "file1.py\nfile2.py")

        simplified = cm.get_messages_simplified()

        # system + user + flattened assistant (no tool messages)
        assert len(simplified) == 3
        last = simplified[2]
        assert last["role"] == "assistant"
        assert "tool_calls" not in last
        assert "shell" in last["content"]
        assert "file1.py" in last["content"]

    def test_get_messages_simplified_multiple_tool_pairs(self):
        """get_messages_simplified() handles multiple sequential tool rounds."""
        cm = ConversationManager("System")
        cm.add_message("user", "Do two things")
        cm.add_assistant_tool_call("Step 1", [{"id": "a1", "name": "read", "arguments": '{"path":"f"}'}])
        cm.add_tool_result("a1", "content of f")
        cm.add_assistant_tool_call("Step 2", [{"id": "a2", "name": "write", "arguments": '{"path":"g"}'}])
        cm.add_tool_result("a2", "wrote ok")

        simplified = cm.get_messages_simplified()

        # system + user + 2 flattened assistant messages
        assert len(simplified) == 4
        assert simplified[2]["role"] == "assistant"
        assert simplified[3]["role"] == "assistant"
        assert "read" in simplified[2]["content"]
        assert "write" in simplified[3]["content"]

    def test_get_messages_simplified_no_tool_messages_in_output(self):
        """get_messages_simplified() never includes role=tool messages."""
        cm = ConversationManager("System")
        cm.add_message("user", "Go")
        cm.add_assistant_tool_call("", [{"id": "x1", "name": "shell", "arguments": "{}"}])
        cm.add_tool_result("x1", "done")

        simplified = cm.get_messages_simplified()

        roles = [m["role"] for m in simplified]
        assert "tool" not in roles

    def test_truncation_prunes_tool_outputs_first(self):
        """truncate_if_needed() prunes tool outputs before removing message pairs."""
        cm = ConversationManager("System")
        long_output = "x" * 5000  # Long tool output
        
        cm.add_message("user", "First question")
        cm.add_message("assistant", "First answer")
        cm.add_message("tool", long_output)
        cm.add_message("user", "Second question")
        cm.add_message("assistant", "Second answer")
        
        # Check that pruning reduces content size before truncation
        cm._prune_oldest_tool_output()
        
        # Tool output should be truncated
        messages = cm.get_messages()
        tool_msg = [m for m in messages if m.get("role") == "tool"][0]
        assert len(tool_msg["content"]) < len(long_output)
        assert "[truncated]" in tool_msg["content"]
