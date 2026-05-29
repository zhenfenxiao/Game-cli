"""Tests for ChatCompressionService."""

from unittest.mock import AsyncMock

import pytest

from opengame.core.chat_compression_service import ChatCompressionService, CompressionStatus


class TestChatCompressionService:
    @pytest.fixture
    def mock_llm(self) -> AsyncMock:
        llm = AsyncMock()
        llm.model = "gpt-4o"
        return llm

    @pytest.fixture
    def service(self, mock_llm: AsyncMock) -> ChatCompressionService:
        return ChatCompressionService(
            llm_client=mock_llm,
            token_limit=128_000,
            threshold=0.70,
            preserve_fraction=0.30,
        )

    @pytest.mark.asyncio
    async def test_noop_empty_history(self, service: ChatCompressionService) -> None:
        result = await service.compress([])
        assert result.status == CompressionStatus.NOOP
        assert "Empty" in result.info

    @pytest.mark.asyncio
    async def test_noop_below_threshold(self, service: ChatCompressionService) -> None:
        small_history = [{"role": "user", "content": "hello"}]
        result = await service.compress(small_history)
        assert result.status == CompressionStatus.NOOP

    @pytest.mark.asyncio
    async def test_compress_with_valid_summary(
        self, service: ChatCompressionService, mock_llm: AsyncMock,
    ) -> None:
        # Create history large enough to trigger compression
        large_content = "x" * 500_000  # ~125k tokens
        history = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": large_content},
            {"role": "assistant", "content": "I'll help"},
            {"role": "user", "content": "do task A"},
            {"role": "assistant", "content": "done A"},
            {"role": "user", "content": "now do B"},
        ]

        mock_llm.generate.return_value.content = "<state_snapshot><overall_goal>Test</overall_goal></state_snapshot>"

        result = await service.compress(history)
        assert result.status == CompressionStatus.COMPRESSED
        assert len(result.new_history) < len(history)

    @pytest.mark.asyncio
    async def test_reject_empty_summary(
        self, service: ChatCompressionService, mock_llm: AsyncMock,
    ) -> None:
        large_history = [
            {"role": "user", "content": "x" * 500_000},
            {"role": "user", "content": "do something"},
        ]
        mock_llm.generate.return_value.content = ""

        result = await service.compress(large_history)
        assert result.status == CompressionStatus.FAILED_EMPTY

    @pytest.mark.asyncio
    async def test_reject_inflated_summary(
        self, service: ChatCompressionService, mock_llm: AsyncMock,
    ) -> None:
        large_history = [
            {"role": "user", "content": "x" * 500_000},
            {"role": "user", "content": "task"},
        ]
        # Return a summary larger than the original
        mock_llm.generate.return_value.content = "y" * 600_000

        result = await service.compress(large_history)
        assert result.status == CompressionStatus.FAILED_INFLATED

    @pytest.mark.asyncio
    async def test_find_split_point_user_boundary(
        self, service: ChatCompressionService,
    ) -> None:
        history = [
            {"role": "system", "content": "prompt"},
            {"role": "user", "content": "x" * 2000},
            {"role": "assistant", "content": "response"},
            {"role": "user", "content": "y" * 2000},
            {"role": "assistant", "content": "response2"},
            {"role": "user", "content": "new task"},
        ]
        idx = service._find_split_point(history, 0.30)
        # Should split at a user message
        assert idx > 0
        assert history[idx]["role"] == "user"
