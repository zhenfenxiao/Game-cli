"""Shell tool: execute shell commands with timeout and safety checking."""

from __future__ import annotations

import json

from opengame.core.tool_registry import ToolParameter, ToolRegistry
from opengame.services.shell_service import ShellReadOnlyChecker, run_command
from opengame.utils.errors import ToolError


def register_shell_tools(registry: ToolRegistry) -> None:
    """Register shell execution tool.

    Args:
        registry: ToolRegistry to register tools with.
    """
    checker = ShellReadOnlyChecker()

    @registry.tool(
        name="shell",
        description="Execute a shell command. Use for running build commands, tests, "
        "git operations, and other CLI tasks. Commands are executed asynchronously "
        "with a configurable timeout. Read-only commands are auto-approved.",
        parameters=[
            ToolParameter(
                name="command",
                type="string",
                description="The shell command to execute",
                required=True,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Maximum execution time in seconds (default 120)",
                required=False,
                default=120,
            ),
        ],
    )
    async def shell(command: str, timeout: int = 120) -> str:
        is_read_only = checker.is_read_only(command)
        is_dangerous = checker.is_dangerous(command)

        try:
            result = await run_command(command, timeout=timeout)
            output: dict = {
                "exit_code": result["exit_code"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "command": command,
                "read_only": is_read_only,
                "dangerous": is_dangerous,
            }
            return json.dumps(output, ensure_ascii=False, indent=2)
        except ToolError as e:
            return json.dumps({
                "exit_code": -1,
                "stdout": "",
                "stderr": e.message,
                "command": command,
                "error": True,
            }, ensure_ascii=False, indent=2)
