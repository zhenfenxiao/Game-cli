"""Control tools: exit_plan_mode.

Simple state transition signals for the agent's execution flow.
"""

from __future__ import annotations

from opengame.core.tool_registry import ToolRegistry


def register_control_tools(registry: ToolRegistry) -> None:
    """Register control flow tools.

    Args:
        registry: ToolRegistry to register tools with.
    """

    @registry.tool(
        name="exit_plan_mode",
        description="Exit planning mode and begin implementation. Use this when "
        "you have finished designing your plan and are ready to start coding.",
    )
    async def exit_plan_mode() -> str:
        return "Exited planning mode. Beginning implementation."
