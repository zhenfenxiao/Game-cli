"""Tests for TokenLimitChecker."""

from opengame.core.token_limit_checker import TokenLimitChecker, get_model_output_limit


class TestTokenLimitChecker:
    def test_initial_state(self) -> None:
        checker = TokenLimitChecker("gpt-4o")
        assert checker.session_turn_count == 0
        assert not checker.is_turn_limit_exceeded()

    def test_turn_limit_exceeded(self) -> None:
        checker = TokenLimitChecker("gpt-4o", max_turns=3)
        checker.increment_turn()
        checker.increment_turn()
        assert not checker.is_turn_limit_exceeded()
        checker.increment_turn()
        assert checker.is_turn_limit_exceeded()

    def test_token_limit_not_exceeded_small_messages(self) -> None:
        checker = TokenLimitChecker("gpt-4o")
        messages = [{"role": "user", "content": "hi"}]
        assert not checker.is_token_limit_exceeded(messages)

    def test_token_limit_exceeded_large_messages(self) -> None:
        checker = TokenLimitChecker("gpt-4o", max_turns=100)
        # Create a message that exceeds the session limit
        huge_content = "x" * (checker.session_token_limit * 6)  # way over
        messages = [{"role": "user", "content": huge_content}]
        assert checker.is_token_limit_exceeded(messages)

    def test_get_remaining_tokens(self) -> None:
        checker = TokenLimitChecker("gpt-4o")
        messages = [{"role": "user", "content": "hello"}]
        remaining = checker.get_remaining_tokens(messages)
        assert remaining > 0
        # Most of the context window should be available
        assert remaining > checker.session_token_limit // 2

    def test_session_token_limit_uses_safety_margin(self) -> None:
        checker = TokenLimitChecker("gpt-4o")  # 128k raw
        assert checker.session_token_limit == int(128_000 * 0.95)


class TestGetModelOutputLimit:
    def test_known_model(self) -> None:
        assert get_model_output_limit("gpt-4o") == 16_384

    def test_unknown_model_default(self) -> None:
        assert get_model_output_limit("unknown-model") == 4_096
