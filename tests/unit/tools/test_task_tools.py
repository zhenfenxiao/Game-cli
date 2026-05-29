"""Tests for task management tools."""

import json
from unittest.mock import MagicMock

import pytest

from opengame.core.tool_registry import ToolRegistry
from opengame.tools.task_tools import register_task_tools


class TestTaskTools:
    @pytest.fixture
    def registry(self) -> ToolRegistry:
        reg = ToolRegistry()
        register_task_tools(reg)
        return reg

    @pytest.mark.asyncio
    async def test_task_create(self, registry: ToolRegistry) -> None:
        result = await registry.execute(
            "task_create",
            {"subject": "Fix bug", "description": "Fix the login bug"},
        )
        assert result.success
        data = json.loads(result.output)
        assert "id" in data
        assert data["subject"] == "Fix bug"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_task_update(self, registry: ToolRegistry) -> None:
        result = await registry.execute(
            "task_update",
            {"task_id": "abc123", "status": "in_progress"},
        )
        assert result.success
        data = json.loads(result.output)
        assert data["updated"] is True

    @pytest.mark.asyncio
    async def test_task_update_invalid_status(self, registry: ToolRegistry) -> None:
        result = await registry.execute(
            "task_update",
            {"task_id": "abc", "status": "invalid_status"},
        )
        assert "Error" in result.output

    @pytest.mark.asyncio
    async def test_todo_write_with_turn_loop(self) -> None:
        reg = ToolRegistry()
        mock_loop = MagicMock()
        mock_loop.context.todo_list = []

        register_task_tools(reg, turn_loop=mock_loop)

        todos = json.dumps([
            {"id": "1", "content": "task 1", "status": "pending", "priority": "high"},
        ])
        result = await reg.execute("todo_write", {"todos": todos})
        assert result.success
        assert len(mock_loop.context.todo_list) == 1
