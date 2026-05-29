"""Diff/patch utilities for file editing.

Provides unified diff generation, patch application, and search-replace validation.
"""

from __future__ import annotations

import difflib


def compute_diff(original: str, modified: str, fromfile: str = "original", tofile: str = "modified") -> str:
    """Generate a unified diff between two strings.

    Args:
        original: Original text content.
        modified: Modified text content.
        fromfile: Label for the original file in diff header.
        tofile: Label for the modified file in diff header.

    Returns:
        Unified diff as a string. Empty string if no differences.
    """
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    # Ensure lines end with newline for difflib
    if original_lines and not original_lines[-1].endswith("\n"):
        original_lines[-1] += "\n"
    if modified_lines and not modified_lines[-1].endswith("\n"):
        modified_lines[-1] += "\n"

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=fromfile,
        tofile=tofile,
    )
    return "".join(diff)


def apply_patch(original: str, patch: str) -> str:
    """Apply a unified diff patch to original text.

    Args:
        original: Original text content.
        patch: Unified diff patch string.

    Returns:
        Patched text content.

    Raises:
        ValueError: If the patch cannot be applied cleanly.
    """
    original_lines = original.splitlines(keepends=True)
    patch_lines = patch.splitlines(keepends=True)

    # Ensure original lines end with newline
    if original_lines and not original_lines[-1].endswith("\n"):
        original_lines[-1] += "\n"

    try:
        result = list(difflib.restore(patch_lines, 1))  # 1 = from original
        return "".join(result)
    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to apply patch: {e}") from e


def validate_search_replace(content: str, old: str, new: str) -> tuple[bool, str]:
    """Validate that a search string appears exactly once in content.

    Used to verify edit operations before executing them.

    Args:
        content: The full file content.
        old: The string to search for.
        new: The replacement string (used only for error messages).

    Returns:
        Tuple of (is_valid, message). is_valid is True if the search string
        appears exactly once.
    """
    if not old:
        return False, "Search string must not be empty"

    count = content.count(old)

    if count == 0:
        return False, "Search string not found in content"
    elif count > 1:
        return False, f"Search string found {count} times in content (must be unique)"
    elif old == new:
        return False, "Search string and replacement are identical"

    return True, "Valid"
