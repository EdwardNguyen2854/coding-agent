# TUI Rendering

## Overview

All output goes through `Renderer` in `renderer.py`. There is a single rendering
path: **plain path** using `prompt_toolkit.PromptSession` with a `rprompt`
toolbar (`sidebar.py`) and `rich.live.Live` for streaming (`renderer.py`).

## StreamingDisplay and _LazyMarkdown

`StreamingDisplay` is the context manager used during LLM streaming:

```python
with renderer.render_streaming_live() as display:
    for delta in llm_client.send_message_stream(...):
        display.update(delta)
```

**Before Phase 3**: `display.update()` called `Markdown(self._text)` on every
token, rebuilding the AST once per token (potentially thousands of times).

**After Phase 3**: `_LazyMarkdown` is the renderable passed to `Live`.
- `append(delta)` accumulates text and sets `_cached = None`.
- `__rich_console__` builds `Markdown` only if `_cached is None`, then caches it.
- `Live` calls `__rich_console__` at most `_LIVE_REFRESH_HZ` (8) times per second.

Result: `Markdown` is built at most 8× per second regardless of token rate.

```python
class _LazyMarkdown:
    def append(self, delta: str) -> None:
        self._text += delta
        self._cached = None          # invalidate

    def __rich_console__(self, console, options):
        if self._cached is None:
            self._cached = Markdown(self._text)   # build once per refresh
        yield from self._cached.__rich_console__(console, options)
```

## PlainStreamingDisplay

Used when `console.is_terminal` is `False` (piped output, dumb terminal).
Writes raw text with `print(delta, end="", flush=True)`. No Rich Live.

## Bottom Toolbar

`sidebar.make_toolbar()` returns a callable used as `rprompt` in `PromptSession`.
It reads `conversation.token_count`, git branch, and workflow state on every
prompt redraw. Token count is cached between mutations (see `conversation.py`),
so the toolbar read is O(1) and does not call `litellm.token_counter()` each time.

## Named Constants

| Constant | Module | Value | Purpose |
|---|---|---|---|
| `_LIVE_REFRESH_HZ` | `renderer` | 8 | Live refresh rate |
| `_MAX_DIFF_LINES` | `renderer` | 80 | Diff preview truncation |
| `_MAX_ARG_DISPLAY` | `renderer` | 50 | Tool arg display length |
| `_SHORT_SESSION_ID_LEN` | `renderer` | 12 | Session ID abbreviation |
| `_CTX_CRITICAL` | `sidebar` | 90 | Red context threshold (%) |
| `_CTX_WARNING` | `sidebar` | 70 | Yellow context threshold (%) |
