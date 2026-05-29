"""Agent tools package.

Provides all 21 tool implementations for the OpenGame agent, organized by category.
Tools are registered via register_* functions that accept a ToolRegistry and
optional dependency injection parameters.
"""

from opengame.tools.factory import create_tool_registry

__all__ = ["create_tool_registry"]
