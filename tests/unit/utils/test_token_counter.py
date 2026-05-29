"""Tests for token estimation and model limits."""

import pytest

from opengame.utils.token_counter import estimate_tokens, get_model_token_limit


class TestEstimateTokens:
    """Tests for estimate_tokens using 4-char-per-token heuristic."""

    def test_empty_string(self) -> None:
        """Empty string returns 0."""
        assert estimate_tokens("") == 0

    def test_none_input(self) -> None:
        """None returns 0."""
        assert estimate_tokens(None) == 0  # type: ignore[arg-type]

    def test_short_string(self) -> None:
        """Very short strings return at least 1."""
        assert estimate_tokens("hi") == 1

    def test_typical_english(self) -> None:
        """~4 characters per token."""
        text = "hello world this is a test"
        assert estimate_tokens(text) == len(text) // 4

    def test_long_text(self) -> None:
        """Long text scales linearly."""
        text = "x" * 4000
        assert estimate_tokens(text) == 1000


class TestGetModelTokenLimit:
    """Tests for model context window lookups."""

    def test_known_openai_model(self) -> None:
        """gpt-4o returns 128k."""
        assert get_model_token_limit("gpt-4o") == 128_000

    def test_known_claude_model(self) -> None:
        """Claude models return 200k."""
        assert get_model_token_limit("claude-sonnet-4") == 200_000

    def test_known_deepseek_model(self) -> None:
        """DeepSeek models return specific limits."""
        assert get_model_token_limit("deepseek-chat") == 128_000

    def test_fuzzy_match(self) -> None:
        """Model names containing known keys are matched."""
        assert get_model_token_limit("gpt-4o-2024-08-06") == 128_000

    def test_unknown_model_returns_default(self) -> None:
        """Unknown models return the 128k default."""
        assert get_model_token_limit("some-new-model") == 128_000
