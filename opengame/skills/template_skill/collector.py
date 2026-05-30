"""ProjectCollector — creates a ProjectSnapshot by walking a project directory.

Collects source files, ignores build artifacts, and generates a code summary
for classification and pattern extraction.
"""

from __future__ import annotations

import re
from pathlib import Path

import aiofiles

from opengame.skills.template_skill.types import FileEntry, ProjectSnapshot

# Directories to ignore during collection
IGNORE_DIRS: set[str] = {
    "node_modules", ".git", ".opengame", "dist", "build",
    ".next", ".nuxt", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".ruff_cache", ".pytest_cache",
}

# File extensions to collect
COLLECT_EXTENSIONS: set[str] = {
    ".ts", ".js", ".json", ".html", ".css", ".md", ".tsx", ".jsx",
}

# Files to skip even if extension matches
SKIP_FILES: set[str] = {
    "package-lock.json", "tsconfig.json", ".prettierrc",
}


class ProjectCollector:
    """Collects project files into a ProjectSnapshot for analysis.

    Walks the project directory tree, reads text files, ignores
    build artifacts and node_modules, and generates a code summary.
    """

    def __init__(self) -> None:
        pass

    async def collect(self, project_dir: str | Path) -> ProjectSnapshot:
        """Collect all source files from a project directory.

        Args:
            project_dir: Path to the project root.

        Returns:
            ProjectSnapshot with files, file tree, and code summary.
        """
        root = Path(project_dir).resolve()

        if not root.exists() or not root.is_dir():
            return ProjectSnapshot(
                project_path=str(root),
                code_summary=f"Directory not found: {root}",
            )

        files: list[FileEntry] = []
        file_tree: list[str] = []
        game_config: dict | None = None

        for entry in sorted(root.rglob("*")):
            if not self._should_include(entry):
                continue

            if entry.is_file():
                rel_path = str(entry.relative_to(root))
                ext = entry.suffix.lower()

                if ext not in COLLECT_EXTENSIONS:
                    continue

                if entry.name in SKIP_FILES:
                    continue

                file_tree.append(rel_path)

                try:
                    async with aiofiles.open(entry, "r", encoding="utf-8") as f:
                        content = await f.read()
                except (UnicodeDecodeError, OSError):
                    content = f"[Binary or unreadable file: {entry.name}]"

                files.append(FileEntry(
                    relative_path=rel_path,
                    content=content,
                    extension=ext,
                ))

                # Capture gameConfig.json
                if entry.name == "gameConfig.json":
                    import json
                    try:
                        game_config = json.loads(content)
                    except json.JSONDecodeError:
                        pass

        # Generate code summary
        code_summary = self._generate_code_summary(files)

        return ProjectSnapshot(
            project_path=str(root),
            files=files,
            file_tree=file_tree,
            game_config=game_config,
            code_summary=code_summary,
        )

    @staticmethod
    def _should_include(entry: Path) -> bool:
        """Check if a path should be included (not in an ignored directory)."""
        parts = entry.parts
        return not any(ignored in parts for ignored in IGNORE_DIRS)

    @staticmethod
    def _generate_code_summary(files: list[FileEntry]) -> str:
        """Generate a human-readable code structure summary.

        Args:
            files: Collected file entries.

        Returns:
            Summary string describing the code structure.
        """
        if not files:
            return "Empty project (no source files found)"

        # Count by extension
        ext_counts: dict[str, int] = {}
        class_names: list[str] = []

        class_pattern = re.compile(r"class\s+(\w+)")
        import_pattern = re.compile(r"import\s+\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]")

        for f in files:
            ext = f.extension
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

            # Extract class names
            for match in class_pattern.finditer(f.content):
                class_names.append(match.group(1))

        # Build summary
        parts: list[str] = []

        ext_summary = ", ".join(f"{count} {ext}" for ext, count in sorted(ext_counts.items()))
        parts.append(f"Project contains {len(files)} files: {ext_summary}")

        if class_names:
            unique_classes = list(dict.fromkeys(class_names))[:20]  # Dedupe, limit
            parts.append(f"Key classes: {', '.join(unique_classes)}")
            if len(class_names) > 20:
                parts.append(f"  ... and {len(class_names) - 20} more classes")

        return "\n".join(parts)
