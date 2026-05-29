"""Async tool execution scheduler.

Runs multiple tool calls in parallel using asyncio.gather.
"""

from __future__ import annotations

import asyncio
from typing import Any

from opengame.core.tool_registry import ToolCall, ToolRegistry, ToolResult


async def execute_all(
    tool_calls: list[ToolCall],
    registry: ToolRegistry,
) -> list[ToolResult]:
    """Execute multiple tool calls in parallel.

    Each tool call is dispatched independently. Failures in one tool
    do not affect others.

    Args:
        tool_calls: List of tool calls to execute.
        registry: ToolRegistry containing the tool implementations.

    Returns:
        List of ToolResult objects, one per tool call (order preserved).
    """
    if not tool_calls:
        return []

    async def execute_one(tc: ToolCall) -> ToolResult:
        try:
            return await registry.execute(
                name=tc.name,
                arguments=tc.arguments,
                call_id=tc.id,
            )
        except Exception as e:
            return ToolResult(
                call_id=tc.id,
                name=tc.name,
                output="",
                error=str(e),
                success=False,
            )

    tasks = [execute_one(tc) for tc in tool_calls]
    results = await asyncio.gather(*tasks)
    return list(results)
