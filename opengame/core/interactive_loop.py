"""InteractiveLoop — per-turn agent REPL for interactive game development.

Unlike TurnLoop (which runs to completion), InteractiveLoop executes
one LLM+tool round at a time, allowing user interaction between turns.

Supports:
- User injecting messages mid-conversation
- ask_user tool pausing for user input
- propose_design tool for design review
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from opengame.core.agent_context import AgentContext
from opengame.core.chat_compression_service import ChatCompressionService, CompressionStatus
from opengame.core.content_generator import ContentGenerator
from opengame.core.exceptions import UserQuestionRequested
from opengame.core.llm_client import BaseLlmClient, LlmResponse
from opengame.core.token_limit_checker import TokenLimitChecker
from opengame.core.tool_output_summarizer import ToolOutputSummarizer
from opengame.core.tool_output_truncator import ToolOutputTruncator
from opengame.core.tool_registry import ToolCall, ToolRegistry
from opengame.core.tool_scheduler import execute_all


class TurnOutcome(Enum):
    """Result of a single turn execution."""

    DONE = auto()           # LLM returned text, no tool calls — conversation complete
    TOOL_CALLS = auto()     # Tools were executed, more turns expected
    USER_QUESTION = auto()  # LLM called ask_user, waiting for user response
    TURN_LIMIT = auto()     # Max turns reached
    TOKEN_LIMIT = auto()    # Token limit exceeded


@dataclass
class TurnOutput:
    """Output from a single turn in the interactive loop."""

    outcome: TurnOutcome
    content: str | None = None          # LLM text response
    tool_results: list[Any] = field(default_factory=list)
    question: UserQuestionRequested | None = None  # Set when USER_QUESTION
    turn_count: int = 0


class InteractiveLoop:
    """Per-turn agent REPL for interactive game development.

    Usage:
        loop = InteractiveLoop(llm_client, tool_registry)
        loop.start(system_prompt)

        # Main interaction loop:
        while True:
            output = await loop.send_message(user_input)
            if output.outcome == TurnOutcome.DONE:
                print(output.content)
                break
            elif output.outcome == TurnOutcome.USER_QUESTION:
                answer = input(f"{output.question.question} > ")
                output = await loop.answer_question(answer)
                print(output.content)
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        tool_registry: ToolRegistry,
        max_turns: int = 50,
        token_limit: int = 128_000,
    ) -> None:
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.max_turns = max_turns

        self.content_generator = ContentGenerator(llm_client)
        self.chat_compressor = ChatCompressionService(
            llm_client=llm_client, token_limit=token_limit,
        )
        self.tool_summarizer = ToolOutputSummarizer(llm_client=llm_client)
        self.tool_truncator = ToolOutputTruncator(token_limit=token_limit)
        self.token_checker = TokenLimitChecker(model=llm_client.model, max_turns=max_turns)

        self._context: AgentContext | None = None
        self._pending_question: UserQuestionRequested | None = None
        self._pending_tool_calls: list[ToolCall] = []

    @property
    def context(self) -> AgentContext | None:
        """Current agent context (messages, todo_list, turn count)."""
        return self._context

    # --- Public API ---

    def start(self, system_prompt: str) -> None:
        """Initialize the conversation with a system prompt.

        Args:
            system_prompt: System prompt defining agent behavior.
        """
        self._context = AgentContext()
        self._context.add_message("system", system_prompt)
        self._pending_question = None
        self._pending_tool_calls = []

    async def send_message(self, user_message: str) -> TurnOutput:
        """Send a user message and run one or more turns until resolution.

        The loop keeps running turns while the LLM makes tool calls.
        It stops when the LLM returns a text response (DONE), when
        a turn/token limit is hit, or when the LLM calls ask_user.

        Args:
            user_message: The user's message.

        Returns:
            TurnOutput with outcome and content.
        """
        if self._context is None:
            raise RuntimeError("InteractiveLoop not started. Call start() first.")

        self._context.add_message("user", user_message)

        # Run turns until a stopping condition
        while self._context.turn_count < self.max_turns:
            self._context.turn_count += 1
            self.token_checker.increment_turn()

            # Guard: turn limit
            if self.token_checker.is_turn_limit_exceeded():
                return TurnOutput(outcome=TurnOutcome.TURN_LIMIT, turn_count=self._context.turn_count)

            # Guard: token limit
            if self.token_checker.is_token_limit_exceeded(self._context.messages):
                return TurnOutput(outcome=TurnOutcome.TOKEN_LIMIT, turn_count=self._context.turn_count)

            # Compression
            if self._approaching_token_limit():
                result = await self.chat_compressor.compress(self._context.messages)
                if result.status == CompressionStatus.COMPRESSED:
                    self._context.messages = result.new_history

            # Call LLM
            tools = self.tool_registry.get_tool_definitions()
            response = await self.content_generator.generate(
                messages=self._context.messages,
                tools=tools if tools else None,
                phase="interactive",
            )

            content, tool_calls = self._parse_response(response)

            # Append assistant message
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id, "type": "function",
                        "function": {"name": tc.name,
                                     "arguments": self._format_args(tc.arguments)},
                    }
                    for tc in tool_calls
                ]
            self._context.messages.append(assistant_msg)

            # No tool calls? Done.
            if not tool_calls:
                return TurnOutput(
                    outcome=TurnOutcome.DONE,
                    content=content,
                    turn_count=self._context.turn_count,
                )

            # Execute tools
            try:
                tool_results = await execute_all(tool_calls, self.tool_registry)
            except UserQuestionRequested as e:
                self._pending_question = e
                self._pending_tool_calls = tool_calls
                return TurnOutput(
                    outcome=TurnOutcome.USER_QUESTION,
                    content=content,
                    question=e,
                    turn_count=self._context.turn_count,
                )

            # Append tool results to context
            for tr in tool_results:
                output = tr.output if tr.success else f"ERROR: {tr.error}"
                summarized = await self.tool_summarizer.summarize(output)
                truncated = self.tool_truncator.truncate(summarized, self._context.messages)
                self._context.messages.append({
                    "role": "tool",
                    "tool_call_id": tr.call_id,
                    "content": truncated,
                })

        return TurnOutput(outcome=TurnOutcome.TURN_LIMIT, turn_count=self._context.turn_count)

    async def answer_question(self, answer: str) -> TurnOutput:
        """Provide the user's answer to a pending ask_user question.

        Injects the answer as the tool result for the ask_user call,
        then continues running turns.

        Args:
            answer: The user's response to the question.

        Returns:
            TurnOutput with outcome and content.
        """
        if self._pending_question is None:
            raise RuntimeError("No pending question to answer")

        # Set the user's response on the exception
        self._pending_question.response = answer

        # Construct tool result with user's answer
        tool_call_id = self._pending_tool_calls[0].id if self._pending_tool_calls else "call_user"
        self._context.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": answer,
        })

        self._pending_question = None
        self._pending_tool_calls = []

        # Continue running turns
        return await self._continue_turns()

    async def _continue_turns(self) -> TurnOutput:
        """Continue running turns after resolving a user question.

        Same as the inner loop of send_message() but without adding
        a new user message.
        """
        while self._context.turn_count < self.max_turns:
            self._context.turn_count += 1
            self.token_checker.increment_turn()

            if self.token_checker.is_turn_limit_exceeded():
                return TurnOutput(outcome=TurnOutcome.TURN_LIMIT, turn_count=self._context.turn_count)
            if self.token_checker.is_token_limit_exceeded(self._context.messages):
                return TurnOutput(outcome=TurnOutcome.TOKEN_LIMIT, turn_count=self._context.turn_count)

            if self._approaching_token_limit():
                result = await self.chat_compressor.compress(self._context.messages)
                if result.status == CompressionStatus.COMPRESSED:
                    self._context.messages = result.new_history

            tools = self.tool_registry.get_tool_definitions()
            response = await self.content_generator.generate(
                messages=self._context.messages,
                tools=tools if tools else None,
                phase="interactive",
            )

            content, tool_calls = self._parse_response(response)

            assistant_msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.name,
                                  "arguments": self._format_args(tc.arguments)}}
                    for tc in tool_calls
                ]
            self._context.messages.append(assistant_msg)

            if not tool_calls:
                return TurnOutput(outcome=TurnOutcome.DONE, content=content,
                                  turn_count=self._context.turn_count)

            try:
                tool_results = await execute_all(tool_calls, self.tool_registry)
            except UserQuestionRequested as e:
                self._pending_question = e
                self._pending_tool_calls = tool_calls
                return TurnOutput(outcome=TurnOutcome.USER_QUESTION, content=content,
                                  question=e, turn_count=self._context.turn_count)

            for tr in tool_results:
                output = tr.output if tr.success else f"ERROR: {tr.error}"
                summarized = await self.tool_summarizer.summarize(output)
                truncated = self.tool_truncator.truncate(summarized, self._context.messages)
                self._context.messages.append({
                    "role": "tool", "tool_call_id": tr.call_id, "content": truncated,
                })

        return TurnOutput(outcome=TurnOutcome.TURN_LIMIT, turn_count=self._context.turn_count)

    # --- Private helpers ---

    def _approaching_token_limit(self) -> bool:
        if not self._context:
            return False
        return self.token_checker.is_token_limit_exceeded(self._context.messages)

    @staticmethod
    def _parse_response(response: LlmResponse) -> tuple[str | None, list[ToolCall]]:
        return response.content, (response.tool_calls or [])

    @staticmethod
    def _format_args(args: dict[str, Any]) -> str:
        import json
        return json.dumps(args, ensure_ascii=False)
