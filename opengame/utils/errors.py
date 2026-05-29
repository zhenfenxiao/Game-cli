"""Custom exception hierarchy for OpenGame.

All OpenGame errors inherit from OpenGameError and carry:
- message: Human-readable description
- context: Structured context dict for debugging
- recoverable: Whether the operation can be retried
"""

from typing import Any


class OpenGameError(Exception):
    """Base exception for all OpenGame errors."""

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        recoverable: bool = False,
    ) -> None:
        self.message = message
        self.context = context or {}
        self.recoverable = recoverable
        super().__init__(message)

    def __str__(self) -> str:
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"[{self.__class__.__name__}] {self.message} (context: {ctx_str})"
        return f"[{self.__class__.__name__}] {self.message}"


class LlmError(OpenGameError):
    """LLM API errors (rate limit, timeout, invalid response)."""

    pass


class ToolError(OpenGameError):
    """Tool execution errors."""

    pass


class ConfigError(OpenGameError):
    """Configuration errors."""

    pass


class DebugError(OpenGameError):
    """Debug loop failures."""

    pass


class AssetError(OpenGameError):
    """Asset generation failures."""

    pass
