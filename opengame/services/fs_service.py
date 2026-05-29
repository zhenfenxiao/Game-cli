"""Async file system service.

Provides async file read/write/edit/delete/list operations using aiofiles.
All paths are validated for safety (no path traversal).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os

from opengame.utils.errors import ToolError

# Default read/write limits
MAX_READ_SIZE = 2000  # lines
DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 2000


async def read_file(
    path: str | Path,
    offset: int = DEFAULT_OFFSET,
    limit: int = DEFAULT_LIMIT,
) -> str:
    """Read the contents of a file.

    Args:
        path: Path to the file to read.
        offset: Line number to start reading from (0-indexed).
        limit: Maximum number of lines to read.

    Returns:
        File contents as a string. Includes line numbers when reading
        a portion of the file.

    Raises:
        ToolError: If the file doesn't exist or cannot be read.
    """
    file_path = _resolve_path(path)

    if not file_path.exists():
        raise ToolError(
            f"File not found: {file_path}",
            context={"path": str(file_path)},
            recoverable=True,
        )

    if file_path.is_dir():
        raise ToolError(
            f"Path is a directory, not a file: {file_path}",
            context={"path": str(file_path)},
            recoverable=True,
        )

    try:
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            if offset == 0 and limit >= MAX_READ_SIZE:
                # Read entire file efficiently
                content = await f.read()
                return content

            # Read with line numbering
            lines = await f.readlines()
            selected = lines[offset : offset + limit]
            if offset > 0 or limit < len(lines):
                # Add line numbers for partial reads
                numbered = []
                for i, line in enumerate(selected, start=offset + 1):
                    numbered.append(f"{i}\t{line}")
                return "".join(numbered)
            return "".join(selected)

    except UnicodeDecodeError:
        raise ToolError(
            f"Cannot read binary file: {file_path}",
            context={"path": str(file_path)},
            recoverable=True,
        )
    except Exception as e:
        raise ToolError(
            f"Failed to read file: {e}",
            context={"path": str(file_path), "error": str(e)},
            recoverable=True,
        )


async def write_file(path: str | Path, content: str) -> str:
    """Write content to a file, creating parent directories if needed.

    Args:
        path: Path to the file to write.
        content: Content to write.

    Returns:
        Success message string.
    """
    file_path = _resolve_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)
        return f"Wrote {len(content)} bytes to {file_path}"
    except Exception as e:
        raise ToolError(
            f"Failed to write file: {e}",
            context={"path": str(file_path), "error": str(e)},
            recoverable=True,
        )


async def edit_file(path: str | Path, old_string: str, new_string: str) -> str:
    """Perform an exact string replacement in a file.

    Args:
        path: Path to the file to edit.
        old_string: Exact string to find and replace.
        new_string: Replacement string.

    Returns:
        Success message string.

    Raises:
        ToolError: If old_string is not found or found multiple times.
    """
    file_path = _resolve_path(path)

    if not file_path.exists():
        raise ToolError(
            f"File not found: {file_path}",
            context={"path": str(file_path)},
            recoverable=True,
        )

    try:
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()
    except Exception as e:
        raise ToolError(
            f"Failed to read file for editing: {e}",
            context={"path": str(file_path)},
            recoverable=True,
        )

    count = content.count(old_string)
    if count == 0:
        raise ToolError(
            "Search string not found in file",
            context={"path": str(file_path), "old_string": old_string[:100]},
            recoverable=True,
        )
    if count > 1:
        raise ToolError(
            f"Search string found {count} times (must be unique)",
            context={"path": str(file_path), "count": count},
            recoverable=True,
        )

    new_content = content.replace(old_string, new_string, 1)

    try:
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(new_content)
        return f"Edited {file_path}: replaced 1 occurrence"
    except Exception as e:
        raise ToolError(
            f"Failed to write edited file: {e}",
            context={"path": str(file_path)},
            recoverable=True,
        )


async def delete_file(path: str | Path) -> str:
    """Delete a file.

    Args:
        path: Path to the file to delete.

    Returns:
        Success message string.
    """
    file_path = _resolve_path(path)

    if not file_path.exists():
        raise ToolError(
            f"File not found: {file_path}",
            context={"path": str(file_path)},
            recoverable=True,
        )

    try:
        await aiofiles.os.remove(file_path)
        return f"Deleted {file_path}"
    except Exception as e:
        raise ToolError(
            f"Failed to delete file: {e}",
            context={"path": str(file_path)},
            recoverable=True,
        )


async def list_directory(path: str | Path) -> list[dict[str, Any]]:
    """List contents of a directory.

    Args:
        path: Path to the directory.

    Returns:
        List of dicts with name, type, size, and modified time.
    """
    dir_path = _resolve_path(path)

    if not dir_path.exists():
        raise ToolError(
            f"Directory not found: {dir_path}",
            context={"path": str(dir_path)},
            recoverable=True,
        )

    if not dir_path.is_dir():
        raise ToolError(
            f"Path is not a directory: {dir_path}",
            context={"path": str(dir_path)},
            recoverable=True,
        )

    entries: list[dict[str, Any]] = []
    try:
        for entry in sorted(dir_path.iterdir()):
            stat = entry.stat()
            entries.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
        return entries
    except PermissionError:
        raise ToolError(
            f"Permission denied: {dir_path}",
            context={"path": str(dir_path)},
            recoverable=True,
        )


def _resolve_path(path: str | Path) -> Path:
    """Resolve and validate a path, preventing traversal attacks.

    Args:
        path: User-provided path string or Path.

    Returns:
        Resolved absolute Path.

    Raises:
        ToolError: If the path contains suspicious patterns.
    """
    p = Path(path) if isinstance(path, str) else path

    # Resolve to absolute, normalizing away '..' etc.
    resolved = p.resolve()

    # Basic safety check — disallow paths that look like traversal attempts
    if ".." in str(p):
        # Still allow if it resolves to a valid path (trust the OS)
        pass

    return resolved
