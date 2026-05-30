"""PatternExtractor — extracts structural patterns from a project snapshot.

Parses TypeScript source files to extract classes, methods, hooks,
imports, configuration, and directory structure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from opengame.skills.template_skill.types import (
    ClassDef,
    ClassificationResult,
    ConfigField,
    DirectoryPattern,
    ExtractedPatterns,
    HookDef,
    ImportEdge,
    MethodDef,
    ProjectSnapshot,
)

# Regex patterns for TypeScript parsing
CLASS_RE = re.compile(
    r"export\s+(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{",
    re.MULTILINE,
)
METHOD_RE = re.compile(
    r"(public|protected|private)?\s*(?:static\s+)?(?:async\s+)?"
    r"(\w+)\s*\([^)]*\)\s*:\s*(\w+)",
    re.MULTILINE,
)
OVERRIDE_RE = re.compile(r"override\s+(public|protected|private)?\s*(\w+)\s*\(", re.MULTILINE)
IMPORT_RE = re.compile(r"import\s+\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
ABSTRACT_CLASS_RE = re.compile(r"abstract\s+class\s+(\w+)", re.MULTILINE)
ABSTRACT_METHOD_RE = re.compile(r"abstract\s+(\w+)\s*\([^)]*\)\s*:\s*(\w+)", re.MULTILINE)


class PatternExtractor:
    """Extract structural patterns from a project snapshot.

    Analyzes TypeScript source to identify classes, hooks, imports,
    configuration extensions, and directory structure.
    """

    def __init__(self) -> None:
        pass

    def extract(
        self,
        snapshot: ProjectSnapshot,
        classification: ClassificationResult,
    ) -> ExtractedPatterns:
        """Extract all patterns from the project.

        Args:
            snapshot: The collected project snapshot.
            classification: The archetype classification result.

        Returns:
            ExtractedPatterns with all identified patterns.
        """
        return ExtractedPatterns(
            archetype=classification.archetype,
            physics_profile=classification.physics_profile,
            project_path=snapshot.project_path,
            file_structure=self._extract_file_structure(snapshot),
            classes=self._extract_classes(snapshot),
            hooks=self._extract_hooks(snapshot),
            config_extensions=self._extract_config(snapshot),
            imports=self._extract_imports(snapshot),
            code_snippets=self._extract_snippets(snapshot),
        )

    @staticmethod
    def _extract_file_structure(snapshot: ProjectSnapshot) -> DirectoryPattern:
        """Extract directory structure from file tree."""
        directories: list[str] = []
        files_by_directory: dict[str, list[str]] = {}

        for file_path in snapshot.file_tree:
            parent = str(Path(file_path).parent) or "."
            if parent not in files_by_directory:
                files_by_directory[parent] = []
                directories.append(parent)
            files_by_directory[parent].append(str(Path(file_path).name))

        return DirectoryPattern(
            directories=directories,
            files_by_directory=files_by_directory,
        )

    def _extract_classes(self, snapshot: ProjectSnapshot) -> list[ClassDef]:
        """Extract class definitions from TypeScript files."""
        classes: list[ClassDef] = []

        for f in snapshot.files:
            if f.extension not in (".ts", ".tsx"):
                continue

            for match in CLASS_RE.finditer(f.content):
                name = match.group(1)
                parent = match.group(2)
                is_abstract = bool(ABSTRACT_CLASS_RE.search(
                    f.content[match.start():match.start() + 50]
                ))

                # Extract methods within this class
                methods = self._extract_methods(f.content, match.start(), match.end())

                classes.append(ClassDef(
                    name=name,
                    parent_class=parent,
                    file_path=f.relative_path,
                    is_abstract=is_abstract,
                    methods=methods,
                ))

        return classes

    def _extract_methods(self, content: str, class_start: int, class_end: int) -> list[MethodDef]:
        """Extract methods from within a class body."""
        methods: list[MethodDef] = []

        # Find the class body
        body_match = re.search(r"\{", content[class_start:])
        if not body_match:
            return methods

        body_start = class_start + body_match.start()
        # Rough body extraction (balanced braces)
        depth = 0
        body_end = body_start
        for i, ch in enumerate(content[body_start:], start=body_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    body_end = i
                    break

        body = content[body_start:body_end]

        for match in METHOD_RE.finditer(body):
            visibility = match.group(1) or "public"
            if visibility in ("public", "protected", "private"):
                methods.append(MethodDef(
                    name=match.group(2),
                    visibility=visibility,  # type: ignore[arg-type]
                    is_abstract=False,
                    is_override="override" in body[max(0, match.start() - 20):match.start()],
                    signature=f"{match.group(2)}(...): {match.group(3)}",
                ))

        return methods

    @staticmethod
    def _extract_hooks(snapshot: ProjectSnapshot) -> list[HookDef]:
        """Extract hook methods (override points) from TypeScript files."""
        hooks: list[HookDef] = []
        seen: set[str] = set()

        for f in snapshot.files:
            if f.extension not in (".ts", ".tsx"):
                continue

            for match in OVERRIDE_RE.finditer(f.content):
                method_name = match.group(2)
                if method_name not in seen:
                    seen.add(method_name)
                    hooks.append(HookDef(
                        name=method_name,
                        declaring_class="",
                        signature=f"{method_name}(...)",
                        is_abstract=False,
                        occurrence_count=1,
                    ))

        return hooks

    @staticmethod
    def _extract_config(snapshot: ProjectSnapshot) -> list[ConfigField]:
        """Extract configuration fields beyond the M0 baseline."""
        baseline_keys = {"screenSize", "debugConfig", "renderConfig"}

        if not snapshot.game_config:
            return []

        config_fields: list[ConfigField] = []

        def _flatten(d: dict, prefix: str = "") -> None:
            for key, value in d.items():
                if key in baseline_keys:
                    continue
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    _flatten(value, full_key)
                else:
                    config_fields.append(ConfigField(
                        key=full_key,
                        value=value,
                        group=prefix.split(".")[0] if prefix else "general",
                    ))

        _flatten(snapshot.game_config)
        return config_fields

    @staticmethod
    def _extract_imports(snapshot: ProjectSnapshot) -> list[ImportEdge]:
        """Extract import dependencies between files."""
        imports: list[ImportEdge] = []

        for f in snapshot.files:
            if f.extension not in (".ts", ".tsx"):
                continue

            for match in IMPORT_RE.finditer(f.content):
                imported = [n.strip() for n in match.group(1).split(",")]
                imports.append(ImportEdge(
                    from_file=f.relative_path,
                    to_file=match.group(2),
                    imported_names=imported,
                ))

        return imports

    @staticmethod
    def _extract_snippets(snapshot: ProjectSnapshot) -> dict[str, str]:
        """Extract key code snippets, prioritizing template-related files."""
        snippets: dict[str, str] = {}
        priority_patterns = ["Base", "_Template", "LevelManager", "main"]

        for f in snapshot.files:
            if f.extension not in (".ts", ".tsx"):
                continue

            # Prioritize files with template-related names
            is_priority = any(p in f.relative_path for p in priority_patterns)
            max_len = 5000 if is_priority else 2000

            if len(f.content) > max_len:
                snippets[f.relative_path] = f.content[:max_len] + "\n// ... truncated"
            else:
                snippets[f.relative_path] = f.content

        return snippets
