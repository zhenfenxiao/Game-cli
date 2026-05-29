"""Safe JSON operations.

Handles edge cases in JSON parsing and serialization, including
Path objects, datetime objects, and Pydantic models.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def safe_json_loads(text: str) -> Any:
    """Parse JSON text safely, returning None on failure.

    Args:
        text: JSON string to parse.

    Returns:
        Parsed object, or None if parsing fails.
    """
    if not text or not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def safe_json_dumps(obj: Any, indent: int = 2) -> str:
    """Serialize an object to JSON, handling special types.

    Handles Path, datetime, and Pydantic models transparently.

    Args:
        obj: Object to serialize.
        indent: JSON indentation level.

    Returns:
        JSON string representation.
    """
    return json.dumps(obj, indent=indent, default=_json_serializer, ensure_ascii=False)


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for non-standard types."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):  # Pydantic v2 model
        return obj.model_dump()
    if hasattr(obj, "dict"):  # Pydantic v1 model / dataclass fallback
        return obj.dict()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def format_json_error(text: str) -> str:
    """Format a JSON parse error with position highlighting.

    Args:
        text: The invalid JSON string.

    Returns:
        Formatted error message showing the error position.
    """
    try:
        json.loads(text)
        return "Valid JSON (no error)"
    except json.JSONDecodeError as e:
        lines = text.split("\n")
        line = lines[e.lineno - 1] if e.lineno <= len(lines) else ""
        pointer = " " * (e.colno - 1) + "^"
        return (
            f"JSON parse error at line {e.lineno}, column {e.colno}: {e.msg}\n"
            f"  {line}\n"
            f"  {pointer}"
        )
