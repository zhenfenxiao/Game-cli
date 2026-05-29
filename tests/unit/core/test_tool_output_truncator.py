"""Tests for ToolOutputTruncator."""

from opengame.core.tool_output_truncator import FLOOR_CHARS, ToolOutputTruncator


class TestToolOutputTruncator:
    def test_empty_text_passthrough(self) -> None:
        truncator = ToolOutputTruncator(128_000)
        assert truncator.truncate("", []) == ""

    def test_short_text_passthrough(self) -> None:
        truncator = ToolOutputTruncator(128_000)
        result = truncator.truncate("short output", [])
        assert result == "short output"

    def test_truncation_applied(self) -> None:
        truncator = ToolOutputTruncator(10_000)
        # Create a huge message to consume most of the context
        huge_msg = [{"role": "user", "content": "x" * 38_000}]  # ~9500 tokens
        long_output = "y" * 10_000
        result = truncator.truncate(long_output, huge_msg)
        assert len(result) < len(long_output)
        assert "truncated" in result.lower()

    def test_floor_preserved(self) -> None:
        truncator = ToolOutputTruncator(10_000)
        # Consume almost all context
        huge_history = [{"role": "user", "content": "x" * 40_000}]
        output = "important" * 300  # ~2400 chars
        result = truncator.truncate(output, huge_history)
        # Floor should preserve at least FLOOR_CHARS
        assert len(result) >= FLOOR_CHARS
