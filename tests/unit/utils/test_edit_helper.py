"""Tests for diff/patch utilities."""

import pytest

from opengame.utils.edit_helper import apply_patch, compute_diff, validate_search_replace


class TestComputeDiff:
    """Tests for compute_diff."""

    def test_identical_strings_produce_empty_diff(self) -> None:
        """No differences = empty diff."""
        diff = compute_diff("hello\n", "hello\n")
        assert diff == ""

    def test_different_strings_produce_diff(self) -> None:
        """Changes produce a unified diff."""
        diff = compute_diff("hello\n", "world\n")
        assert "hello" in diff or "world" in diff
        assert diff != ""


class TestApplyPatch:
    """Tests for apply_patch."""

    def test_apply_diff_roundtrip(self) -> None:
        """Computing a diff and applying it returns the modified text."""
        original = "line1\nline2\nline3\n"
        modified = "line1\nline2_changed\nline3\n"
        diff = compute_diff(original, modified)
        result = apply_patch(original, diff)
        assert result.strip() == modified.strip()

    def test_apply_preserves_content(self) -> None:
        """Applying a patch preserves non-changed content."""
        original = "A\nB\nC\nD\nE\n"
        modified = "A\nB\nX\nD\nE\n"
        diff = compute_diff(original, modified)
        result = apply_patch(original, diff)
        assert "A" in result
        assert "E" in result
        assert "X" in result
        assert "C" not in result


class TestValidateSearchReplace:
    """Tests for validate_search_replace."""

    def test_unique_match_is_valid(self) -> None:
        """Single occurrence is valid."""
        ok, msg = validate_search_replace("hello world hello", "world", "earth")
        assert ok is True
        assert "Valid" in msg

    def test_empty_search_returns_invalid(self) -> None:
        """Empty search string is invalid."""
        ok, msg = validate_search_replace("hello", "", "x")
        assert ok is False

    def test_zero_occurrences_is_invalid(self) -> None:
        """Search string not found."""
        ok, msg = validate_search_replace("hello", "world", "x")
        assert ok is False
        assert "not found" in msg.lower()

    def test_multiple_occurrences_is_invalid(self) -> None:
        """Multiple occurrences are invalid."""
        ok, msg = validate_search_replace("hello hello", "hello", "hi")
        assert ok is False
        assert "2 times" in msg

    def test_identical_strings_is_invalid(self) -> None:
        """Old and new are the same."""
        ok, msg = validate_search_replace("hello world", "hello", "hello")
        assert ok is False
        assert "identical" in msg.lower()
