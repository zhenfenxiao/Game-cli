"""ChatCompressionService — conversation history compression.

When the conversation history exceeds 70% of the model's token limit,
this service summarizes the older portion into a structured XML
<state_snapshot> that preserves project context while freeing up
context window space for the next turn.

Strategy:
1. Check if estimated tokens exceed threshold (70% of limit)
2. Find a safe split point (at user message boundaries, never after
   assistant messages with pending tool calls)
3. Send older messages to LLM for summarization into XML
4. Validate the summary (non-empty, not inflated)
5. Replace older portion with the summary message
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from opengame.core.llm_client import BaseLlmClient

# Compression triggers when history exceeds this fraction of the token limit
COMPRESSION_TOKEN_THRESHOLD = 0.70

# Keep this fraction of the most recent history uncompressed
COMPRESSION_PRESERVE_THRESHOLD = 0.30

# Maximum tokens for the summary generation
COMPRESSION_SUMMARY_MAX_TOKENS = 4000

# Rough heuristic: ~4 characters per token
CHARS_PER_TOKEN = 4

COMPRESSION_PROMPT: str = """\
You are a conversation archivist. Your job is to create a structured XML state snapshot that captures the essential context from a conversation history. The snapshot will replace the older messages, allowing the agent to continue working seamlessly.

Generate the following XML structure:

<state_snapshot>
<overall_goal>
The user's current overall goal — what are they trying to accomplish? Be specific.
</overall_goal>

<key_knowledge>
Critical facts the agent has learned: file locations, configurations, API patterns, architecture decisions, constraints. Be concise but complete.
</key_knowledge>

<file_system_state>
Key files that exist, their purposes, and important recent modifications. Include file paths.
</file_system_state>

<recent_actions>
What has been done so far, in chronological order. Include tool calls and their results (especially errors or anomalies).
</recent_actions>

<current_plan>
What is the agent currently working on? What are the immediate next steps and open tasks?
</current_plan>
</state_snapshot>

Rules:
- Be concise. The snapshot must be shorter than the original history.
- Preserve ALL error messages, file paths, and code snippets.
- Focus on information needed to CONTINUE work, not a full transcript.
- Do NOT include conversational fluff or repeated information.
"""


class CompressionStatus(Enum):
    """Status of a compression attempt."""

    COMPRESSED = "compressed"       # Successfully compressed
    NOOP = "noop"                   # No compression needed (below threshold)
    FAILED_INFLATED = "inflated"    # Summary was larger than original (rejected)
    FAILED_EMPTY = "empty"          # Summary was empty (rejected)
    FAILED_ERROR = "error"          # Exception during compression (rejected)


@dataclass
class CompressionResult:
    """Result of a compression attempt."""

    status: CompressionStatus
    new_history: list[dict[str, Any]] = field(default_factory=list)
    original_token_count: int = 0
    summary_token_count: int = 0
    info: str = ""


class ChatCompressionService:
    """Compress conversation history via LLM summarization.

    Replaces the older ~70% of conversation history with a single
    XML summary message, preserving the most recent ~30% for
    immediate context.
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        token_limit: int,
        threshold: float = COMPRESSION_TOKEN_THRESHOLD,
        preserve_fraction: float = COMPRESSION_PRESERVE_THRESHOLD,
    ) -> None:
        self.llm_client = llm_client
        self.token_limit = token_limit
        self.threshold = threshold
        self.preserve_fraction = preserve_fraction
        self._last_failed: bool = False

    async def compress(
        self,
        history: list[dict[str, Any]],
        force: bool = False,
    ) -> CompressionResult:
        """Attempt to compress conversation history.

        Args:
            history: Current conversation messages.
            force: If True, attempt compression even if previous attempt failed.

        Returns:
            CompressionResult with status and (if COMPRESSED) new history.
        """
        # Guard: empty history
        if not history:
            return CompressionResult(
                status=CompressionStatus.NOOP,
                info="Empty history, nothing to compress",
            )

        # Guard: previous failure (unless forced)
        if self._last_failed and not force:
            return CompressionResult(
                status=CompressionStatus.NOOP,
                info="Skipping — previous compression attempt failed",
            )

        # Step 1: Check token threshold
        original_tokens = self._estimate_tokens(history)
        threshold_tokens = int(self.token_limit * self.threshold)

        if original_tokens < threshold_tokens:
            return CompressionResult(
                status=CompressionStatus.NOOP,
                info=f"Below threshold ({original_tokens} < {threshold_tokens})",
            )

        # Step 2: Find safe split point
        split_idx = self._find_split_point(history, self.preserve_fraction)
        if split_idx <= 0:
            return CompressionResult(
                status=CompressionStatus.NOOP,
                info="No safe split point found",
            )

        to_summarize = history[:split_idx]
        to_preserve = history[split_idx:]

        # Step 3: Generate summary
        try:
            summary = await self._generate_summary(to_summarize)
        except Exception as e:
            self._last_failed = True
            return CompressionResult(
                status=CompressionStatus.FAILED_ERROR,
                info=f"LLM call failed: {e}",
            )

        # Step 4: Validate summary
        if not summary or not summary.strip():
            self._last_failed = True
            return CompressionResult(
                status=CompressionStatus.FAILED_EMPTY,
                info="Summary was empty",
            )

        # Build new history: summary message + preserved messages
        summary_message = {
            "role": "system",
            "content": f"[Compressed conversation history]\n\n{summary}",
        }
        new_history = [summary_message] + to_preserve

        summary_tokens = self._estimate_tokens(new_history)

        # Reject if compression didn't actually reduce tokens
        if summary_tokens >= original_tokens:
            self._last_failed = True
            return CompressionResult(
                status=CompressionStatus.FAILED_INFLATED,
                original_token_count=original_tokens,
                summary_token_count=summary_tokens,
                info=f"Summary did not reduce tokens ({summary_tokens} >= {original_tokens})",
            )

        # Success
        self._last_failed = False
        return CompressionResult(
            status=CompressionStatus.COMPRESSED,
            new_history=new_history,
            original_token_count=original_tokens,
            summary_token_count=summary_tokens,
            info=f"Compressed from ~{original_tokens} to ~{summary_tokens} tokens",
        )

    # --- Private helpers ---

    @staticmethod
    def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
        """Estimate token count using character-based heuristic."""
        total_chars = 0
        for msg in messages:
            total_chars += len(json.dumps(msg, ensure_ascii=False))
        return max(1, total_chars // CHARS_PER_TOKEN)

    def _find_split_point(
        self, history: list[dict[str, Any]], preserve_fraction: float,
    ) -> int:
        """Find the index where to split history for compression.

        Everything BEFORE the returned index will be summarized.
        Everything AT AND AFTER the returned index will be preserved.

        Rules:
        - Split only at 'user' messages (not assistant/tool responses)
        - Never split right after an assistant message that has tool_calls
          (the pending tool results need to stay together)

        Args:
            history: Current conversation messages.
            preserve_fraction: Fraction of total chars to preserve.

        Returns:
            Index to split at. Returns 0 if no safe split point found.
            Returns len(history) if it's safe to compress everything.
        """
        char_counts = [
            len(json.dumps(msg, ensure_ascii=False)) for msg in history
        ]
        total_chars = sum(char_counts)
        target_chars = int(total_chars * preserve_fraction)

        last_safe_idx = 0
        cumulative = 0

        for i, msg in enumerate(history):
            # Only split at 'user' messages (not tool responses)
            is_user = msg.get("role") == "user" and "tool_call_id" not in msg

            if is_user:
                if cumulative >= target_chars and i > 0:
                    return i
                last_safe_idx = i

            cumulative += char_counts[i]

        # No split found after target — check if last message allows full compression
        if history:
            last_msg = history[-1]
            if last_msg.get("role") == "assistant":
                has_tool_calls = last_msg.get("tool_calls") is not None
                if not has_tool_calls:
                    # Safe: last message has no pending tool calls
                    return len(history)

        return last_safe_idx

    async def _generate_summary(self, messages: list[dict[str, Any]]) -> str:
        """Send older messages to LLM for structured XML summarization.

        Args:
            messages: The older portion of history to summarize.

        Returns:
            XML state_snapshot string, or empty string on failure.
        """
        # Flatten messages for the prompt (truncate each for efficiency)
        history_text = "\n\n".join(
            f"[{msg.get('role', 'unknown')}] {str(msg.get('content', ''))[:500]}"
            for msg in messages
        )

        prompt = f"""{COMPRESSION_PROMPT}

## Conversation History to Summarize

{history_text}

## Your Output

Generate the <state_snapshot> XML below. Do NOT include any other output."""

        response = await self.llm_client.generate(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
            stream=False,
            temperature=0.2,
            max_tokens=COMPRESSION_SUMMARY_MAX_TOKENS,
        )

        content = response.content or ""

        # Extract the <state_snapshot> block
        match = re.search(r"<state_snapshot>.*?</state_snapshot>", content, re.DOTALL)
        if match:
            return match.group(0)

        return content.strip()
