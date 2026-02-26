# Architecture Overview

## Module Boundaries

```
cli.py            Entry point (Click commands). Owns the REPL loop.
agent.py          ReAct loop: LLM call → tool call → repeat.
llm.py            LiteLLM wrapper: streaming, retries, error mapping.
conversation.py   Message history + token estimation/caching.
permissions.py    Per-tool approval (auto-allow / prompt user).
renderer.py       All Rich output: streaming, spinners, diffs, banners.
sidebar.py        Bottom toolbar for PromptSession (token %, branch, todos).
session.py        JSON session persistence (~/.coding-agent/sessions/).
tools/            Tool registry: file_read, shell, git_diff, etc.
workflow.py       Plan → approve → execute state machine.
```

## Rendering Pipeline

```
cli.py (REPL)
  └─ Renderer()                   # plain path; no split pane
       ├─ render_banner()         # startup panel
       ├─ render_streaming_live() # returns StreamingDisplay or PlainStreamingDisplay
       │     StreamingDisplay
       │       └─ _LazyMarkdown   # invalidates Markdown cache on append()
       │            └─ Live       # refreshes at _LIVE_REFRESH_HZ (8 Hz)
       ├─ status_spinner()        # Rich Status during tool execution
       └─ print_error / print_info / print_warning / print_success
```

## ReAct Loop Flow

```
agent.run(user_input)
  ├─ conversation.add_message("user", ...)
  └─ while True:
       ├─ conversation.truncate_if_needed()   # stale-loop-safe
       ├─ llm_client.send_message_stream()    # streams deltas
       │     → display.update(delta)          # _LazyMarkdown.append()
       ├─ response has tool_calls?
       │   NO  → add assistant message, return
       │   YES → _handle_tool_call() for each
       │          ├─ permissions.check_approval()
       │          ├─ execute_tool()
       │          └─ conversation.add_message("tool", result)
       └─ loop
```

## Key Design Decisions

- **Plain path only**: The split-pane layout (`split_layout.py`) was removed.
  The single rendering path reduces complexity and eliminates TUI instability.
- **`_LazyMarkdown`**: Avoids rebuilding `rich.Markdown` on every streamed token.
  The object is rebuilt at most once per Live refresh interval (≤8 Hz).
- **Token cache**: `ConversationManager.token_count` caches the result of
  `litellm.token_counter()` and invalidates on every mutation (`add_message`,
  `add_assistant_tool_call`, `add_tool_result`, `clear`).
- **Stale-loop guard in `truncate_if_needed`**: tracks `prev_estimate` so the
  loop exits if the token estimate stops decreasing (prevents infinite loops).
