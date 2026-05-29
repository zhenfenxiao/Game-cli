"""Tool registry with @tool decorator and async dispatch.

Provides a decorator-based system for registering tools that can be
called by the LLM agent. Each tool has a name, description, and
JSON Schema for its parameters.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolParameter:
    """A single parameter in a tool's schema."""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    enum: list[str] | None = None


@dataclass
class ToolDefinition:
    """Complete metadata for a registered tool."""

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    func: Callable[..., Any] | None = None  # The callable (None for async tools)
    is_async: bool = False

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible function schema."""
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


@dataclass
class ToolCall:
    """Represents a pending tool call from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result of executing a tool."""

    call_id: str
    name: str
    output: str
    error: str | None = None
    success: bool = True


@dataclass
class TurnResult:
    """Result of a single turn in the agent loop."""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    finish_reason: str = "stop"


class ToolRegistry:
    """Registry for tools that can be called by the LLM agent.

    Tools are registered via the @tool decorator and can be executed
    by name with JSON arguments.

    Usage:
        registry = ToolRegistry()

        @registry.tool(name="read_file", description="Read a file")
        async def read_file(path: str, offset: int = 0) -> str:
            ...
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def tool(
        self,
        name: str,
        description: str = "",
        parameters: list[ToolParameter] | None = None,
    ) -> Callable:
        """Decorator to register a tool function.

        Args:
            name: Unique tool name (used by LLM to call it).
            description: Human-readable description for the LLM.
            parameters: Optional explicit parameter definitions. If not provided,
                        parameters are inferred from the function signature.

        Returns:
            Decorator that registers the function and returns it unchanged.
        """
        def decorator(func: Callable) -> Callable:
            is_async = inspect.iscoroutinefunction(func)

            # Infer parameters from function signature if not explicitly provided
            if parameters is None:
                inferred_params = _infer_parameters(func)
            else:
                inferred_params = list(parameters)

            self._tools[name] = ToolDefinition(
                name=name,
                description=description or func.__doc__ or "",
                parameters=inferred_params,
                func=func,
                is_async=is_async,
            )
            return func

        return decorator

    def register(
        self,
        name: str,
        func: Callable,
        description: str = "",
        parameters: list[ToolParameter] | None = None,
    ) -> None:
        """Register a tool function directly (without decorator).

        Args:
            name: Unique tool name.
            func: The callable to register.
            description: Human-readable description.
            parameters: Optional explicit parameter definitions.
        """
        is_async = inspect.iscoroutinefunction(func)
        self._tools[name] = ToolDefinition(
            name=name,
            description=description or func.__doc__ or "",
            parameters=parameters or _infer_parameters(func),
            func=func,
            is_async=is_async,
        )

    async def execute(self, name: str, arguments: dict[str, Any], call_id: str = "") -> ToolResult:
        """Execute a registered tool by name.

        Args:
            name: Tool name to execute.
            arguments: Keyword arguments for the tool function.
            call_id: Optional call ID for correlating results.

        Returns:
            ToolResult with output or error.
        """
        if name not in self._tools:
            return ToolResult(
                call_id=call_id,
                name=name,
                output="",
                error=f"Unknown tool: {name}",
                success=False,
            )

        tool_def = self._tools[name]
        if tool_def.func is None:
            return ToolResult(
                call_id=call_id,
                name=name,
                output="",
                error=f"Tool '{name}' has no callable",
                success=False,
            )

        try:
            if tool_def.is_async:
                result = await tool_def.func(**arguments)
            else:
                result = tool_def.func(**arguments)

            output = str(result) if not isinstance(result, str) else result
            return ToolResult(
                call_id=call_id,
                name=name,
                output=output,
                success=True,
            )
        except Exception as e:
            return ToolResult(
                call_id=call_id,
                name=name,
                output="",
                error=str(e),
                success=False,
            )

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get all registered tools as OpenAI-compatible function schemas.

        Returns:
            List of tool definition dicts for the LLM API.
        """
        return [t.to_json_schema() for t in self._tools.values()]

    def list_tools(self) -> list[str]:
        """Get names of all registered tools.

        Returns:
            List of tool names.
        """
        return list(self._tools.keys())

    def get_tool(self, name: str) -> ToolDefinition | None:
        """Get a single tool definition by name.

        Args:
            name: Tool name.

        Returns:
            ToolDefinition or None if not found.
        """
        return self._tools.get(name)


def _infer_parameters(func: Callable) -> list[ToolParameter]:
    """Infer tool parameters from a function's signature.

    Args:
        func: The function to inspect.

    Returns:
        List of ToolParameter objects inferred from the signature.
    """
    params: list[ToolParameter] = []
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return params

    for param_name, param in sig.parameters.items():
        # Skip self/cls
        if param_name in ("self", "cls"):
            continue

        # Map Python types to JSON Schema types
        annotation = param.annotation
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        # Handle string-based annotations (forward refs)
        if isinstance(annotation, str):
            param_type = "string"
        else:
            param_type = type_map.get(annotation, "string")  # type: ignore[arg-type]

        has_default = param.default is not inspect.Parameter.empty
        tool_param = ToolParameter(
            name=param_name,
            type=param_type,
            description="",
            required=not has_default,
            default=param.default if has_default else None,
        )
        params.append(tool_param)

    return params
