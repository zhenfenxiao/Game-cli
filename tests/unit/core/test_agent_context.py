"""Tests for AgentContext and TurnLoopResult."""

from opengame.core.agent_context import AgentContext, TurnLoopResult


class TestAgentContext:
    def test_default_construction(self) -> None:
        ctx = AgentContext()
        assert ctx.messages == []
        assert ctx.turn_count == 0
        assert ctx.todo_list == []

    def test_add_message(self) -> None:
        ctx = AgentContext()
        ctx.add_message("user", "Hello")
        assert len(ctx.messages) == 1
        assert ctx.messages[0]["role"] == "user"
        assert ctx.messages[0]["content"] == "Hello"

    def test_add_message_with_kwargs(self) -> None:
        ctx = AgentContext()
        ctx.add_message("assistant", "Hi", tool_calls=[{"id": "1"}])
        assert ctx.messages[0]["tool_calls"] == [{"id": "1"}]

    def test_increment_turn(self) -> None:
        ctx = AgentContext()
        ctx.increment_turn()
        ctx.increment_turn()
        assert ctx.turn_count == 2

    def test_add_tool_result(self) -> None:
        ctx = AgentContext()
        ctx.add_tool_result({"output": "done"})
        assert len(ctx.tool_results) == 1


class TestTurnLoopResult:
    def test_default(self) -> None:
        r = TurnLoopResult()
        assert r.text is None
        assert r.finished is False

    def test_successful(self) -> None:
        r = TurnLoopResult(text="Done", finished=True, turn_count=5)
        assert r.text == "Done"
        assert r.finished is True
        assert r.turn_count == 5
