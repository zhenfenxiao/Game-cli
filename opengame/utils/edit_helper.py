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

    Parses unified diff hunks and applies additions/removals manually.

    Args:
        original: Original text content.
        patch: Unified diff patch string.

    Returns:
        Patched text content.

    Raises:
        ValueError: If the patch cannot be applied cleanly.
    """
    if not patch.strip():
        return original

    original_lines = original.splitlines()
    patch_lines = patch.splitlines()

    result = list(original_lines)
    hunk_offset = 0  # Tracks net position change from prior hunks

    # Parse hunks
    i = 0
    while i < len(patch_lines):
        line = patch_lines[i]

        # Skip header lines
        if line.startswith("---") or line.startswith("+++"):
            i += 1
            continue

        # Parse hunk header: @@ -start,count +start,count @@
        if line.startswith("@@"):
            parts = line.split()
            orig_info = parts[1]  # e.g., "-1,3"
            orig_start = int(orig_info[1:].split(",")[0])
            result_idx = orig_start - 1 + hunk_offset
            i += 1

            while i < len(patch_lines):
                hunk_line = patch_lines[i]
                if hunk_line.startswith("@@"):
                    break  # Next hunk

                if hunk_line.startswith(" "):
                    result_idx += 1
                elif hunk_line.startswith("-"):
                    if 0 <= result_idx < len(result):
                        result.pop(result_idx)
                        hunk_offset -= 1
                elif hunk_line.startswith("+"):
                    result.insert(result_idx, hunk_line[1:])
                    result_idx += 1
                    hunk_offset += 1
                # Skip other lines (like "\\ No newline...")

                i += 1
        else:
            i += 1

    return "\n".join(result) + "\n"


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
