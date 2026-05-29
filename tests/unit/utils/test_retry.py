"""Tests for the retry decorator."""

import asyncio
from typing import Any

import pytest

from opengame.utils.retry import retry


class TestRetrySync:
    """Tests for sync retry behavior."""

    def test_successful_call_no_retry(self) -> None:
        """Function that succeeds on first try returns immediately."""
        call_count = 0

        @retry(max_retries=3)
        def maybe_fail() -> int:
            nonlocal call_count
            call_count += 1
            return 42

        result = maybe_fail()
        assert result == 42
        assert call_count == 1

    def test_retry_on_exception(self) -> None:
        """Function that fails N times then succeeds."""
        call_count = 0

        @retry(max_retries=3, backoff_base=0.01)
        def fail_then_succeed() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary failure")
            return 99

        result = fail_then_succeed()
        assert result == 99
        assert call_count == 3

    def test_exhaust_retries_raises(self) -> None:
        """When all retries exhausted, the last exception is raised."""
        call_count = 0

        @retry(max_retries=2, backoff_base=0.01)
        def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("permanent failure")

        with pytest.raises(ValueError, match="permanent failure"):
            always_fails()
        assert call_count == 3  # 1 initial + 2 retries

    def test_only_specified_exceptions_trigger_retry(self) -> None:
        """Only exceptions in the 'exceptions' tuple trigger retry."""
        call_count = 0

        @retry(max_retries=3, backoff_base=0.01, exceptions=(ValueError,))
        def fail_with_type_error() -> None:
            nonlocal call_count
            call_count += 1
            raise TypeError("not caught")

        with pytest.raises(TypeError):
            fail_with_type_error()
        assert call_count == 1  # No retry for TypeError


class TestRetryAsync:
    """Tests for async retry behavior."""

    @pytest.mark.asyncio
    async def test_async_successful_call(self) -> None:
        """Async function that succeeds."""
        call_count = 0

        @retry(max_retries=3)
        async def maybe_fail() -> int:
            nonlocal call_count
            call_count += 1
            return 42

        result = await maybe_fail()
        assert result == 42
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_and_succeed(self) -> None:
        """Async function retries and eventually succeeds."""
        call_count = 0

        @retry(max_retries=3, backoff_base=0.01)
        async def fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("temp")
            return "ok"

        result = await fail_then_succeed()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_exhaust_retries(self) -> None:
        """Async function exhausts retries and raises."""
        call_count = 0

        @retry(max_retries=1, backoff_base=0.01)
        async def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError, match="fail"):
            await always_fails()
        assert call_count == 2
