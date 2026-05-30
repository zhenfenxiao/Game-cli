"""OpenAI-compatible LLM client.

Supports streaming with tool call accumulation, non-streaming generation,
and automatic retries.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from opengame.core.llm_client import BaseLlmClient, LlmResponse, LlmUsage
from opengame.core.tool_registry import ToolCall
from opengame.utils.retry import retry


class OpenAiClient(BaseLlmClient):
    """LLM client for OpenAI and OpenAI-compatible APIs.

    Supports streaming with tool call delta accumulation, which is
    the most complex part of the client. Tool calls from streaming
    responses arrive as JSON fragments that must be accumulated.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(model=model, base_url=base_url, api_key=api_key)
        self.timeout = timeout
        self._client = AsyncOpenAI(
            api_key=api_key or "not-set",
            base_url=base_url,
            timeout=timeout,
        )

    @retry(max_retries=3, backoff_base=1.0, backoff_max=30.0, exceptions=(Exception,))
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
            tools: Optional list of tool schemas.
            stream: If True, accumulate a streaming response.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            LlmResponse with content and/or tool calls.
        """
        if stream:
            return await self._streaming_generate(messages, tools, temperature, max_tokens)
        return await self._blocking_generate(messages, tools, temperature, max_tokens)

    async def stream_generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LlmResponse]:
        """Stream a response, yielding partial content as it arrives.

        Args:
            messages: List of message dicts.
            tools: Optional tool schemas.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Yields:
            LlmResponse objects with incremental content.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        stream = await self._client.chat.completions.create(**kwargs)

        accumulated_content = ""
        tool_call_acc: dict[int, dict[str, Any]] = {}
        finish_reason = "stop"

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            finish = chunk.choices[0].finish_reason if chunk.choices else None

            if finish:
                finish_reason = finish

            if delta:
                # Accumulate text content
                if delta.content:
                    accumulated_content += delta.content

                # Accumulate tool call deltas
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_call_acc:
                            tool_call_acc[idx] = {
                                "id": tc_delta.id or "",
                                "name": "",
                                "arguments": "",
                            }

                        if tc_delta.id:
                            tool_call_acc[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_call_acc[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_call_acc[idx]["arguments"] += tc_delta.function.arguments

            # Build tool calls from accumulated fragments
            tool_calls: list[ToolCall] = []
            for idx in sorted(tool_call_acc.keys()):
                tc = tool_call_acc[idx]
                if tc["name"]:
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append(ToolCall(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=args,
                    ))

            yield LlmResponse(
                content=accumulated_content,
                tool_calls=tool_calls if not finish or finish == "tool_calls" else [],
                finish_reason=finish_reason,
                model=self.model,
            )

    # --- Private methods ---

    async def _blocking_generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
    ) -> LlmResponse:
        """Non-streaming generation."""
        # Detect reasoning models (deepseek-v4-pro, o1, o3, etc.)
        is_reasoning_model = any(
            prefix in self.model.lower()
            for prefix in ("deepseek-v4", "deepseek-r1", "o1", "o3", "o4")
        )

        # Reasoning models need larger token budget (reasoning tokens are included)
        if is_reasoning_model and max_tokens < 4096:
            max_tokens = 4096

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        # Reasoning models may not support temperature simultaneously
        if not is_reasoning_model:
            kwargs["temperature"] = temperature

        if tools:
            kwargs["tools"] = tools

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        content = choice.message.content or ""
        finish_reason = choice.finish_reason or "stop"

        tool_calls: list[ToolCall] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        usage = None
        if response.usage:
            usage = LlmUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        return LlmResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            model=response.model,
        )

    async def _streaming_generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
    ) -> LlmResponse:
        """Accumulate a streaming response into a single LlmResponse."""
        final_response = LlmResponse(model=self.model)
        async for partial in self.stream_generate(messages, tools, temperature, max_tokens):
            final_response = partial
        return final_response
