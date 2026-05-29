"""Base LLM client abstract class and response types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from opengame.core.tool_registry import ToolCall


@dataclass
class LlmUsage:
    """Token usage statistics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LlmResponse:
    """Response from an LLM API call."""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: LlmUsage | None = None
    model: str = ""


class BaseLlmClient(ABC):
    """Abstract base class for LLM API clients.

    All LLM providers implement this interface, supporting both
    streaming and non-streaming generation with tool calling.
    """

    def __init__(self, model: str = "gpt-4o", base_url: str | None = None, api_key: str | None = None) -> None:
        self.model = model
        self.base_url = base_url
        self.api_key = api_key

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LlmResponse:
        """Generate a response from the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool schemas available to the model.
            stream: If True, stream the response (returned as accumulated).
            temperature: Sampling temperature (0.0 - 2.0).
            max_tokens: Maximum tokens in the response.

        Returns:
            LlmResponse with content and/or tool calls.
        """
        ...

    @abstractmethod
    async def stream_generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LlmResponse]:
        """Stream a response from the LLM.

        Yields partial LlmResponse objects as tokens arrive. The final
        response includes complete accumulated tool calls.

        Args:
            messages: List of message dicts.
            tools: Optional tool schemas.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Yields:
            LlmResponse objects with incremental content.
        """
        ...
