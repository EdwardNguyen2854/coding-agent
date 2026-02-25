"""Performance tests for Phase 3 fixes."""

from unittest.mock import MagicMock, patch


class TestLazyMarkdown:
    """Test that StreamingDisplay rebuilds Markdown lazily via _LazyMarkdown."""

    def test_streaming_markdown_not_rebuilt_per_token(self):
        """Markdown constructor should be called far fewer than 100 times for 100 tokens."""
        from coding_agent.renderer import StreamingDisplay, _LazyMarkdown

        console = MagicMock()

        markdown_init_calls = [0]
        original_init = __import__("rich.markdown", fromlist=["Markdown"]).Markdown.__init__

        def counting_init(self, *args, **kwargs):
            markdown_init_calls[0] += 1
            original_init(self, *args, **kwargs)

        with patch("coding_agent.renderer.Markdown.__init__", counting_init):
            lazy = _LazyMarkdown()
            for i in range(100):
                lazy.append(f"token{i} ")
            # Simulate one render call (what Live does at refresh rate)
            fake_console = MagicMock()
            fake_options = MagicMock()
            list(lazy.__rich_console__(fake_console, fake_options))

        # Should have built Markdown at most once (on render), not 100 times
        assert markdown_init_calls[0] < 20, (
            f"Markdown was built {markdown_init_calls[0]} times, expected < 20"
        )

    def test_lazy_markdown_caches_between_renders(self):
        """_LazyMarkdown caches the Markdown object between renders without appends."""
        from coding_agent.renderer import _LazyMarkdown

        lazy = _LazyMarkdown()
        lazy.append("hello world")

        build_count = [0]
        original_init = __import__("rich.markdown", fromlist=["Markdown"]).Markdown.__init__

        def counting_init(self, *args, **kwargs):
            build_count[0] += 1
            original_init(self, *args, **kwargs)

        with patch("coding_agent.renderer.Markdown.__init__", counting_init):
            fake_console = MagicMock()
            fake_options = MagicMock()
            # Two renders without any append — should only build once
            list(lazy.__rich_console__(fake_console, fake_options))
            list(lazy.__rich_console__(fake_console, fake_options))

        assert build_count[0] == 1, (
            f"Markdown was rebuilt {build_count[0]} times, expected 1 (cached)"
        )

    def test_lazy_markdown_invalidates_on_append(self):
        """_LazyMarkdown rebuilds Markdown after an append."""
        from coding_agent.renderer import _LazyMarkdown

        lazy = _LazyMarkdown()
        lazy.append("first")

        build_count = [0]
        original_init = __import__("rich.markdown", fromlist=["Markdown"]).Markdown.__init__

        def counting_init(self, *args, **kwargs):
            build_count[0] += 1
            original_init(self, *args, **kwargs)

        with patch("coding_agent.renderer.Markdown.__init__", counting_init):
            fake_console = MagicMock()
            fake_options = MagicMock()
            list(lazy.__rich_console__(fake_console, fake_options))  # build 1
            lazy.append(" second")
            list(lazy.__rich_console__(fake_console, fake_options))  # build 2 after append

        assert build_count[0] == 2, (
            f"Expected 2 Markdown builds (one per append), got {build_count[0]}"
        )


class TestTokenCountCache:
    """Test that token_count property is cached and invalidated correctly."""

    def test_token_count_cache(self):
        """token_count should use cached value after first computation."""
        from coding_agent.conversation import ConversationManager

        conv = ConversationManager("system prompt")
        call_count = [0]

        original = conv._estimate_tokens

        def counting_estimate():
            call_count[0] += 1
            return original()

        conv._estimate_tokens = counting_estimate

        # Access token_count 10 times
        for _ in range(10):
            _ = conv.token_count

        assert call_count[0] == 1, (
            f"_estimate_tokens called {call_count[0]} times, expected 1 (cached)"
        )

    def test_token_count_invalidates_on_new_message(self):
        """Cache is cleared after add_message."""
        from coding_agent.conversation import ConversationManager

        conv = ConversationManager("system prompt")
        call_count = [0]

        original = conv._estimate_tokens

        def counting_estimate():
            call_count[0] += 1
            return original()

        conv._estimate_tokens = counting_estimate

        _ = conv.token_count        # call 1
        conv.add_message("user", "hello")
        _ = conv.token_count        # call 2 (cache invalidated)
        _ = conv.token_count        # still call 2 (cached again)

        assert call_count[0] == 2, (
            f"_estimate_tokens called {call_count[0]} times, expected 2"
        )

    def test_token_count_invalidates_on_tool_result(self):
        """Cache is cleared after add_tool_result."""
        from coding_agent.conversation import ConversationManager

        conv = ConversationManager("system prompt")
        call_count = [0]
        original = conv._estimate_tokens

        def counting_estimate():
            call_count[0] += 1
            return original()

        conv._estimate_tokens = counting_estimate

        _ = conv.token_count
        conv.add_tool_result("tc1", "result content")
        _ = conv.token_count

        assert call_count[0] == 2

    def test_token_count_invalidates_on_clear(self):
        """Cache is cleared after clear()."""
        from coding_agent.conversation import ConversationManager

        conv = ConversationManager("system prompt")
        call_count = [0]
        original = conv._estimate_tokens

        def counting_estimate():
            call_count[0] += 1
            return original()

        conv._estimate_tokens = counting_estimate

        _ = conv.token_count
        conv.clear()
        _ = conv.token_count

        assert call_count[0] == 2
