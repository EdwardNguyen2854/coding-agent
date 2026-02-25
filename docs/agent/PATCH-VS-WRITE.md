# `file_patch` vs `file_write` — When to Use Which

## Short answer

| Situation | Use |
|---|---|
| Creating a brand-new file | `file_write` |
| Replacing **all** of a file's content | `file_write` |
| Changing **part** of an existing file | `file_patch` |
| Renaming a symbol / updating references | `file_patch` |
| Fixing a specific lint or type error | `file_patch` |
| Generating a file from a template | `file_write` |

---

## Why `file_patch` is almost always better for edits

`file_patch` applies a targeted change. It:

- **Makes the diff reviewable.** The model and human can both see exactly what changed.
- **Reduces accidental regressions.** Only the touched lines are modified; the rest of the file is untouched.
- **Detects conflicts early.** If the file has changed since you read it, `file_patch` can be given a `file_hash` to reject the operation before clobbering someone else's edits.
- **Produces a clean audit trail.** The patch input is logged by `ToolGuard` alongside the operation.

`file_write` replaces the entire file. If you've only read lines 1–50 and the file has 500 lines, writing back only what you saw silently deletes lines 51–500.

---

## Input modes for `file_patch`

### Mode A — Unified diff

Best when you already have a diff or you want to express the change in a standard format.

```json
{
  "diff_text": "--- a/src/foo.py\n+++ b/src/foo.py\n@@ -10,4 +10,4 @@\n-old_name(\n+new_name(\n"
}
```

### Mode B — Structured hunks

Best when you know the exact line range to replace without computing a full diff. Easier to generate programmatically.

```json
{
  "patches": [
    {
      "path": "src/foo.py",
      "hunks": [
        { "start": 10, "end": 14, "replace_with": "new_name(args)\n" }
      ]
    }
  ]
}
```

`start` and `end` are **1-based, inclusive** line numbers. Multiple hunks in one call are applied in reverse order (highest line number first) to keep earlier line numbers valid.

### Optional: `file_hash` guard

To prevent accidentally patching a file that has changed since you last read it:

```json
{
  "diff_text": "...",
  "file_hash": "abc123..."
}
```

Compute the hash with `hashlib.sha256(path.read_bytes()).hexdigest()` and pass it along. If the file has been modified, the patch is rejected with error code `HASH_MISMATCH`.

---

## When `file_write` is the right choice

- **New files.** The file doesn't exist yet; there's nothing to patch.
- **Full content replacement.** You've generated the complete new content from scratch (e.g. a template renderer, a code generator).
- **Binary or non-text files.** `file_patch` works on text; `file_write` can handle arbitrary bytes.

---

## Conflict handling

`file_patch` returns a `rejected_hunks` list if any hunks cannot be applied. Check this field; never assume silence means success:

```python
result = tool.run({"patches": [...]})
if result.data["rejected_hunks"]:
    # Re-read the file, recalculate the patch, and retry
    ...
```

---

## Quick decision tree

```
Is the file new?
  └─ Yes → file_write

Am I replacing the whole file?
  └─ Yes → file_write

Am I changing specific lines or symbols?
  └─ Yes → file_patch (prefer structured hunks for precision,
                        unified diff for readability)
```
