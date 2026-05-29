"""ToolRegistry factory — creates a fully populated registry with dependency injection.

This is the single entry point for creating a complete, wired-up ToolRegistry.
It calls each register_* function with the appropriate injected dependencies,
ensuring tools like smart_edit, todo_write, and subagent have access to
runtime services they need.
"""

from __future__ import annotations

from typing import Any

from opengame.core.llm_client import BaseLlmClient
from opengame.core.tool_registry import ToolRegistry
from opengame.tools.control_tools import register_control_tools
from opengame.tools.file_tools import register_file_tools
from opengame.tools.game_tools import register_game_tools
from opengame.tools.memory_tools import register_memory_tools
from opengame.tools.shell_tools import register_shell_tools
from opengame.tools.subagent_tool import register_subagent_tool
from opengame.tools.task_tools import register_task_tools
from opengame.tools.web_tools import register_web_tools


def create_tool_registry(
    llm_client: BaseLlmClient | None = None,
    turn_loop: Any | None = None,
) -> ToolRegistry:
    """Create a fully populated ToolRegistry with all agent tools.

    Dependency injection is handled via closures:
    - smart_edit captures llm_client
    - generate_gdd captures llm_client
    - todo_write captures turn_loop (for AgentContext access)
    - subagent captures turn_loop (for recursive invocation)

    Args:
        llm_client: Optional LLM client for AI-dependent tools.
        turn_loop: Optional TurnLoop instance for context-dependent tools.

    Returns:
        Populated ToolRegistry with all available tools registered.
    """
    registry = ToolRegistry()

    # Register tools that don't need dependency injection first
    register_shell_tools(registry)
    register_web_tools(registry)
    register_memory_tools(registry)
    register_control_tools(registry)

    # Register tools that need llm_client (passed via closure)
    register_file_tools(registry, llm_client=llm_client)
    register_game_tools(registry, llm_client=llm_client)

    # Register tools that need turn_loop context (passed via closure)
    register_task_tools(registry, turn_loop=turn_loop)

    # Register subagent (needs turn_loop, registered last)
    if turn_loop:
        register_subagent_tool(registry, turn_loop=turn_loop)

    return registry
