"""ToolOutputSummarizer — LLM-based tool output compression.

Compresses individual tool outputs when they exceed a token budget,
using a lightweight model for cost efficiency. Always falls back
gracefully to the original output on any failure.
"""

from __future__ import annotations

from opengame.core.llm_client import BaseLlmClient

# Maximum input text to send to the LLM for summarization
MAX_INPUT_CHARS = 15_000

# Default maximum output tokens for the summary itself
DEFAULT_MAX_OUTPUT_TOKENS = 2000

# Character threshold for triggering summarization (fast path gate)
DEFAULT_MAX_OUTPUT_CHARS = 2000

TOOL_OUTPUT_SUMMARY_PROMPT: str = """\
You are a tool output summarizer. Summarize the following tool output into a concise form while preserving ALL errors, warnings, and critical information.

Rules:
- Preserve all error messages, warnings, and their associated file paths and line numbers
- Preserve file paths, code snippets, and any structured data that the agent needs
- Summarize repetitive output (e.g. long file listings, repeated log lines) into counts or patterns
- The summary should be significantly shorter than the original
- If the output is already concise, return it as-is

## Tool Output

{text_to_summarize}

## Your Summary
"""


class ToolOutputSummarizer:
    """Summarize individual tool outputs that exceed a token budget.

    Unlike ChatCompressionService which handles the full conversation history,
    this service targets single, oversized tool results (e.g. long grep output,
    large file reads, extensive build logs).

    Uses a lightweight model for cost efficiency. Never fails the main flow —
    if summarization produces empty/inflated output or an exception, the
    original text is returned unchanged.
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    ) -> None:
        self.llm_client = llm_client
        self.max_output_tokens = max_output_tokens
        self.max_output_chars = max_output_chars

    async def summarize(self, text: str) -> str:
        """Summarize tool output if it exceeds the character budget.

        Args:
            text: Raw tool output text.

        Returns:
            Summarized text, or original if below threshold or on failure.
        """
        # Fast path: return as-is if already short
        if not text or len(text) < self.max_output_chars:
            return text

        prompt = TOOL_OUTPUT_SUMMARY_PROMPT.format(
            text_to_summarize=text[:MAX_INPUT_CHARS],
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

            # Validation: reject empty or inflated summaries
            if not summary.strip():
                return text

            if len(summary) >= len(text):
                return text

            return summary

        except Exception:
            # Never fail the main flow because summarization failed
            return text
