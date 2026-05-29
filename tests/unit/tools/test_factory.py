"""Tests for ToolRegistry factory."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opengame.tools.factory import create_tool_registry


class TestCreateToolRegistry:
    def test_basic_registry(self) -> None:
        reg = create_tool_registry()
        tools = reg.list_tools()
        # Should have all basic tools (17 without llm_client/turn_loop)
        assert len(tools) >= 17
        assert "read_file" in tools
        assert "shell" in tools
        assert "classify_game_type" in tools

    def test_with_llm_client(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.model = "gpt-4o"
        reg = create_tool_registry(llm_client=mock_llm)
        tools = reg.list_tools()
        assert "smart_edit" in tools
        assert "generate_gdd" in tools

    def test_with_turn_loop(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.model = "gpt-4o"
        mock_loop = MagicMock()
        mock_loop.llm_client = mock_llm
        mock_loop.tool_registry = create_tool_registry(llm_client=mock_llm)
        mock_loop.token_limit = 128_000
        mock_loop.compression_threshold = 0.70

        reg = create_tool_registry(llm_client=mock_llm, turn_loop=mock_loop)
        tools = reg.list_tools()
        assert "todo_write" in tools
        assert "subagent" in tools

    def test_all_tools_have_schemas(self) -> None:
        reg = create_tool_registry()
        schemas = reg.get_tool_definitions()
        assert len(schemas) == len(reg.list_tools())
        for schema in schemas:
            assert schema["type"] == "function"
            assert "name" in schema["function"]
            assert "parameters" in schema["function"]
