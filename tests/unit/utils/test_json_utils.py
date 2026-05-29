"""Tests for safe JSON utilities."""

from datetime import datetime
from pathlib import Path

import pytest

from opengame.utils.json_utils import format_json_error, safe_json_dumps, safe_json_loads


class TestSafeJsonLoads:
    """Tests for safe_json_loads."""

    def test_parse_valid_json(self) -> None:
        """Valid JSON is parsed correctly."""
        assert safe_json_loads('{"a": 1}') == {"a": 1}
        assert safe_json_loads('[1, 2, 3]') == [1, 2, 3]
        assert safe_json_loads('"hello"') == "hello"

    def test_parse_invalid_json_returns_none(self) -> None:
        """Invalid JSON returns None instead of raising."""
        assert safe_json_loads("not json") is None
        assert safe_json_loads("{broken") is None

    def test_parse_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert safe_json_loads("") is None

    def test_parse_none_returns_none(self) -> None:
        """None input returns None."""
        assert safe_json_loads(None) is None  # type: ignore[arg-type]

    def test_parse_non_string_returns_none(self) -> None:
        """Non-string input returns None."""
        assert safe_json_loads(42) is None  # type: ignore[arg-type]


class TestSafeJsonDumps:
    """Tests for safe_json_dumps."""

    def test_dumps_basic_types(self) -> None:
        """Basic Python types are serialized."""
        result = safe_json_dumps({"a": 1, "b": "hello", "c": True})
        parsed = safe_json_loads(result)
        assert parsed == {"a": 1, "b": "hello", "c": True}

    def test_dumps_path_object(self) -> None:
        """Path objects are converted to strings."""
        result = safe_json_dumps({"path": Path("/tmp/test")})
        assert "/tmp/test" in result
        parsed = safe_json_loads(result)
        assert parsed["path"] == "/tmp/test"

    def test_dumps_datetime(self) -> None:
        """Datetime objects are serialized."""
        dt = datetime(2026, 5, 29, 12, 0, 0)
        result = safe_json_dumps({"time": dt})
        assert "2026-05-29T12:00:00" in result


class TestFormatJsonError:
    """Tests for format_json_error."""

    def test_valid_json_no_error(self) -> None:
        """Valid JSON returns a 'no error' message."""
        result = format_json_error('{"a": 1}')
        assert "Valid JSON" in result

    def test_invalid_json_shows_position(self) -> None:
        """Invalid JSON error message includes position info."""
        result = format_json_error('{"a": }')
        assert "parse error" in result.lower() or "JSON" in result
