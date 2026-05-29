"""Content generator — abstraction over LLM content generation.

Provides a thin abstraction layer between the TurnLoop and the LLM client,
allowing cleaner separation of concerns.
"""

from __future__ import annotations

from typing import Any

from opengame.core.llm_client import BaseLlmClient, LlmResponse


class ContentGenerator:
    """Thin wrapper around BaseLlmClient for the TurnLoop.

    Centralizes the LLM call with tool definitions, making it easy to
    swap providers or add middleware (logging, caching, etc.).
    """

    def __init__(self, llm_client: BaseLlmClient) -> None:
        self._client = llm_client

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LlmResponse:
        """Generate a response from the LLM.

        Args:
            messages: Conversation messages.
            tools: Available tool schemas.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.

        Returns:
            LlmResponse with content and/or tool calls.
        """
        return await self._client.generate(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )
