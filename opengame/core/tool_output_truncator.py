"""ToolOutputTruncator — dynamic hard truncation of tool outputs.

This is the LAST line of defense before a tool result is appended to history.
Calculates a safe truncation threshold based on remaining context window,
preventing a single oversized tool result from exceeding the token limit.
"""

from __future__ import annotations

import json
from typing import Any

# Minimum characters to preserve regardless of remaining context
FLOOR_CHARS = 1000

# Rough heuristic: ~4 characters per token for English text
CHARS_PER_TOKEN = 4

# Truncation marker appended to truncated output
TRUNCATION_MARKER = "\n\n[... Output truncated to fit context window ...]"


class ToolOutputTruncator:
    """Dynamically truncate tool outputs before they enter conversation history.

    Formula:
        remaining = token_limit - tokens_used_by_history
        threshold_chars = 4 * remaining
        output_limit = max(threshold_chars, 1000)  # Never go below floor
    """

    def __init__(self, token_limit: int) -> None:
        self.token_limit = token_limit

    def truncate(self, text: str, current_history: list[dict[str, Any]]) -> str:
        """Truncate tool output to fit within remaining context window.

        Args:
            text: Raw tool output text.
            current_history: Current conversation messages BEFORE this result.

        Returns:
            Truncated text if over threshold, otherwise the original text.
        """
        if not text:
            return text

        # Estimate tokens used by current history
        history_tokens = _estimate_history_tokens(current_history)
        remaining_tokens = max(0, self.token_limit - history_tokens)

        # Convert remaining tokens to character threshold (with floor)
        threshold_chars = max(CHARS_PER_TOKEN * remaining_tokens, FLOOR_CHARS)

        if len(text) <= threshold_chars:
            return text

        # Truncate with marker
        truncated = text[:threshold_chars] + TRUNCATION_MARKER
        return truncated


def _estimate_history_tokens(history: list[dict[str, Any]]) -> int:
    """Estimate token count for conversation history.

    Uses a character-based heuristic. For accurate counts,
    use the LLM provider's token counting API.

    Args:
        history: List of message dicts.

    Returns:
        Estimated token count.
    """
    total_chars = 0
    for msg in history:
        total_chars += len(json.dumps(msg, ensure_ascii=False))
    return max(1, total_chars // CHARS_PER_TOKEN)
