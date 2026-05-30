"""Content generator — abstraction over LLM content generation.

Provides a thin abstraction layer between the TurnLoop and the LLM client,
allowing cleaner separation of concerns with optional trace recording.
"""

from __future__ import annotations

import time
from typing import Any

from opengame.core.llm_client import BaseLlmClient, LlmResponse


class ContentGenerator:
    """Thin wrapper around BaseLlmClient for the TurnLoop.

    Centralizes the LLM call with tool definitions, making it easy to
    swap providers or add middleware (logging, caching, tracing, etc.).
    """

    def __init__(self, llm_client: BaseLlmClient) -> None:
        self._client = llm_client
        self._tracer = None

    def set_tracer(self, tracer: Any) -> None:
        """Inject a TraceSession for recording LLM exchanges."""
        self._tracer = tracer

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        phase: str = "",
    ) -> LlmResponse:
        """Generate a response from the LLM.

        Args:
            messages: Conversation messages.
            tools: Available tool schemas.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            phase: Optional pipeline phase name for tracing.

        Returns:
            LlmResponse with content and/or tool calls.
        """
        start = time.monotonic()

        response = await self._client.generate(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Record full LLM exchange if tracer is active
        if self._tracer and phase:
            tool_calls_data = None
            if response.tool_calls:
                tool_calls_data = [
                    {"id": tc.id, "name": tc.name,
                     "arguments": tc.arguments}
                    for tc in response.tool_calls
                ]

            token_usage = None
            if response.usage:
                token_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            self._tracer.record_llm_exchange(
                phase=phase,
                messages=messages,
                response_content=response.content,
                model=response.model or self._client.model,
                finish_reason=response.finish_reason,
                token_usage=token_usage,
                tool_calls=tool_calls_data,
                elapsed_ms=elapsed_ms,
            )

        return response
