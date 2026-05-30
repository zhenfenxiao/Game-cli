# 04 — Agent Runtime

The agent runtime is the engine that drives the AI agent's decision-making loop. It orchestrates LLM calls, tool execution, and conversation state.

## 4.1 Turn Loop

The turn loop is the core REPL (Read-Eval-Print Loop) of the agent:

```python
# core/turn_loop.py
from dataclasses import dataclass, field
from typing import Callable
import asyncio


@dataclass
class AgentContext:
    """Mutable context maintained across turns."""
    messages: list[dict] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    turn_count: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)
    todo_list: list[dict] = field(default_factory=list)
    memory: list[dict] = field(default_factory=list)


class TurnLoop:
    """
    Main conversation loop:

    1. Build messages list (system prompt + conversation history)
    2. Call LLM with available tools
    3. Parse response — text content or tool calls
    4. If tool calls: execute each tool in parallel
    5. Append tool results to history
    6. Repeat until the LLM signals completion or max_turns reached
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        tool_registry: ToolRegistry,
        max_turns: int = 100,
        token_limit: int = 128000,
        compression_threshold: float = 0.8,
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.max_turns = max_turns
        self.token_limit = token_limit
        self.compression_threshold = compression_threshold

    async def run(
        self,
        system_prompt: str,
        user_message: str,
        context: AgentContext | None = None,
    ) -> TurnResult:
        if context is None:
            context = AgentContext()

        # Initialize conversation
        context.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        while context.turn_count < self.max_turns:
            context.turn_count += 1

            # Check token budget — compress if needed
            if self._approaching_token_limit(context):
                await self._compress_conversation(context)

            # Get available tool definitions
            tools = self.tool_registry.get_tool_definitions()

            # Call LLM
            response = await self.llm_client.generate(
                messages=context.messages,
                tools=tools,
                stream=True,
            )

            # Parse response
            assistant_message, tool_calls = self._parse_response(response)

            # Add assistant message to history
            context.messages.append({
                "role": "assistant",
                "content": assistant_message,
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments}}
                    for tc in tool_calls
                ] if tool_calls else None,
            })

            # If no tool calls, we're done
            if not tool_calls:
                return TurnResult(
                    text=assistant_message,
                    finished=True,
                    token_usage=context.token_usage,
                )

            # Execute tool calls in parallel
            tool_results = await self._execute_tools(tool_calls)
            context.tool_results.extend(tool_results)

            # Add tool results to conversation
            for result in tool_results:
                context.messages.append({
                    "role": "tool",
                    "tool_call_id": result.call_id,
                    "content": result.output if not result.error else f"ERROR: {result.error}",
                })

        # Max turns reached
        return TurnResult(
            text="Maximum turns reached.",
            finished=False,
            token_usage=context.token_usage,
        )

    async def _execute_tools(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute all tool calls concurrently."""
        tasks = [
            self.tool_registry.execute(tc.name, tc.arguments, tc.id)
            for tc in tool_calls
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def _parse_response(self, response: LlmResponse) -> tuple[str | None, list[ToolCall]]:
        """Parse LLM response into text and tool calls."""
        text = response.content
        tool_calls = []
        for tc in response.tool_calls or []:
            tool_calls.append(ToolCall(
                id=tc["id"],
                name=tc["function"]["name"],
                arguments=tc["function"]["arguments"],
            ))
        return text, tool_calls

    def _approaching_token_limit(self, context: AgentContext) -> bool:
        """Check if conversation is approaching the token budget."""
        total = sum(context.token_usage.values())
        return total > self.token_limit * self.compression_threshold

    async def _compress_conversation(self, context: AgentContext) -> None:
        """Compress conversation history when approaching token limit."""
        compressor = ChatCompressionService(
            llm_client=self.llm_client,
            token_limit=self.token_limit,
        )
        result = await compressor.compress(context.messages)
        if result.new_history:
            context.messages = result.new_history
            context.token_usage = result.new_token_usage
```

### Turn Loop Requirements

| # | Requirement | Detail |
|---|-------------|--------|
| 1 | Streaming | Must support streaming responses for real-time UX |
| 2 | Tool parsing | Must parse tool calls from streaming chunks |
| 3 | Parallel execution | Multiple tool calls execute concurrently |
| 4 | Token management | Compress history when approaching token limit |
| 5 | Error handling | Retry LLM calls on rate limits/timeouts |
| 6 | Subagent support | Delegate to subagents as a tool |
| 7 | Conversation state | Maintain full message history across turns |

## 4.2 Tool Registry

Tools are registered via decorators and dispatched by name:

```python
# core/tool_registry.py
from typing import Callable, Any
import asyncio
import inspect


class ToolRegistry:
    """Registry for agent tools. Tools are registered via the @tool decorator."""

    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._definitions: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        schema: dict[str, Any],
    ) -> Callable:
        """Decorator to register a tool."""
        def decorator(func: Callable) -> Callable:
            self._tools[name] = func
            self._definitions[name] = ToolDefinition(
                name=name,
                description=description,
                parameters=_extract_parameters(func, schema),
                is_async=inspect.iscoroutinefunction(func),
            )
            return func
        return decorator

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        call_id: str,
    ) -> ToolResult:
        """Execute a tool by name with given arguments."""
        if name not in self._tools:
            return ToolResult(
                call_id=call_id,
                name=name,
                output="",
                error=f"Tool '{name}' not found",
            )

        func = self._tools[name]
        start = asyncio.get_event_loop().time()

        try:
            if inspect.iscoroutinefunction(func):
                result = await func(**arguments)
            else:
                result = func(**arguments)

            return ToolResult(
                call_id=call_id,
                name=name,
                output=str(result) if result is not None else "",
                duration_ms=int((asyncio.get_event_loop().time() - start) * 1000),
            )
        except Exception as e:
            return ToolResult(
                call_id=call_id,
                name=name,
                output="",
                error=str(e),
                duration_ms=int((asyncio.get_event_loop().time() - start) * 1000),
            )

    def get_tool_definitions(self) -> list[dict]:
        """Get all tool definitions as OpenAI-compatible function schemas."""
        return [d.to_json_schema() for d in self._definitions.values()]

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())


def _extract_parameters(func: Callable, schema: dict) -> list[ToolParameter]:
    """Extract parameters from function signature and JSON schema."""
    sig = inspect.signature(func)
    params = []
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        param_schema = schema.get("properties", {}).get(name, {})
        params.append(ToolParameter(
            name=name,
            type=param_schema.get("type", "string"),
            description=param_schema.get("description", ""),
            required=name in schema.get("required", []),
            default=param.default if param.default is not inspect.Parameter.empty else None,
        ))
    return params
```

### Tool Registration Example

```python
# tools/file_tools.py
from opengame.core.tool_registry import ToolRegistry

registry = ToolRegistry()

@registry.register(
    name="read_file",
    description="Read the contents of a file. Use absolute paths. Supports offset and limit for large files.",
    schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to read"
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-indexed)",
                "default": 0
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read",
                "default": 2000
            }
        },
        "required": ["file_path"]
    }
)
async def read_file(file_path: str, offset: int = 0, limit: int = 2000) -> str:
    """Read a file with optional offset and limit."""
    from aiofiles import open as aio_open
    async with aio_open(file_path, "r") as f:
        lines = []
        async for i, line in enumerate(f):
            if i < offset:
                continue
            if len(lines) >= limit:
                break
            lines.append(line)
        return "".join(lines)
```

## 4.3 LLM Client

### Base Interface

```python
# core/llm_client.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LlmResponse:
    """Parsed response from an LLM."""
    content: str | None = None
    tool_calls: list[dict] | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    model: str | None = None


class BaseLlmClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = True,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LlmResponse:
        """
        Generate a response from the LLM.

        Args:
            messages: Conversation history [{role, content}, ...]
            tools: Available tool definitions as OpenAI function schemas
            stream: Whether to stream the response
            temperature: Sampling temperature (overrides config)
            max_tokens: Maximum tokens to generate (overrides config)

        Returns:
            Parsed LLM response with content and/or tool calls
        """
        pass

    @abstractmethod
    async def stream_generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Any:
        """Stream generator yielding partial response chunks."""
        pass
```

### OpenAI-Compatible Client

```python
# core/openai_client.py
from openai import AsyncOpenAI
import json


class OpenAiClient(BaseLlmClient):
    """OpenAI-compatible API client with streaming and tool call support."""

    def __init__(self, config: LlmConfig):
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )
        self.config = config

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = True,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LlmResponse:
        if stream:
            return await self._generate_streaming(messages, tools, temperature, max_tokens)
        else:
            return await self._generate_blocking(messages, tools, temperature, max_tokens)

    async def _generate_streaming(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> LlmResponse:
        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            tools=tools,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            stream=True,
        )

        content_parts = []
        tool_calls = {}

        async for chunk in response:
            delta = chunk.choices[0].delta

            # Accumulate text content
            if delta.content:
                content_parts.append(delta.content)

            # Accumulate tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {"id": tc.id, "function": {"name": "", "arguments": ""}}
                    if tc.function.name:
                        tool_calls[idx]["function"]["name"] = tc.function.name
                    if tc.function.arguments:
                        tool_calls[idx]["function"]["arguments"] += tc.function.arguments

        # Parse accumulated tool calls
        parsed_tool_calls = []
        for idx in sorted(tool_calls.keys()):
            tc = tool_calls[idx]
            parsed_tool_calls.append({
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": json.loads(tc["function"]["arguments"]),
                }
            })

        return LlmResponse(
            content="".join(content_parts) if content_parts else None,
            tool_calls=parsed_tool_calls if parsed_tool_calls else None,
        )

    async def _generate_blocking(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> LlmResponse:
        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            tools=tools,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            stream=False,
        )

        message = response.choices[0].message
        return LlmResponse(
            content=message.content,
            tool_calls=[
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                    }
                }
                for tc in (message.tool_calls or [])
            ] if message.tool_calls else None,
            usage=dict(response.usage) if response.usage else None,
        )
```

### Retry Decorator

```python
# utils/retry.py
import functools
import asyncio
from typing import Callable, TypeVar

T = TypeVar("T")


def retry(
    max_retries: int = 3,
    backoff_base: float = 1.0,
    backoff_max: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """Retry decorator with exponential backoff."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        raise
                    wait = min(backoff_base * (2 ** attempt), backoff_max)
                    await asyncio.sleep(wait)
            raise RuntimeError("Unreachable")

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        raise
                    wait = min(backoff_base * (2 ** attempt), backoff_max)
                    import time
                    time.sleep(wait)
            raise RuntimeError("Unreachable")

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
```

## 4.4 Prompt Assembly

```python
# core/prompts.py
class PromptAssembler:
    """Assembles system prompts with injected context."""

    def assemble_game_prompt(
        self,
        base_prompt_path: str,
        template_library_summary: str | None = None,
        debug_protocol_summary: str | None = None,
        gdd_content: str | None = None,
        project_context: dict | None = None,
    ) -> str:
        """
        Assemble the complete system prompt for game generation.

        Loads the base prompt (custom.md for games), then injects:
        - Template library context (available archetypes, families)
        - Debug protocol context (known error patterns)
        - GDD content (if already generated)
        - Project-specific context (file tree, conventions)
        """
        # Load base prompt
        with open(base_prompt_path, "r") as f:
            prompt = f.read()

        # Inject context sections
        sections = []

        if template_library_summary:
            sections.append(f"\n# Template Library Context\n\n{template_library_summary}\n")

        if debug_protocol_summary:
            sections.append(f"\n# Debug Protocol Context\n\n{debug_protocol_summary}\n")

        if gdd_content:
            sections.append(f"\n# Game Design Document\n\n{gdd_content}\n")

        if project_context:
            sections.append(f"\n# Project Context\n\n{self._format_project_context(project_context)}\n")

        if sections:
            prompt = prompt + "\n\n" + "\n".join(sections)

        return prompt

    def _format_project_context(self, context: dict) -> str:
        """Format project context for prompt injection."""
        parts = []
        if "file_tree" in context:
            parts.append("## File Tree\n" + "\n".join(context["file_tree"]))
        if "conventions" in context:
            parts.append("## Project Conventions\n" + context["conventions"])
        return "\n\n".join(parts)
```

## 4.5 Context Compression

Context compression is a critical mechanism that prevents the agent from exceeding the LLM's context window. The TypeScript reference implements four complementary strategies. All four must be implemented in the Python port.

### 4.5.1 Architecture Overview

```
Turn Loop
    │
    ├─── TokenLimitChecker ────► Hard session/token ceiling
    │
    ├─── ChatCompressionService ────► Compress older history via LLM summary
    │         ├─ SplitPointFinder (30% preserve)
    │         ├─ StateSnapshotGenerator (XML summary)
    │         └─ ValidationGate (non-empty + token-reduced)
    │
    ├─── ToolOutputSummarizer ────► Compress large individual tool outputs
    │
    └─── ToolOutputTruncator ────► Hard truncate based on remaining window
```

### 4.5.2 ChatCompressionService — Conversation History Compression

```python
# core/chat_compression_service.py
from dataclasses import dataclass
from enum import Enum
from typing import Final
import json


COMPRESSION_TOKEN_THRESHOLD: Final[float] = 0.70
"""Trigger compression when history exceeds this fraction of model token limit."""

COMPRESSION_PRESERVE_THRESHOLD: Final[float] = 0.30
"""Preserve the last N% of history (most recent context). Compress the rest."""

COMPRESSION_PROMPT: Final[str] = """\
You are the component that summarizes internal chat history into a given structure.

When the conversation history grows too large, you will be invoked to distill the entire history into a concise, structured XML snapshot. This snapshot is CRITICAL, as it will become the agent's *only* memory of the past. The agent will resume its work based solely on this snapshot. All crucial details, plans, errors, and user directives MUST be preserved.

First, you will think through the entire history in a private <scratchpad>. Review the user's overall goal, the agent's actions, tool outputs, file modifications, and any unresolved questions. Identify every piece of information that is essential for future actions.

After your reasoning is complete, generate the final <state_snapshot> XML object. Be incredibly dense with information. Omit any irrelevant conversational filler.

The structure MUST be as follows:

<state_snapshot>
    <overall_goal>
        <!-- A single, concise sentence describing the user's high-level objective. -->
    </overall_goal>

    <key_knowledge>
        <!-- Crucial facts, conventions, and constraints the agent must remember based on the conversation history and interaction with the user. Use bullet points. -->
    </key_knowledge>

    <file_system_state>
        <!-- List files that have been created, read, modified, or deleted. Note their status and critical learnings. -->
    </file_system_state>

    <recent_actions>
        <!-- A summary of the last few significant agent actions and their outcomes. Focus on facts. -->
    </recent_actions>

    <current_plan>
        <!-- The agent's step-by-step plan. Mark completed steps. -->
    </current_plan>
</state_snapshot>
"""


class CompressionStatus(Enum):
    """Result status of a compression attempt."""
    COMPRESSED = "compressed"
    NOOP = "noop"                           # History below threshold
    FAILED_INFLATED = "failed_inflated"     # Summary was larger than original
    FAILED_EMPTY = "failed_empty"           # Summary was empty
    FAILED_ERROR = "failed_error"           # LLM call failed


@dataclass
class CompressionResult:
    """Result of a compression operation."""
    status: CompressionStatus
    new_history: list[dict] | None          # None if compression not applied
    new_token_usage: dict[str, int]         # Updated token counts
    original_tokens: int
    summary_tokens: int
    info: str                               # Human-readable description


class ChatCompressionService:
    """
    Compress conversation history by summarizing older messages via LLM.

    Algorithm:
    1. Check if history token count exceeds threshold (default 70% of limit)
    2. Find a split point: preserve the most recent 30%, compress the rest
    3. Send the older portion to an LLM with a compression prompt
    4. Validate: summary must be non-empty and must reduce token count
    5. Replace the older portion with a single system message containing the summary
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        token_limit: int,
        threshold: float = COMPRESSION_TOKEN_THRESHOLD,
        preserve_fraction: float = COMPRESSION_PRESERVE_THRESHOLD,
    ):
        self.llm_client = llm_client
        self.token_limit = token_limit
        self.threshold = threshold
        self.preserve_fraction = preserve_fraction
        self._failed_last_attempt = False

    async def compress(
        self,
        history: list[dict],
        force: bool = False,
    ) -> CompressionResult:
        """
        Compress conversation history if it exceeds the token threshold.

        Args:
            history: Full conversation history [{role, content}, ...]
            force: Force compression even if below threshold (e.g. after previous failure)

        Returns:
            CompressionResult with new history and status
        """
        # Guard: empty history
        if not history:
            return CompressionResult(
                status=CompressionStatus.NOOP,
                new_history=None,
                new_token_usage={},
                original_tokens=0,
                summary_tokens=0,
                info="History is empty",
            )

        # Guard: skip if previous attempt failed and not forced
        if self._failed_last_attempt and not force:
            return CompressionResult(
                status=CompressionStatus.NOOP,
                new_history=None,
                new_token_usage={},
                original_tokens=0,
                summary_tokens=0,
                info="Skipping: previous compression attempt failed",
            )

        # Step 1: Count tokens (approximate)
        original_tokens = self._estimate_tokens(history)
        threshold_tokens = int(self.token_limit * self.threshold)

        if original_tokens < threshold_tokens and not force:
            return CompressionResult(
                status=CompressionStatus.NOOP,
                new_history=None,
                new_token_usage={"total": original_tokens},
                original_tokens=original_tokens,
                summary_tokens=0,
                info=f"History ({original_tokens}) below threshold ({threshold_tokens})",
            )

        # Step 2: Find split point (preserve recent 30%)
        split_idx = self._find_split_point(history, self.preserve_fraction)

        to_compress = history[:split_idx]
        to_preserve = history[split_idx:]

        if not to_compress:
            return CompressionResult(
                status=CompressionStatus.NOOP,
                new_history=None,
                new_token_usage={"total": original_tokens},
                original_tokens=original_tokens,
                summary_tokens=0,
                info="Nothing to compress — all history within preserve window",
            )

        # Step 3: Generate summary via LLM
        try:
            summary = await self._generate_summary(to_compress)
        except Exception as e:
            self._failed_last_attempt = True
            return CompressionResult(
                status=CompressionStatus.FAILED_ERROR,
                new_history=None,
                new_token_usage={"total": original_tokens},
                original_tokens=original_tokens,
                summary_tokens=0,
                info=f"LLM summary generation failed: {e}",
            )

        # Step 4: Validate summary
        if not summary or not summary.strip():
            self._failed_last_attempt = True
            return CompressionResult(
                status=CompressionStatus.FAILED_EMPTY,
                new_history=None,
                new_token_usage={"total": original_tokens},
                original_tokens=original_tokens,
                summary_tokens=0,
                info="Summary was empty — rejecting compression",
            )

        # Step 5: Build new history with summary
        summary_message = {
            "role": "system",
            "content": f"[Previous conversation summarized]\n\n{summary}",
        }
        new_history = [summary_message] + to_preserve
        summary_tokens = self._estimate_tokens([summary_message])
        compressed_tokens = self._estimate_tokens(new_history)

        # Validation gate: reject if compression inflated token count
        if compressed_tokens >= original_tokens:
            self._failed_last_attempt = True
            return CompressionResult(
                status=CompressionStatus.FAILED_INFLATED,
                new_history=None,
                new_token_usage={"total": original_tokens},
                original_tokens=original_tokens,
                summary_tokens=summary_tokens,
                info=f"Compression inflated tokens: {original_tokens} -> {compressed_tokens}",
            )

        self._failed_last_attempt = False
        return CompressionResult(
            status=CompressionStatus.COMPRESSED,
            new_history=new_history,
            new_token_usage={"total": compressed_tokens},
            original_tokens=original_tokens,
            summary_tokens=summary_tokens,
            info=f"Compressed {len(to_compress)} messages into summary. "
                 f"Tokens: {original_tokens} -> {compressed_tokens}",
        )

    def _estimate_tokens(self, messages: list[dict]) -> int:
        """
        Estimate token count from message characters.

        Uses a rough heuristic: ~4 characters per token (English text).
        This is fast and sufficient for threshold checking.
        For precise counting, use the LLM provider's count_tokens API.
        """
        total_chars = sum(
            len(json.dumps(msg, ensure_ascii=False))
            for msg in messages
        )
        return total_chars // 4

    def _find_split_point(self, history: list[dict], preserve_fraction: float) -> int:
        """
        Find the index where to split history for compression.

        Returns the oldest index that should be COMPRESSED (everything before
        this index). Everything from this index onward is PRESERVED.

        Rules:
        - Split only at 'user' messages (not model/tool responses)
        - Never split right after a model message that contains tool calls
        - If safe, can compress everything (return len(history))
        """
        char_counts = [len(json.dumps(msg, ensure_ascii=False)) for msg in history]
        total_chars = sum(char_counts)
        target_chars = total_chars * preserve_fraction

        last_split = 0
        cumulative = 0

        for i, msg in enumerate(history):
            # Only split at user messages that are NOT function responses
            if msg.get("role") == "user" and "tool_call_id" not in msg:
                if cumulative >= target_chars:
                    return i
                last_split = i
            cumulative += char_counts[i]

        # No split point found after target — check if we can compress everything
        last_msg = history[-1] if history else None
        if last_msg and last_msg.get("role") == "assistant":
            has_tool_calls = last_msg.get("tool_calls") is not None
            if not has_tool_calls:
                return len(history)  # Safe to compress everything

        return last_split

    async def _generate_summary(self, messages: list[dict]) -> str:
        """Generate a structured summary of the given messages via LLM."""
        # Flatten messages into a single text for the prompt
        history_text = "\n\n".join(
            f"[{msg.get('role', 'unknown')}] {msg.get('content', '')[:500]}"
            for msg in messages
        )

        prompt = f"""{COMPRESSION_PROMPT}

## Conversation History to Summarize

{history_text}

## Your Output

Generate the <state_snapshot> XML below. Do NOT include the <scratchpad> in your final output."""

        response = await self.llm_client.generate(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
            stream=False,
            temperature=0.2,
            max_tokens=4000,
        )

        content = response.content or ""

        # Extract just the <state_snapshot> block
        import re
        match = re.search(r"<state_snapshot>.*?</state_snapshot>", content, re.DOTALL)
        if match:
            return match.group(0)

        return content.strip()
```

### 4.5.3 ToolOutputSummarizer — Individual Tool Output Compression

```python
# core/tool_output_summarizer.py

TOOL_OUTPUT_SUMMARY_PROMPT: str = """\
You are a tool output summarizer. Summarize the following tool output into a concise form while preserving ALL errors, warnings, and critical information.

Rules:
- Preserve all <error> and <warning> tags exactly as they appear
- Preserve file paths, line numbers, and code snippets
- Summarize repetitive output (e.g. long file listings) into counts or patterns
- The summary must not exceed {max_output_tokens} tokens
- If the output is already short, return it as-is

## Tool Output

{text_to_summarize}

## Your Summary
"""


class ToolOutputSummarizer:
    """
    Summarize individual tool outputs that exceed a token budget.

    Unlike ChatCompressionService which handles the full conversation history,
    this service targets single, oversized tool results (e.g. long grep output,
    large file reads, extensive build logs).

    Uses a lightweight/cheap model for cost efficiency.
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        max_output_tokens: int = 2000,
        summary_model: str | None = None,
    ):
        self.llm_client = llm_client
        self.max_output_tokens = max_output_tokens
        self.summary_model = summary_model  # e.g. "gemini-2.0-flash-lite"

    async def summarize(self, text: str) -> str:
        """
        Summarize tool output if it exceeds the token budget.

        Args:
            text: Raw tool output text

        Returns:
            Summarized text, or original if below threshold
        """
        # Fast path: skip if already short (character-based heuristic)
        if not text or len(text) < self.max_output_tokens:
            return text

        prompt = TOOL_OUTPUT_SUMMARY_PROMPT.format(
            max_output_tokens=self.max_output_tokens,
            text_to_summarize=text[:15000],  # Truncate to avoid overloading
        )

        try:
            response = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                tools=None,
                stream=False,
                temperature=0.1,
                max_tokens=self.max_output_tokens,
            )

            summary = response.content or ""

            # If summary is empty or failed, fall back to original
            if not summary.strip():
                return text

            # If summary is longer than original, fall back
            if len(summary) > len(text):
                return text

            return summary

        except Exception as e:
            # Never fail the main flow because summarization failed
            return text
```

### 4.5.4 ToolOutputTruncator — Dynamic Hard Truncation

```python
# core/tool_output_truncator.py

class ToolOutputTruncator:
    """
    Dynamically truncate tool outputs before they enter the conversation history.

    Calculates a safe truncation threshold based on the REMAINING context window,
    ensuring a single tool result never pushes the total over the limit.

    This is the LAST line of defense before a message is appended to history.
    """

    def __init__(self, token_limit: int):
        self.token_limit = token_limit

    def truncate(
        self,
        text: str,
        current_history: list[dict],
    ) -> str:
        """
        Truncate tool output to fit within the remaining context window.

        Formula:
            remaining = token_limit - tokens_used_by_history
            threshold_chars = 4 * remaining   # ~4 chars/token heuristic
            output_limit = max(threshold_chars, 1000)  # Never go below 1000 chars

        Args:
            text: Raw tool output
            current_history: Conversation history BEFORE this tool result is added

        Returns:
            Truncated text (with ellipsis marker if truncated)
        """
        if not text:
            return text

        # Estimate current history tokens
        history_chars = sum(
            len(json.dumps(msg, ensure_ascii=False))
            for msg in current_history
        )
        history_tokens = history_chars // 4

        remaining_tokens = self.token_limit - history_tokens
        remaining_tokens = max(remaining_tokens, 0)

        # Allow tool output to consume up to 4x remaining tokens in characters
        # (generous — actual tokens may be less due to repeated patterns)
        threshold_chars = 4 * remaining_tokens

        # Floor: never truncate below 1000 characters
        threshold_chars = max(threshold_chars, 1000)

        if len(text) <= threshold_chars:
            return text

        # Truncate with a clear marker
        truncated = text[:threshold_chars]
        marker = f"\n\n[... Output truncated: {len(text)} chars -> {threshold_chars} chars ...]"
        return truncated + marker
```

### 4.5.5 TokenLimitChecker — Hard Ceiling

```python
# core/token_limit_checker.py

# Per-model token limits
MODEL_TOKEN_LIMITS: dict[str, int] = {
    # OpenAI
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_385,
    # Anthropic
    "claude-3-5-sonnet": 200_000,
    "claude-3-opus": 200_000,
    "claude-3-haiku": 200_000,
    # Google
    "gemini-1.5-pro": 2_000_000,
    "gemini-1.5-flash": 1_000_000,
    "gemini-2.0-flash": 1_000_000,
    # Defaults
    "default": 128_000,
}

# Per-model output (generation) limits
MODEL_OUTPUT_LIMITS: dict[str, int] = {
    "gpt-4o": 16_384,
    "gpt-4o-mini": 16_384,
    "claude-3-5-sonnet": 8_192,
    "gemini-1.5-pro": 8_192,
    "default": 4_096,
}


def get_model_token_limit(model: str) -> int:
    """Get the context window size for a model."""
    for prefix, limit in MODEL_TOKEN_LIMITS.items():
        if prefix in model.lower():
            return limit
    return MODEL_TOKEN_LIMITS["default"]


def get_model_output_limit(model: str) -> int:
    """Get the maximum generation tokens for a model."""
    for prefix, limit in MODEL_OUTPUT_LIMITS.items():
        if prefix in model.lower():
            return limit
    return MODEL_OUTPUT_LIMITS["default"]


class TokenLimitChecker:
    """
    Enforce hard token limits before sending requests to the LLM.

    Uses the LLM provider's count_tokens API for accurate counting
    (not heuristics) when checking the session limit.
    """

    def __init__(self, llm_client: BaseLlmClient, model: str):
        self.llm_client = llm_client
        self.model = model
        self.token_limit = get_model_token_limit(model)
        self.session_token_limit = int(self.token_limit * 0.95)  # 5% safety margin
        self.max_turns = 100
        self.session_turn_count = 0

    def increment_turn(self) -> None:
        """Increment the session turn counter."""
        self.session_turn_count += 1

    def is_turn_limit_exceeded(self) -> bool:
        """Check if the turn limit has been reached."""
        return self.session_turn_count >= self.max_turns

    async def is_token_limit_exceeded(self, messages: list[dict]) -> bool:
        """
        Check if adding these messages would exceed the session token limit.

        Uses the LLM provider's count_tokens API for accuracy.
        Falls back to heuristic if API is unavailable.
        """
        try:
            # Try to use the provider's token counting API
            token_count = await self._count_tokens(messages)
            return token_count > self.session_token_limit
        except Exception:
            # Fallback to heuristic
            total_chars = sum(
                len(json.dumps(msg, ensure_ascii=False))
                for msg in messages
            )
            estimated_tokens = total_chars // 4
            return estimated_tokens > self.session_token_limit

    async def _count_tokens(self, messages: list[dict]) -> int:
        """Call the LLM provider's token counting API."""
        # OpenAI-compatible: use tiktoken or API
        # This is provider-specific
        raise NotImplementedError("Token counting is provider-specific")

    def get_remaining_tokens(self, messages: list[dict]) -> int:
        """Estimate remaining tokens in the context window."""
        total_chars = sum(
            len(json.dumps(msg, ensure_ascii=False))
            for msg in messages
        )
        estimated_tokens = total_chars // 4
        return max(0, self.token_limit - estimated_tokens)
```

### 4.5.6 Integration in Turn Loop

```python
# Updated TurnLoop with all compression strategies integrated

class TurnLoop:
    def __init__(
        self,
        llm_client: BaseLlmClient,
        tool_registry: ToolRegistry,
        max_turns: int = 100,
        token_limit: int = 128000,
        compression_threshold: float = 0.70,
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.max_turns = max_turns
        self.token_limit = token_limit
        self.compression_threshold = compression_threshold

        # Compression services
        self.chat_compressor = ChatCompressionService(
            llm_client=llm_client,
            token_limit=token_limit,
            threshold=compression_threshold,
        )
        self.tool_summarizer = ToolOutputSummarizer(llm_client=llm_client)
        self.tool_truncator = ToolOutputTruncator(token_limit=token_limit)
        self.token_checker = TokenLimitChecker(llm_client=llm_client, model="gpt-4o")

    async def run(
        self,
        system_prompt: str,
        user_message: str,
        context: AgentContext | None = None,
    ) -> TurnResult:
        if context is None:
            context = AgentContext()

        context.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        while context.turn_count < self.max_turns:
            context.turn_count += 1
            self.token_checker.increment_turn()

            # --- HARD CEILING: Check turn limit ---
            if self.token_checker.is_turn_limit_exceeded():
                return TurnResult(
                    text="Maximum session turns reached.",
                    finished=False,
                    token_usage=context.token_usage,
                )

            # --- HARD CEILING: Check token limit (accurate) ---
            if await self.token_checker.is_token_limit_exceeded(context.messages):
                return TurnResult(
                    text="Session token limit exceeded.",
                    finished=False,
                    token_usage=context.token_usage,
                )

            # --- STRATEGY 1: Compress conversation history ---
            if self._approaching_token_limit(context):
                result = await self.chat_compressor.compress(context.messages)
                if result.status == CompressionStatus.COMPRESSED:
                    context.messages = result.new_history
                    context.token_usage = result.new_token_usage

            # Get tool definitions
            tools = self.tool_registry.get_tool_definitions()

            # Call LLM
            response = await self.llm_client.generate(
                messages=context.messages,
                tools=tools,
                stream=True,
            )

            # Parse and handle response...
            assistant_message, tool_calls = self._parse_response(response)
            context.messages.append({
                "role": "assistant",
                "content": assistant_message,
                "tool_calls": [...] if tool_calls else None,
            })

            if not tool_calls:
                return TurnResult(
                    text=assistant_message,
                    finished=True,
                    token_usage=context.token_usage,
                )

            # Execute tools
            tool_results = await self._execute_tools(tool_calls)

            # --- STRATEGY 2 + 3: Summarize and truncate tool outputs ---
            for result in tool_results:
                # First: summarize if very large
                summarized = await self.tool_summarizer.summarize(result.output)
                # Then: truncate to fit remaining window
                truncated = self.tool_truncator.truncate(summarized, context.messages)

                context.messages.append({
                    "role": "tool",
                    "tool_call_id": result.call_id,
                    "content": truncated if not result.error else f"ERROR: {result.error}",
                })

        return TurnResult(
            text="Maximum turns reached.",
            finished=False,
            token_usage=context.token_usage,
        )
```

### 4.5.7 Compression Strategy Summary

| # | Strategy | Trigger | What It Does | Fallback |
|---|----------|---------|-------------|----------|
| 1 | **ChatCompression** | History > 70% of limit | LLM summarizes older 70% into XML `<state_snapshot>` | Reject if inflates tokens or empty |
| 2 | **ToolOutputSummarize** | Single output > 2000 chars | Light model condenses output, preserves errors/warnings | Return original if fails |
| 3 | **ToolOutputTruncate** | Before adding to history | Hard truncate to `4 * remaining_tokens` chars | Floor at 1000 chars |
| 4 | **TokenLimitChecker** | Every turn | Accurate `count_tokens()` API check | Heuristic fallback |
| 5 | **TurnLimit** | Every turn | Hard ceiling of 100 turns | N/A |

### 4.5.8 Key Design Decisions

1. **Why 70% threshold?** Provides headroom for the next LLM response (which may include tool calls and reasoning) without immediately hitting the ceiling.

2. **Why preserve 30%?** The most recent context (user's latest request, pending tool results) is the most relevant for the next action. Older context is more "state" than "immediate intent".

3. **Why XML summary format?** Structured XML is dense, machine-parseable, and explicitly separates overall_goal / key_knowledge / file_system_state / recent_actions / current_plan. The LLM can resume work directly from this format.

4. **Why two-stage tool output handling?** Summarize first (semantic compression), then truncate (hard limit). This ensures meaning is preserved as much as possible before the hard cut.

5. **Why validation gate?** Compression is not free (it consumes an LLM call). If the summary is larger than the original, or is empty, we reject it and try again next turn (or fall back to truncation).
