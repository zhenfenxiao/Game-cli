"""Subagent tool: delegate tasks to specialized subagents.

Creates a new AgentContext and recursively invokes the TurnLoop with
a filtered tool set and reduced turn limit.
"""

from __future__ import annotations

import json
from typing import Any

from opengame.core.agent_context import AgentContext
from opengame.core.tool_registry import ToolParameter, ToolRegistry

# Maximum turns for subagent invocations (prevents infinite recursion)
SUBAGENT_MAX_TURNS = 25


def register_subagent_tool(
    registry: ToolRegistry,
    turn_loop: Any | None = None,
) -> None:
    """Register subagent delegation tool.

    Requires the TurnLoop instance for recursive invocation. The subagent
    runs with a limited turn budget and can use a subset of tools.

    Args:
        registry: ToolRegistry to register tools with.
        turn_loop: TurnLoop instance for subagent execution.
    """
    if not turn_loop:
        return

    async def subagent(description: str, prompt: str, tools: str | None = None) -> str:
        """Delegate a task to a specialized subagent.

        The subagent runs independently with its own conversation context,
        a limited turn budget, and optionally a filtered set of tools.
        """
        # Parse tools filter if provided
        tool_list: list[str] | None = None
        if tools:
            try:
                tool_list = json.loads(tools) if isinstance(tools, str) else tools
            except json.JSONDecodeError:
                pass

        # Build the filtered tool registry
        sub_registry = ToolRegistry()
        if tool_list:
            # Only include specified tools
            for tool_name in tool_list:
                tool_def = turn_loop.tool_registry.get_tool(tool_name)
                if tool_def and tool_def.func:
                    sub_registry.register(
                        name=tool_def.name,
                        func=tool_def.func,
                        description=tool_def.description,
                        parameters=tool_def.parameters,
                    )
        else:
            # Copy all tools except subagent (prevent infinite recursion)
            for tool_name in turn_loop.tool_registry.list_tools():
                if tool_name == "subagent":
                    continue
                tool_def = turn_loop.tool_registry.get_tool(tool_name)
                if tool_def and tool_def.func:
                    sub_registry.register(
                        name=tool_def.name,
                        func=tool_def.func,
                        description=tool_def.description,
                        parameters=tool_def.parameters,
                    )

        # Build system prompt for subagent
        system_prompt = f"""You are a specialized subagent with the following purpose:
{description}

Complete your assigned task efficiently. Use the available tools to read files,
search code, and gather information. When finished, provide a clear summary of
your findings or the work completed.

You have a limited turn budget ({SUBAGENT_MAX_TURNS} turns). Be concise."""

        # Create sub context
        sub_context = AgentContext()

        # Create a sub-TurnLoop with limited turns and the filtered registry
        # We reuse the same LLM client but with restricted capabilities
        from opengame.core.turn_loop import TurnLoop

        sub_loop = TurnLoop(
            llm_client=turn_loop.llm_client,
            tool_registry=sub_registry,
            max_turns=SUBAGENT_MAX_TURNS,
            token_limit=turn_loop.token_limit,
            compression_threshold=turn_loop.compression_threshold,
        )

        # Run subagent
        result = await sub_loop.run(
            system_prompt=system_prompt,
            user_message=prompt,
            context=sub_context,
        )

        return json.dumps({
            "subagent_result": result.text,
            "finished": result.finished,
            "turns_used": result.turn_count,
        }, ensure_ascii=False, indent=2)

    registry.register(
        name="subagent",
        func=subagent,
        description="Delegate a task to a specialized subagent. The subagent runs with "
        "its own conversation context and a limited turn budget. Use for complex, "
        "self-contained subtasks that don't need the full conversation history.",
        parameters=[
            ToolParameter(
                name="description",
                type="string",
                description="Short description of what the subagent should do",
                required=True,
            ),
            ToolParameter(
                name="prompt",
                type="string",
                description="The detailed task for the subagent to complete",
                required=True,
            ),
            ToolParameter(
                name="tools",
                type="string",
                description="Optional JSON array of tool names to make available. "
                "If not provided, all tools except subagent are available.",
                required=False,
            ),
        ],
    )
