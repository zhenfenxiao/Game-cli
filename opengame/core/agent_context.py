"""Agent context and turn loop result data classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    """Runtime context for a single agent conversation.

    Tracks messages, tool results, turn count, token usage,
    todo list state, and memory entries throughout a conversation.
    """

    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[Any] = field(default_factory=list)
    turn_count: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)
    todo_list: list[dict[str, Any]] = field(default_factory=list)
    memory: list[dict[str, Any]] = field(default_factory=list)

    def add_message(self, role: str, content: str | None = None, **kwargs: Any) -> None:
        """Append a message to the conversation history."""
        msg: dict[str, Any] = {"role": role}
        if content is not None:
            msg["content"] = content
        msg.update(kwargs)
        self.messages.append(msg)

    def add_tool_result(self, result: Any) -> None:
        """Record a tool execution result."""
        self.tool_results.append(result)

    def increment_turn(self) -> None:
        """Advance the turn counter."""
        self.turn_count += 1


@dataclass
class TurnLoopResult:
    """Result returned by TurnLoop.run().

    Contains the final output text, whether the conversation is finished,
    and usage statistics.
    """

    text: str | None = None
    finished: bool = False
    token_usage: dict[str, int] = field(default_factory=dict)
    turn_count: int = 0
