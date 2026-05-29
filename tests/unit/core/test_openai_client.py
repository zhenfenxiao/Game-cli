"""Tests for the OpenAI-compatible client.

Uses respx for HTTP request mocking.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opengame.core.llm_client import LlmResponse
from opengame.core.openai_client import OpenAiClient


class TestOpenAiClientInit:
    """Tests for client initialization."""

    def test_default_init(self) -> None:
        """Client can be created with defaults."""
        client = OpenAiClient()
        assert client.model == "gpt-4o"
        assert client.timeout == 120.0

    def test_custom_init(self) -> None:
        """Custom model and base_url."""
        client = OpenAiClient(
            model="gpt-4o-mini",
            base_url="https://custom.api.com/v1",
            api_key="sk-test",
            timeout=60.0,
        )
        assert client.model == "gpt-4o-mini"
        assert client.base_url == "https://custom.api.com/v1"
        assert client.timeout == 60.0


class TestOpenAiClientResponses:
    """Tests for response handling."""

    @pytest.mark.asyncio
    async def test_blocking_generate(self) -> None:
        """Blocking generation returns complete response."""
        client = OpenAiClient(api_key="sk-test")

        # Mock the OpenAI client's create method
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Hello, world!"
        mock_message.tool_calls = None
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "gpt-4o"

        mock_create = AsyncMock(return_value=mock_response)
        with patch.object(client._client.chat.completions, "create", mock_create):
            result = await client.generate(
                messages=[{"role": "user", "content": "Say hello"}],
                stream=False,
            )

        assert isinstance(result, LlmResponse)
        assert result.content == "Hello, world!"
        assert result.finish_reason == "stop"
        assert len(result.tool_calls) == 0

    @pytest.mark.asyncio
    async def test_tool_call_response(self) -> None:
        """Response with tool calls is parsed correctly."""
        client = OpenAiClient(api_key="sk-test")

        import json
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = None

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "read_file"
        mock_tool_call.function.arguments = json.dumps({"path": "/tmp/test.txt"})

        mock_message.tool_calls = [mock_tool_call]
        mock_choice.message = mock_message
        mock_choice.finish_reason = "tool_calls"
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "gpt-4o"

        mock_create = AsyncMock(return_value=mock_response)
        with patch.object(client._client.chat.completions, "create", mock_create):
            result = await client.generate(
                messages=[{"role": "user", "content": "Read a file"}],
                tools=[{"type": "function", "function": {"name": "read_file"}}],
                stream=False,
            )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"
        assert result.tool_calls[0].arguments == {"path": "/tmp/test.txt"}
