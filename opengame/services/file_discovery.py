"""Async file discovery and indexing service.

Provides file tree discovery, glob pattern matching, and content search (grep).
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

# Directories and patterns ignored by default
DEFAULT_IGNORE_DIRS: set[str] = {
    "node_modules",
    ".git",
    ".opengame",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".cache",
}

DEFAULT_IGNORE_PATTERNS: list[str] = [
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.lock",
    "package-lock.json",
    "*.min.js",
    "*.min.css",
    "*.map",
]


async def discover_files(
    root_dir: str | Path,
    patterns: list[str] | None = None,
    ignore_patterns: list[str] | None = None,
) -> list[Path]:
    """Discover files in a directory tree, respecting ignore patterns.

    Args:
        root_dir: Root directory to search from.
        patterns: Optional glob patterns to filter files (e.g., ["*.ts", "*.json"]).
        ignore_patterns: Additional patterns to ignore.

    Returns:
        List of Path objects for matching files.
    """
    root = Path(root_dir).resolve()
    if not root.exists() or not root.is_dir():
        return []

    ignore_dirs = DEFAULT_IGNORE_DIRS.copy()
    ignore_file_patterns = list(DEFAULT_IGNORE_PATTERNS)
    if ignore_patterns:
        ignore_file_patterns.extend(ignore_patterns)

    # Load .gitignore if present
    gitignore_patterns = _load_gitignore(root)
    ignore_file_patterns.extend(gitignore_patterns)

    results: list[Path] = []

    for entry in root.rglob("*"):
        # Skip ignored directories
        if any(ignored in entry.parts for ignored in ignore_dirs):
            continue

        if not entry.is_file():
            continue

        # Check ignore patterns
        if any(fnmatch.fnmatch(entry.name, pat) for pat in ignore_file_patterns):
            continue

        # Filter by user patterns
        if patterns:
            if not any(fnmatch.fnmatch(entry.name, pat) for pat in patterns):
                continue

        results.append(entry)

    return sorted(results)


async def glob_files(
    pattern: str,
    directory: str | Path | None = None,
) -> list[Path]:
    """Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.ts", "src/*.py").
        directory: Directory to search in (defaults to current directory).

    Returns:
        List of matching Path objects.
    """
    base = Path(directory).resolve() if directory else Path.cwd()

    if not base.exists():
        return []

    results = list(base.glob(pattern))

    # Filter out ignored directories
    filtered = []
    for p in results:
        if not any(ignored in p.parts for ignored in DEFAULT_IGNORE_DIRS):
            filtered.append(p)

    return sorted(filtered)


async def grep_files(
    query: str,
    path: str | Path,
    is_regex: bool = False,
) -> list[dict[str, Any]]:
    """Search for text in files.

    Args:
        query: Search query (literal or regex pattern).
        path: Directory or file to search.
        is_regex: If True, treat query as a regex pattern.

    Returns:
        List of dicts with file, line_number, and line for each match.
    """
    target = Path(path).resolve()
    results: list[dict[str, Any]] = []

    if not target.exists():
        return results

    # Determine files to search
    files: list[Path] = []
    if target.is_file():
        files = [target]
    else:
        files = await discover_files(target)

    search_pattern: re.Pattern
    try:
        if is_regex:
            search_pattern = re.compile(query)
        else:
            search_pattern = re.compile(re.escape(query))
    except re.error:
        return results

    for file_path in files:
        # Skip binary/large files
        if file_path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".mp3", ".wav", ".mp4", ".zip", ".tar"}:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        lines = content.split("\n")
        for i, line in enumerate(lines, start=1):
            if search_pattern.search(line):
                results.append({
                    "file": str(file_path),
                    "line_number": i,
                    "line": line.strip()[:200],  # Truncate long lines
                })

    return results


def _load_gitignore(root: Path) -> list[str]:
    """Load .gitignore patterns from a directory, if present."""
    gitignore_path = root / ".gitignore"
    if not gitignore_path.exists():
        return []

    patterns: list[str] = []
    try:
        content = gitignore_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    except Exception:
        pass

    return patterns
