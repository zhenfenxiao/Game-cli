"""Tests for InteractiveLoop."""

from unittest.mock import AsyncMock

import pytest

from opengame.core.exceptions import UserQuestionRequested
from opengame.core.interactive_loop import InteractiveLoop, TurnOutcome
from opengame.core.tool_registry import ToolRegistry
from opengame.tools.interactive_tools import register_interactive_tools


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock()
    llm.model = "test-model"
    return llm


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()

    @reg.tool(name="echo", description="Echo back")
    async def echo(message: str) -> str:
        return f"Echo: {message}"

    return reg


class TestInteractiveLoop:
    @pytest.mark.asyncio
    async def test_single_turn_done(self, mock_llm: AsyncMock, registry: ToolRegistry) -> None:
        """LLM returns text, no tool calls → DONE."""
        mock_llm.generate.return_value.content = "Task complete."
        mock_llm.generate.return_value.tool_calls = []
        mock_llm.generate.return_value.finish_reason = "stop"

        loop = InteractiveLoop(mock_llm, registry)
        loop.start("You are helpful.")

        output = await loop.send_message("Do something")
        assert output.outcome == TurnOutcome.DONE
        assert "Task complete" in output.content

    @pytest.mark.asyncio
    async def test_tool_call_then_done(self, mock_llm: AsyncMock, registry: ToolRegistry) -> None:
        """LLM calls tool, then responds → DONE after tool execution."""
        call1 = AsyncMock()
        call1.content = None
        call1.tool_calls = [
            type("TC", (), {"id": "1", "name": "echo", "arguments": {"message": "hello"}})()
        ]
        call1.finish_reason = "tool_calls"

        call2 = AsyncMock()
        call2.content = "Echo received."
        call2.tool_calls = []
        call2.finish_reason = "stop"

        mock_llm.generate.side_effect = [call1, call2]

        loop = InteractiveLoop(mock_llm, registry)
        loop.start("You are helpful.")

        output = await loop.send_message("Echo hello")
        assert output.outcome == TurnOutcome.DONE
        assert "Echo received" in output.content

    @pytest.mark.asyncio
    async def test_ask_user_pauses_execution(self, mock_llm: AsyncMock) -> None:
        """ask_user tool pauses loop with USER_QUESTION outcome."""
        reg = ToolRegistry()
        register_interactive_tools(reg)

        call1 = AsyncMock()
        call1.content = None
        call1.tool_calls = [
            type("TC", (), {"id": "u1", "name": "ask_user", "arguments": {
                "question": "What color?",
                "header": "Color",
            }})()
        ]
        call1.finish_reason = "tool_calls"

        call2 = AsyncMock()
        call2.content = "Got it, using dark theme."
        call2.tool_calls = []
        call2.finish_reason = "stop"

        mock_llm.generate.side_effect = [call1, call2]

        loop = InteractiveLoop(mock_llm, reg)
        loop.start("You are a designer.")

        output = await loop.send_message("Pick a theme")
        assert output.outcome == TurnOutcome.USER_QUESTION
        assert output.question is not None
        assert "What color" in output.question.question

        # Answer the question
        output2 = await loop.answer_question("dark")
        assert output2.outcome == TurnOutcome.DONE
        assert "Got it" in output2.content

    @pytest.mark.asyncio
    async def test_user_question_exception(self) -> None:
        """UserQuestionRequested exception has correct fields."""
        exc = UserQuestionRequested(
            question="Test?",
            header="Test",
            options=["a", "b"],
        )
        assert exc.question == "Test?"
        assert exc.header == "Test"
        assert exc.options == ["a", "b"]
        assert exc.response is None

        exc.response = "a"
        assert exc.response == "a"
