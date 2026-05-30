"""Token limit checker — enforces turn and token ceilings.

Uses the token counter from utils for model-aware context window limits
with a 5% safety margin.
"""

from __future__ import annotations

from typing import Any

from opengame.utils.token_counter import estimate_tokens, get_model_token_limit

# Default maximum turns in a single conversation
MAX_TURNS = 100

# Safety margin: use 95% of the declared context window
SAFETY_MARGIN = 0.95

# Models and their output token limits (used for reserving response space)
MODEL_OUTPUT_LIMITS: dict[str, int] = {
    "gpt-4o": 16_384,
    "gpt-4o-mini": 16_384,
    "gpt-4-turbo": 4_096,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 4_096,
    "claude-3-opus": 4_096,
    "claude-3.5-sonnet": 8_192,
    "claude-sonnet-4": 16_384,
    "claude-opus-4": 16_384,
    "deepseek-v4": 8_192,
    "deepseek-reasoner": 8_192,
}


def get_model_output_limit(model: str) -> int:
    """Get the output token limit for a model.

    Args:
        model: Model name/identifier.

    Returns:
        Output token limit. Defaults to 4096 for unknown models.
    """
    # Exact match
    if model in MODEL_OUTPUT_LIMITS:
        return MODEL_OUTPUT_LIMITS[model]

    # Fuzzy match
    model_lower = model.lower()
    for known_model, limit in MODEL_OUTPUT_LIMITS.items():
        if known_model in model_lower:
            return limit

    return 4_096


class TokenLimitChecker:
    """Enforces turn and token limits during agent conversations.

    Uses the model's declared context window with a 5% safety margin
    to prevent API errors from exceeded limits.
    """

    def __init__(self, model: str = "gpt-4o", max_turns: int = MAX_TURNS) -> None:
        self.model = model
        self.max_turns = max_turns
        self.session_turn_count = 0

        # Context window with safety margin
        raw_limit = get_model_token_limit(model)
        self.session_token_limit = int(raw_limit * SAFETY_MARGIN)

    def increment_turn(self) -> None:
        """Increment the turn counter."""
        self.session_turn_count += 1

    def is_turn_limit_exceeded(self) -> bool:
        """Check if the turn count has exceeded the maximum.

        Returns:
            True if max_turns has been reached or exceeded.
        """
        return self.session_turn_count >= self.max_turns

    def is_token_limit_exceeded(self, messages: list[dict[str, Any]]) -> bool:
        """Check if the estimated token usage exceeds the session limit.

        Args:
            messages: Current conversation messages.

        Returns:
            True if estimated tokens exceed the safe limit.
        """
        estimated = self._count_tokens(messages)
        return estimated > self.session_token_limit

    def get_remaining_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Calculate remaining tokens in the context window.

        Args:
            messages: Current conversation messages.

        Returns:
            Number of tokens remaining (never negative).
        """
        estimated = self._count_tokens(messages)
        output_reserve = get_model_output_limit(self.model)
        remaining = self.session_token_limit - estimated - output_reserve
        return max(0, remaining)

    def _count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Estimate token count for a list of messages.

        Uses the char-based heuristic from utils.token_counter.
        Falls back to simple estimation if tiktoken is unavailable.

        Args:
            messages: List of message dicts.

        Returns:
            Estimated token count.
        """
        total = 0
        for msg in messages:
            # Count role
            total += estimate_tokens(msg.get("role", ""))

            # Count content (may be string or list of content blocks)
            content = msg.get("content", "")
            if isinstance(content, str):
                total += estimate_tokens(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        total += estimate_tokens(str(block.get("text", "")))

            # Count tool calls
            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    total += estimate_tokens(str(tc.get("function", {}).get("arguments", "")))
                    total += estimate_tokens(str(tc.get("function", {}).get("name", "")))

            # Count tool call id
            if "tool_call_id" in msg:
                total += estimate_tokens(msg["tool_call_id"])

        return max(1, total)
