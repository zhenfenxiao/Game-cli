"""Tests for TurnLoop."""

from unittest.mock import AsyncMock

import pytest

from opengame.core.tool_registry import ToolRegistry
from opengame.core.turn_loop import TurnLoop


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock()
    llm.model = "gpt-4o"
    return llm


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()

    @reg.tool(name="echo", description="Echo back the message")
    async def echo(message: str) -> str:
        return f"Echo: {message}"

    return reg


class TestTurnLoopBasic:
    @pytest.mark.asyncio
    async def test_single_turn_no_tool_calls(
        self, mock_llm: AsyncMock, registry: ToolRegistry,
    ) -> None:
        mock_llm.generate.return_value.content = "I have completed the task."
        mock_llm.generate.return_value.tool_calls = []
        mock_llm.generate.return_value.finish_reason = "stop"

        loop = TurnLoop(mock_llm, registry)
        result = await loop.run(
            system_prompt="You are a helpful assistant.",
            user_message="Say hello",
        )

        assert result.finished is True
        assert "completed" in result.text.lower()
        assert result.turn_count == 1

    @pytest.mark.asyncio
    async def test_multi_turn_with_tool_calls(
        self, mock_llm: AsyncMock, registry: ToolRegistry,
    ) -> None:
        # First call: return a tool call
        call1 = AsyncMock()
        call1.content = None
        call1.tool_calls = [
            type("ToolCall", (), {
                "id": "call_1",
                "name": "echo",
                "arguments": {"message": "hello"},
            })()
        ]
        call1.finish_reason = "tool_calls"

        # Second call: final response
        call2 = AsyncMock()
        call2.content = "Got the echo, task done."
        call2.tool_calls = []
        call2.finish_reason = "stop"

        mock_llm.generate.side_effect = [call1, call2]

        loop = TurnLoop(mock_llm, registry)
        result = await loop.run(
            system_prompt="You are helpful.",
            user_message="Echo hello",
        )

        assert result.finished is True
        assert result.turn_count == 2

    @pytest.mark.asyncio
    async def test_max_turns_exceeded(
        self, mock_llm: AsyncMock, registry: ToolRegistry,
    ) -> None:
        # Always return tool calls to force looping
        mock_llm.generate.return_value.content = None
        mock_llm.generate.return_value.tool_calls = [
            type("ToolCall", (), {
                "id": "call_1",
                "name": "echo",
                "arguments": {"message": "x"},
            })()
        ]
        mock_llm.generate.return_value.finish_reason = "tool_calls"

        loop = TurnLoop(mock_llm, registry, max_turns=3)
        result = await loop.run(
            system_prompt="You are helpful.",
            user_message="Keep echoing",
        )

        assert result.finished is False
        assert "maximum" in result.text.lower() and "turns" in result.text.lower()
        assert result.turn_count == 3

    @pytest.mark.asyncio
    async def test_tool_execution_error_handled(
        self, mock_llm: AsyncMock, registry: ToolRegistry,
    ) -> None:
        # Register a tool that raises an error
        @registry.tool(name="failer", description="Always fails")
        async def failer() -> str:
            raise ValueError("Intentional failure")

        # First: tool call to failer
        call1 = AsyncMock()
        call1.content = None
        call1.tool_calls = [
            type("ToolCall", (), {
                "id": "call_x",
                "name": "failer",
                "arguments": {},
            })()
        ]
        call1.finish_reason = "tool_calls"

        # Second: LLM sees error and responds
        call2 = AsyncMock()
        call2.content = "The tool failed but I can handle it."
        call2.tool_calls = []
        call2.finish_reason = "stop"

        mock_llm.generate.side_effect = [call1, call2]

        loop = TurnLoop(mock_llm, registry, max_turns=5)
        result = await loop.run(
            system_prompt="You are helpful.",
            user_message="Try the failer",
        )

        assert result.finished is True
