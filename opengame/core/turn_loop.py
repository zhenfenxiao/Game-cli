"""TurnLoop — the main agent conversation loop.

Orchestrates the complete agent REPL: sends messages to the LLM,
parses tool calls, executes tools in parallel, and applies all four
compression strategies to manage context window usage.

Compression strategy order (per-turn):
  1. TokenLimitChecker — hard turn/token ceilings (guards)
  2. ChatCompressionService — LLM summarization of older history (70% threshold)
  3. ToolOutputSummarizer — LLM condensing of large single outputs
  4. ToolOutputTruncator — hard character-based truncation
"""

from __future__ import annotations

from typing import Any

from opengame.core.agent_context import AgentContext, TurnLoopResult
from opengame.core.chat_compression_service import ChatCompressionService, CompressionStatus
from opengame.core.content_generator import ContentGenerator
from opengame.core.llm_client import BaseLlmClient, LlmResponse
from opengame.core.token_limit_checker import TokenLimitChecker
from opengame.core.tool_output_summarizer import ToolOutputSummarizer
from opengame.core.tool_output_truncator import ToolOutputTruncator
from opengame.core.tool_registry import ToolCall, ToolRegistry
from opengame.core.tool_scheduler import execute_all

# Default configuration
DEFAULT_MAX_TURNS = 100
DEFAULT_TOKEN_LIMIT = 128_000
DEFAULT_COMPRESSION_THRESHOLD = 0.70


class TurnLoop:
    """Main agent conversation loop with tool execution and compression.

    Usage:
        loop = TurnLoop(llm_client, tool_registry)
        result = await loop.run(
            system_prompt="You are a helpful assistant...",
            user_message="Build a Snake game",
        )
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        tool_registry: ToolRegistry,
        max_turns: int = DEFAULT_MAX_TURNS,
        token_limit: int = DEFAULT_TOKEN_LIMIT,
        compression_threshold: float = DEFAULT_COMPRESSION_THRESHOLD,
    ) -> None:
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.max_turns = max_turns
        self.token_limit = token_limit
        self.compression_threshold = compression_threshold

        # Content generator (thin wrapper around llm_client)
        self.content_generator = ContentGenerator(llm_client)

        # Initialize all 4 compression/lifecycle services
        self.chat_compressor = ChatCompressionService(
            llm_client=llm_client,
            token_limit=token_limit,
            threshold=compression_threshold,
        )
        self.tool_summarizer = ToolOutputSummarizer(llm_client=llm_client)
        self.tool_truncator = ToolOutputTruncator(token_limit=token_limit)
        self.token_checker = TokenLimitChecker(
            model=llm_client.model,
            max_turns=max_turns,
        )

        # Runtime context reference (set during run(), accessible by tools)
        self._context: AgentContext | None = None

    def set_tracer(self, tracer: Any) -> None:
        """Inject a TraceSession for recording LLM exchanges."""
        self.content_generator.set_tracer(tracer)

    @property
    def context(self) -> AgentContext | None:
        """Get the current agent context (accessible by tools for state injection)."""
        return self._context

    async def run(
        self,
        system_prompt: str,
        user_message: str,
        context: AgentContext | None = None,
    ) -> TurnLoopResult:
        """Run the agent conversation loop.

        Args:
            system_prompt: System prompt defining agent behavior and capabilities.
            user_message: The user's initial request.
            context: Optional pre-configured AgentContext (for subagent delegation).

        Returns:
            TurnLoopResult with final output, finish status, and usage stats.
        """
        # Initialize or reuse context
        self._context = context or AgentContext()

        # Start conversation with system prompt + user message
        self._context.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # Main conversation loop
        while self._context.turn_count < self.max_turns:
            self._context.turn_count += 1
            self.token_checker.increment_turn()

            # --- GUARD 1: Hard turn ceiling ---
            if self.token_checker.is_turn_limit_exceeded():
                return TurnLoopResult(
                    text="Maximum session turns reached. Please continue or restart.",
                    finished=False,
                    token_usage=self._context.token_usage,
                    turn_count=self._context.turn_count,
                )

            # --- GUARD 2: Hard token ceiling ---
            if self.token_checker.is_token_limit_exceeded(self._context.messages):
                return TurnLoopResult(
                    text="Session token limit exceeded. The conversation is too long. "
                    "Please start a new session or summarize progress manually.",
                    finished=False,
                    token_usage=self._context.token_usage,
                    turn_count=self._context.turn_count,
                )

            # --- STRATEGY 1: Compress conversation history ---
            if self._approaching_token_limit():
                result = await self.chat_compressor.compress(self._context.messages)
                if result.status == CompressionStatus.COMPRESSED:
                    self._context.messages = result.new_history
                    # Record in trace
                    if hasattr(self.content_generator, "_tracer") and self.content_generator._tracer:
                        self.content_generator._tracer.record_compression(
                            phase="implementation",
                            tokens_before=result.original_token_count,
                            tokens_after=result.summary_token_count,
                        )

            # --- Call LLM ---
            tools = self.tool_registry.get_tool_definitions()
            response = await self.content_generator.generate(
                messages=self._context.messages,
                tools=tools if tools else None,
                phase="implementation",
            )

            # --- Parse response ---
            content, tool_calls = self._parse_response(response)

            # Append assistant message to history
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": content or "",
            }
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": self._format_arguments(tc.arguments),
                        },
                    }
                    for tc in tool_calls
                ]
            self._context.messages.append(assistant_msg)

            # --- No tool calls? Conversation is complete ---
            if not tool_calls:
                return TurnLoopResult(
                    text=content,
                    finished=True,
                    token_usage=self._context.token_usage,
                    turn_count=self._context.turn_count,
                )

            # --- Execute tools in parallel ---
            tool_results = await execute_all(tool_calls, self.tool_registry)
            for tr in tool_results:
                self._context.add_tool_result(tr)

            # --- STRATEGY 2 + 3: Summarize and truncate tool outputs ---
            for tr in tool_results:
                output = tr.output if tr.success else f"ERROR: {tr.error}"

                # Summarize large outputs
                summarized = await self.tool_summarizer.summarize(output)

                # Truncate to fit remaining window
                truncated = self.tool_truncator.truncate(
                    summarized, self._context.messages,
                )

                self._context.messages.append({
                    "role": "tool",
                    "tool_call_id": tr.call_id,
                    "content": truncated,
                })

        # Max turns reached without finishing
        return TurnLoopResult(
            text="Maximum turns reached without completion.",
            finished=False,
            token_usage=self._context.token_usage,
            turn_count=self._context.turn_count,
        )

    # --- Private helpers ---

    def _approaching_token_limit(self) -> bool:
        """Check if conversation history is approaching the token limit.

        Uses the same estimation as TokenLimitChecker for consistency.

        Returns:
            True if compression should be attempted.
        """
        if not self._context:
            return False
        return self.token_checker.is_token_limit_exceeded(self._context.messages)

    @staticmethod
    def _parse_response(response: LlmResponse) -> tuple[str | None, list[ToolCall]]:
        """Extract text content and tool calls from an LLM response.

        Args:
            response: The LlmResponse from the LLM client.

        Returns:
            Tuple of (text_content, list_of_tool_calls).
        """
        content = response.content
        tool_calls = response.tool_calls if response.tool_calls else []
        return content, tool_calls

    @staticmethod
    def _format_arguments(arguments: dict[str, Any]) -> str:
        """Format tool call arguments as a JSON string.

        Args:
            arguments: Dict of argument name -> value.

        Returns:
            JSON string representation.
        """
        import json
        return json.dumps(arguments, ensure_ascii=False)
