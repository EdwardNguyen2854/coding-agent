from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolResult:
    """Standard envelope for all tool responses.

    This replaces the older tools.base.ToolResult and should be used by all tools.
    """

    ok: bool
    error_code: Optional[str]
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)

    def __init__(
        self,
        ok: Optional[bool] = None,
        error_code: Optional[str] = None,
        message: str = "",
        data: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
        # Legacy kwargs from older tools.base.ToolResult
        output: Optional[str] = None,
        error: Optional[str] = None,
        is_error: Optional[bool] = None,
    ) -> None:
        # Resolve ok from is_error if not explicitly provided
        if ok is None:
            self.ok = not is_error if is_error is not None else True
        else:
            self.ok = ok

        # Resolve message from legacy error/output fields
        if message == "" and error:
            self.message = error
        elif message == "" and output:
            self.message = output
        else:
            self.message = message

        # Resolve data from legacy output field
        if data is not None:
            self.data = data
        elif output is not None:
            self.data = {"output": output}
        else:
            self.data = {}

        self.error_code = error_code
        self.warnings = warnings or []
        self.artifacts = artifacts or []

    @property
    def is_error(self) -> bool:
        """Legacy read access: mirrors ok."""
        return not self.ok

    @property
    def output(self) -> Optional[str]:
        """Legacy read access: returns data['content'], data['output'], or message."""
        return self.data.get("content") or self.data.get("output") or self.message

    @classmethod
    def success(
        cls,
        data: Optional[Dict[str, Any]] = None,
        message: str = "",
        warnings: Optional[List[str]] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> "ToolResult":
        return cls(
            ok=True,
            error_code=None,
            message=message,
            data=data or {},
            warnings=warnings or [],
            artifacts=artifacts or [],
        )

    @classmethod
    def failure(
        cls,
        error_code: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> "ToolResult":
        return cls(
            ok=False,
            error_code=error_code,
            message=message,
            data=data or {},
            warnings=warnings or [],
            artifacts=artifacts or [],
        )
