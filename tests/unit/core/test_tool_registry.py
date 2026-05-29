"""Tests for the ToolRegistry."""

from __future__ import annotations

import pytest

from opengame.core.tool_registry import (
    ToolCall,
    ToolDefinition,
    ToolParameter,
    ToolRegistry,
    ToolResult,
    TurnResult,
    _infer_parameters,
)


class TestToolRegistry:
    """Tests for tool registration and execution."""

    def test_register_tool_via_decorator(self) -> None:
        """Tools can be registered with the @tool decorator."""
        registry = ToolRegistry()

        @registry.tool(name="add", description="Add two numbers")
        async def add(a: int, b: int) -> int:
            return a + b

        assert "add" in registry.list_tools()

    def test_execute_tool(self) -> None:
        """Registered tools can be executed."""
        registry = ToolRegistry()

        @registry.tool(name="multiply")
        async def multiply(x: int, y: int) -> int:
            return x * y

        result = registry.execute("multiply", {"x": 3, "y": 4}, call_id="call-1")
        import asyncio
        result_obj = asyncio.run(result)
        assert result_obj.success is True
        assert "12" in result_obj.output

    def test_execute_unknown_tool(self) -> None:
        """Executing an unknown tool returns an error."""
        registry = ToolRegistry()
        import asyncio
        result = asyncio.run(registry.execute("nonexistent", {}))
        assert result.success is False
        assert "Unknown tool" in result.error

    def test_execute_tool_with_error(self) -> None:
        """Tool execution errors are caught and returned."""
        registry = ToolRegistry()

        @registry.tool(name="failer")
        async def failer() -> str:
            raise ValueError("intentional failure")

        import asyncio
        result = asyncio.run(registry.execute("failer", {}))
        assert result.success is False
        assert "intentional failure" in result.error


class TestToolDefinitions:
    """Tests for ToolDefinition and JSON schema generation."""

    def test_basic_schema(self) -> None:
        """Basic tool generates valid schema."""
        registry = ToolRegistry()

        @registry.tool(name="greet", description="Greet a user")
        async def greet(name: str, times: int = 1) -> str:
            return f"Hello {name} " * times

        schemas = registry.get_tool_definitions()
        assert len(schemas) == 1
        schema = schemas[0]
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "greet"
        assert "name" in schema["function"]["parameters"]["properties"]
        assert "times" in schema["function"]["parameters"]["properties"]

    def test_required_params(self) -> None:
        """Required parameters are listed in schema."""
        registry = ToolRegistry()

        @registry.tool(name="test")
        async def test_fn(required_param: str, optional_param: str = "default") -> str:
            return "ok"

        schema = registry.get_tool_definitions()[0]
        required = schema["function"]["parameters"]["required"]
        assert "required_param" in required
        assert "optional_param" not in required


class TestInferParameters:
    """Tests for signature inference."""

    def test_infer_str_param(self) -> None:
        """String parameters are inferred correctly."""
        def func(name: str) -> None: ...
        params = _infer_parameters(func)
        assert len(params) == 1
        assert params[0].name == "name"
        assert params[0].type == "string"
        assert params[0].required is True

    def test_infer_int_param_with_default(self) -> None:
        """Parameters with defaults are not required."""
        def func(limit: int = 10) -> None: ...
        params = _infer_parameters(func)
        assert params[0].required is False
        assert params[0].default == 10

    def test_skip_self_param(self) -> None:
        """'self' parameter is skipped."""
        class Foo:
            def method(self, x: str) -> None: ...
        params = _infer_parameters(Foo.method)
        assert len(params) == 1
        assert params[0].name == "x"


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_successful_result(self) -> None:
        """Successful result has no error."""
        r = ToolResult(call_id="1", name="test", output="done")
        assert r.success is True
        assert r.error is None

    def test_failed_result(self) -> None:
        """Failed result carries error message."""
        r = ToolResult(call_id="1", name="test", output="", error="failed", success=False)
        assert r.success is False
        assert r.error == "failed"
