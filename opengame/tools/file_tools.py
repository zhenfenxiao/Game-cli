"""File tools: read_file, read_many_files, write_file, edit, smart_edit, glob, grep, ls.

All tools are thin wrappers around the existing async services from
opengame.services, with proper error handling and LLM-friendly output formatting.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from opengame.core.llm_client import BaseLlmClient
from opengame.core.tool_registry import ToolParameter, ToolRegistry
from opengame.services import file_discovery
from opengame.services import fs_service
from opengame.utils.errors import ToolError


def register_file_tools(
    registry: ToolRegistry,
    llm_client: BaseLlmClient | None = None,
) -> None:
    """Register all file operation tools.

    Args:
        registry: ToolRegistry to register tools with.
        llm_client: Optional LLM client for smart_edit (closure-injected).
    """

    # --- read_file ---
    @registry.tool(
        name="read_file",
        description="Read the contents of a file at the given path. "
        "Use offset and limit to read a specific range of lines.",
        parameters=[
            ToolParameter(name="file_path", type="string", description="Absolute path to the file", required=True),
            ToolParameter(name="offset", type="integer", description="Line number to start reading from (0-indexed)", required=False, default=0),
            ToolParameter(name="limit", type="integer", description="Maximum number of lines to read", required=False, default=2000),
        ],
    )
    async def read_file(file_path: str, offset: int = 0, limit: int = 2000) -> str:
        try:
            return await fs_service.read_file(file_path, offset, limit)
        except ToolError as e:
            return f"Error reading file: {e.message}"

    # --- read_many_files ---
    @registry.tool(
        name="read_many_files",
        description="Read multiple files in parallel. Useful for exploring a codebase.",
        parameters=[
            ToolParameter(name="file_paths", type="array", description="List of absolute file paths to read", required=True),
        ],
    )
    async def read_many_files(file_paths: list[str]) -> str:
        async def read_one(path: str) -> tuple[str, str]:
            try:
                content = await fs_service.read_file(path)
                return path, content
            except ToolError as e:
                return path, f"ERROR: {e.message}"

        tasks = [read_one(p) for p in file_paths]
        results = await asyncio.gather(*tasks)

        output_parts: list[str] = []
        for path, content in results:
            output_parts.append(f"=== {path} ===\n{content}")
        return "\n\n".join(output_parts)

    # --- write_file ---
    @registry.tool(
        name="write_file",
        description="Write content to a file. Creates parent directories if needed. Overwrites existing files.",
        parameters=[
            ToolParameter(name="file_path", type="string", description="Absolute path to write to", required=True),
            ToolParameter(name="content", type="string", description="Content to write", required=True),
        ],
    )
    async def write_file(file_path: str, content: str) -> str:
        try:
            return await fs_service.write_file(file_path, content)
        except ToolError as e:
            return f"Error writing file: {e.message}"

    # --- edit ---
    @registry.tool(
        name="edit",
        description="Make an exact string replacement in a file. "
        "The old_string must appear exactly once in the file.",
        parameters=[
            ToolParameter(name="file_path", type="string", description="Absolute path to the file", required=True),
            ToolParameter(name="old_string", type="string", description="The exact string to find and replace", required=True),
            ToolParameter(name="new_string", type="string", description="The replacement string", required=True),
        ],
    )
    async def edit(file_path: str, old_string: str, new_string: str) -> str:
        try:
            return await fs_service.edit_file(file_path, old_string, new_string)
        except ToolError as e:
            return f"Error editing file: {e.message}"

    # --- smart_edit ---
    if llm_client:
        async def smart_edit(file_path: str, instruction: str) -> str:
            """Make an intelligent edit to a file using AI to determine the exact change."""
            try:
                current_content = await fs_service.read_file(file_path)
            except ToolError as e:
                return f"Error reading file: {e.message}"

            prompt = f"""You are a code editor. Given the current file content and an edit instruction, output the exact OLD and NEW strings to replace.

Output format (exactly):
--- OLD ---
<the exact string to find in the file>
--- NEW ---
<the replacement string>

Current file: {file_path}
Content:
```
{current_content}
```

Edit instruction: {instruction}

Respond with ONLY the OLD/NEW block."""
            try:
                response = await llm_client.generate(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=2000,
                )
                content = response.content or ""
            except Exception as e:
                return f"Error calling LLM for smart_edit: {e}"

            # Parse the response
            import re
            old_match = re.search(r"--- OLD ---\s*\n(.*?)\n--- NEW ---", content, re.DOTALL)
            new_match = re.search(r"--- NEW ---\s*\n(.*?)$", content, re.DOTALL)

            if not old_match or not new_match:
                return f"ERROR: Could not parse smart_edit response. Response was:\n{content[:500]}"

            old_str = old_match.group(1).strip()
            new_str = new_match.group(1).strip()

            if not old_str:
                return "ERROR: smart_edit produced empty OLD string"

            try:
                return await fs_service.edit_file(file_path, old_str, new_str)
            except ToolError as e:
                return f"Error applying smart_edit: {e.message}"

        registry.register(
            name="smart_edit",
            func=smart_edit,
            description="Make an intelligent edit to a file by describing what you want to change in natural language. "
            "The system will determine the exact text to find and replace.",
            parameters=[
                ToolParameter(name="file_path", type="string", description="Absolute path to the file", required=True),
                ToolParameter(name="instruction", type="string", description="Natural language description of the change", required=True),
            ],
        )

    # --- glob ---
    @registry.tool(
        name="glob",
        description="Find files matching a glob pattern. Use to discover files in a project.",
        parameters=[
            ToolParameter(name="pattern", type="string", description="Glob pattern (e.g., '**/*.ts', 'src/*.py')", required=True),
            ToolParameter(name="directory", type="string", description="Directory to search in (defaults to current directory)", required=False),
        ],
    )
    async def glob(pattern: str, directory: str | None = None) -> str:
        results = await file_discovery.glob_files(pattern, directory)
        if not results:
            return f"No files matching '{pattern}'"
        return "\n".join(str(p) for p in results)

    # --- grep ---
    @registry.tool(
        name="grep",
        description="Search for text in files. Returns matching lines with file paths and line numbers.",
        parameters=[
            ToolParameter(name="query", type="string", description="Search query (literal or regex pattern)", required=True),
            ToolParameter(name="path", type="string", description="File or directory to search in", required=True),
            ToolParameter(name="is_regex", type="boolean", description="Treat query as a regex pattern", required=False, default=False),
        ],
    )
    async def grep(query: str, path: str, is_regex: bool = False) -> str:
        results = await file_discovery.grep_files(query, path, is_regex)
        if not results:
            return f"No matches for '{query}'"
        lines = [f"{r['file']}:{r['line_number']}: {r['line']}" for r in results]
        return "\n".join(lines[:200])  # Limit to 200 matches

    # --- ls ---
    @registry.tool(
        name="ls",
        description="List the contents of a directory.",
        parameters=[
            ToolParameter(name="path", type="string", description="Absolute path to the directory", required=True),
        ],
    )
    async def ls(path: str) -> str:
        try:
            entries = await fs_service.list_directory(path)
            if not entries:
                return f"Directory '{path}' is empty"
            lines = []
            for e in entries:
                type_indicator = "📁" if e["type"] == "directory" else "📄"
                size_str = f" ({e['size']} bytes)" if e["type"] == "file" else ""
                lines.append(f"{type_indicator} {e['name']}{size_str}")
            return "\n".join(lines)
        except ToolError as e:
            return f"Error listing directory: {e.message}"
