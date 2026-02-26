from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.core.tool_guard import ToolGuard
from coding_agent.core.tool_result import ToolResult

SCHEMA = {
    "name": "file_patch",
    "description": (
        "Apply patches to files in the workspace. Accepts either a unified diff string "
        "(diff_text) or a structured list of hunks (patches). "
        "Prefer file_patch over file_write for surgical edits — it is safer and produces "
        "a clear audit trail. Use file_write only when creating a file from scratch or "
        "replacing its entire content. See docs/patch_vs_write.md for full guidance."
    ),
    "properties": {
        "diff_text": {
            "type": "string",
            "description": "A unified diff string (--- a/... +++ b/... @@ ... @@). Mutually exclusive with patches.",
        },
        "patches": {
            "type": "array",
            "items": {"type": "object"},
            "description": "Structured patch list. Mutually exclusive with diff_text.",
        },
        "file_hash": {
            "type": "string",
            "description": (
                "Optional SHA-256 hex digest of the target file(s). "
                "If provided, the patch is rejected when the file has changed since the hash was computed."
            ),
        },
    },
    "required": [],
}


class FilePatchTool:
    name = "file_patch"

    def __init__(self, workspace_root: str, policy: Optional[Dict[str, Any]] = None) -> None:
        self._guard = ToolGuard(workspace_root=workspace_root, policy=policy or {})
        self._workspace_root = Path(workspace_root).resolve()

    def schema(self) -> Dict[str, Any]:
        return SCHEMA

    def run(self, args: Dict[str, Any]) -> ToolResult:
        blocked = self._guard.check(self.name, args, schema=SCHEMA)
        if blocked is not None:
            return blocked

        diff_text: Optional[str] = args.get("diff_text")
        patches: Optional[List[Dict[str, Any]]] = args.get("patches")
        file_hash: Optional[str] = args.get("file_hash")

        if diff_text is None and patches is None:
            return ToolResult.failure(
                "MISSING_INPUT",
                "Provide either diff_text (unified diff) or patches (structured hunks).",
            )
        if diff_text is not None and patches is not None:
            return ToolResult.failure(
                "AMBIGUOUS_INPUT",
                "Provide either diff_text or patches, not both.",
            )

        if diff_text is not None:
            return self._apply_unified_diff(diff_text, file_hash)
        return self._apply_structured_patches(patches, file_hash)  # type: ignore[arg-type]

    # ------------------------------------------------------------------ unified diff

    def _apply_unified_diff(self, diff_text: str, file_hash: Optional[str]) -> ToolResult:
        # Try whatthepatch, fall back to `patch` binary
        try:
            import whatthepatch  # type: ignore
            return self._apply_with_whatthepatch(diff_text, file_hash)
        except ImportError:
            pass

        # Fall back to `patch` binary
        patch_bin = self._find_patch_binary()
        if patch_bin:
            return self._apply_with_patch_binary(diff_text, file_hash, patch_bin)

        return ToolResult.failure(
            "NO_PATCH_BACKEND",
            "Neither 'whatthepatch' (pip install whatthepatch) nor the 'patch' binary is available.",
        )

    def _apply_with_whatthepatch(self, diff_text: str, file_hash: Optional[str]) -> ToolResult:
        import whatthepatch  # type: ignore

        files_changed: List[str] = []
        rejected_hunks: List[Dict[str, Any]] = []

        try:
            diffs = list(whatthepatch.parse_patch(diff_text))
        except Exception as exc:
            return ToolResult.failure("PARSE_ERROR", f"Could not parse diff: {exc}")

        for diff in diffs:
            if diff.header is None:
                continue

            target = diff.header.new_path or diff.header.old_path
            if target is None:
                continue
            # Strip leading a/ b/ prefixes
            if target.startswith(("a/", "b/")):
                target = target[2:]

            file_path = (self._workspace_root / target).resolve()
            rel = str(file_path.relative_to(self._workspace_root)).replace("\\", "/")

            # Hash check
            if file_hash and file_path.exists():
                actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
                if actual_hash != file_hash:
                    return ToolResult.failure(
                        "HASH_MISMATCH",
                        f"File '{rel}' has changed since hash was computed. Re-read the file and retry.",
                    )

            original_lines = []
            if file_path.exists():
                original_lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

            try:
                new_text = whatthepatch.apply_diff(diff, "".join(original_lines))
                if new_text is None:
                    rejected_hunks.append({"file": rel, "reason": "apply_diff returned None"})
                    continue
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(new_text, encoding="utf-8")
                files_changed.append(rel)
            except Exception as exc:
                rejected_hunks.append({"file": rel, "reason": str(exc)})

        if not files_changed and rejected_hunks:
            return ToolResult.failure(
                "ALL_HUNKS_REJECTED",
                f"No hunks could be applied. {len(rejected_hunks)} rejected.",
                data={"files_changed": [], "rejected_hunks": rejected_hunks},
            )

        return ToolResult.success(
            data={
                "applied": len(files_changed) > 0,
                "files_changed": files_changed,
                "rejected_hunks": rejected_hunks,
            },
            message=f"Patched {len(files_changed)} file(s); {len(rejected_hunks)} hunk(s) rejected",
            warnings=[f"{len(rejected_hunks)} hunk(s) could not be applied"] if rejected_hunks else [],
        )

    def _apply_with_patch_binary(
        self, diff_text: str, file_hash: Optional[str], patch_bin: str
    ) -> ToolResult:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False, encoding="utf-8") as f:
            f.write(diff_text)
            patch_file = f.name

        try:
            proc = subprocess.run(
                [patch_bin, "-p1", "--batch", f"--input={patch_file}"],
                capture_output=True,
                text=True,
                cwd=str(self._workspace_root),
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return ToolResult.failure("TIMEOUT", "patch binary timed out")
        finally:
            Path(patch_file).unlink(missing_ok=True)

        if proc.returncode != 0:
            return ToolResult.failure(
                "PATCH_FAILED",
                f"patch binary failed (exit {proc.returncode}): {proc.stderr.strip()}",
                data={"stdout": proc.stdout, "stderr": proc.stderr, "rejected_hunks": []},
            )

        # Parse stdout for changed files
        files_changed = []
        for line in proc.stdout.splitlines():
            if line.startswith("patching file "):
                files_changed.append(line[len("patching file "):].strip())

        return ToolResult.success(
            data={"applied": True, "files_changed": files_changed, "rejected_hunks": []},
            message=f"Patched {len(files_changed)} file(s) via patch binary",
        )

    @staticmethod
    def _find_patch_binary() -> Optional[str]:
        for candidate in ["patch", "/usr/bin/patch"]:
            try:
                subprocess.run([candidate, "--version"], capture_output=True, check=True, timeout=5)
                return candidate
            except Exception:
                continue
        return None

    # ---------------------------------------------------------- structured patches

    def _apply_structured_patches(
        self, patches: List[Dict[str, Any]], file_hash: Optional[str]
    ) -> ToolResult:
        """
        patches: [
            {
                "path": "src/foo.py",
                "hunks": [
                    {"start": 10, "end": 14, "replace_with": "new content here\n"}
                ]
            }
        ]
        Line numbers are 1-based and inclusive.
        """
        files_changed: List[str] = []
        rejected_hunks: List[Dict[str, Any]] = []

        for patch in patches:
            raw_path = patch.get("path")
            hunks = patch.get("hunks", [])
            if not raw_path:
                rejected_hunks.append({"reason": "patch entry missing 'path'"})
                continue

            file_path = (self._workspace_root / raw_path).resolve()
            rel = str(file_path.relative_to(self._workspace_root)).replace("\\", "/")

            if not file_path.exists():
                rejected_hunks.append({"file": rel, "reason": "file not found"})
                continue

            # Hash check
            if file_hash:
                actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
                if actual_hash != file_hash:
                    return ToolResult.failure(
                        "HASH_MISMATCH",
                        f"File '{rel}' has changed since hash was computed.",
                    )

            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

            # Apply hunks in reverse order to preserve line numbers
            sorted_hunks = sorted(hunks, key=lambda h: h.get("start", 0), reverse=True)
            file_rejected: List[Dict[str, Any]] = []

            for hunk in sorted_hunks:
                start = hunk.get("start")
                end = hunk.get("end")
                replace_with: str = hunk.get("replace_with", "")

                if start is None or end is None:
                    file_rejected.append({**hunk, "reason": "hunk missing start or end"})
                    continue
                if start < 1 or end > len(lines) or start > end:
                    file_rejected.append({
                        **hunk,
                        "reason": f"hunk range [{start},{end}] out of bounds (file has {len(lines)} lines)",
                    })
                    continue

                replacement_lines = replace_with.splitlines(keepends=True)
                if replacement_lines and not replacement_lines[-1].endswith("\n"):
                    replacement_lines[-1] += "\n"

                # 1-based to 0-based
                lines[start - 1: end] = replacement_lines

            if file_rejected:
                rejected_hunks.extend(file_rejected)

            if not file_rejected or len(file_rejected) < len(sorted_hunks):
                file_path.write_text("".join(lines), encoding="utf-8")
                files_changed.append(rel)

        return ToolResult.success(
            data={
                "applied": len(files_changed) > 0,
                "files_changed": files_changed,
                "rejected_hunks": rejected_hunks,
            },
            message=f"Patched {len(files_changed)} file(s); {len(rejected_hunks)} hunk(s) rejected",
            warnings=[f"{len(rejected_hunks)} hunk(s) could not be applied"] if rejected_hunks else [],
        )
