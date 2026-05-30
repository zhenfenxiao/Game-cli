"""Pydantic v2 data models for Template Skill.

Defines all models from PRD section 3.2:
PhysicsProfile, FileEntry, ProjectSnapshot, ClassificationResult,
ExtractedPatterns, TemplateFileDef, AbstractedTemplates,
TemplateFamily, EvolutionEntry, TemplateLibrary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


# --- Core Classification ---


class PhysicsProfile(BaseModel):
    """Physical properties of a game, used for archetype classification."""

    has_gravity: bool = Field(description="Does the game apply Y-axis gravity?")
    perspective: Literal["side", "top_down", "none"] = Field(
        description="Camera perspective: side-view, top-down, or not applicable"
    )
    movement_type: Literal["continuous", "grid", "path", "ui_only"] = Field(
        description="Movement system: continuous physics, discrete grid, fixed path, or UI-only"
    )


class FileEntry(BaseModel):
    """A single file in a project snapshot."""

    relative_path: str = Field(description="Path relative to project root")
    content: str = Field(description="File contents")
    extension: str = Field(description="File extension, e.g. '.ts', '.json'")


class ProjectSnapshot(BaseModel):
    """Complete snapshot of a project for analysis."""

    project_path: str
    files: list[FileEntry] = Field(default_factory=list)
    file_tree: list[str] = Field(default_factory=list)
    game_config: dict[str, Any] | None = None
    code_summary: str = ""


class ClassificationResult(BaseModel):
    """Output of the archetype classifier."""

    archetype: str = Field(description="snake_case physics regime label")
    reasoning: str = Field(default="", description="Explanation citing specific code evidence")
    physics_profile: PhysicsProfile
    confidence: float = Field(ge=0.0, le=1.0)
    is_new_family: bool = Field(default=False, description="Whether this archetype is new to the library")


# --- Pattern Extraction ---


class ClassDef(BaseModel):
    """Extracted class definition from source code."""

    name: str
    parent_class: str | None = None
    file_path: str
    is_abstract: bool = False
    methods: list[MethodDef] = Field(default_factory=list)


class MethodDef(BaseModel):
    """Extracted method definition."""

    name: str
    visibility: Literal["public", "protected", "private"] = "public"
    is_abstract: bool = False
    is_override: bool = False
    signature: str = Field(default="", description="Simplified signature string")


class HookDef(BaseModel):
    """A hook method — an override point in the template architecture."""

    name: str
    declaring_class: str = Field(default="", description="Which base class declares this hook")
    signature: str = ""
    is_abstract: bool = False
    occurrence_count: int = Field(default=0, description="How many projects use this hook")


class ImportEdge(BaseModel):
    """An import dependency between files."""

    from_file: str
    to_file: str
    imported_names: list[str] = Field(default_factory=list)


class DirectoryPattern(BaseModel):
    """Directory structure pattern extracted from a project."""

    directories: list[str] = Field(default_factory=list)
    files_by_directory: dict[str, list[str]] = Field(default_factory=dict)


class ConfigField(BaseModel):
    """A configuration field extracted from gameConfig.json."""

    key: str
    value: Any
    group: str = "general"
    description: str = ""


class ExtractedPatterns(BaseModel):
    """Compound result of pattern extraction from a project snapshot."""

    archetype: str
    physics_profile: PhysicsProfile
    project_path: str
    file_structure: DirectoryPattern = Field(default_factory=DirectoryPattern)
    classes: list[ClassDef] = Field(default_factory=list)
    hooks: list[HookDef] = Field(default_factory=list)
    config_extensions: list[ConfigField] = Field(default_factory=list)
    imports: list[ImportEdge] = Field(default_factory=list)
    code_snippets: dict[str, str] = Field(default_factory=dict)


# --- Abstraction ---


class TemplateFileDef(BaseModel):
    """A single file in an abstracted template."""

    relative_path: str
    content: str
    role: Literal["base_class", "copy_template", "system", "behavior", "utility"] = "behavior"


class AbstractedTemplates(BaseModel):
    """Result of abstracting extracted patterns into template files."""

    archetype: str
    template_files: list[TemplateFileDef] = Field(default_factory=list)
    hooks: list[HookDef] = Field(default_factory=list)
    config_schema: list[ConfigField] = Field(default_factory=list)
    summary: str = ""


# --- Library Management ---


class TemplateFamily(BaseModel):
    """A single archetype family in the template library."""

    id: str = Field(description="Unique family ID, e.g. 'fam-platformer-001'")
    archetype: str
    physics_profile: PhysicsProfile
    discovered_at_task: str = ""
    contributing_projects: list[str] = Field(default_factory=list)
    stability: float = Field(default=0.1, ge=0.0, le=1.0)
    file_structure: DirectoryPattern = Field(default_factory=DirectoryPattern)
    base_classes: list[ClassDef] = Field(default_factory=list)
    hooks: list[HookDef] = Field(default_factory=list)
    config_extensions: list[ConfigField] = Field(default_factory=list)
    template_files: list[TemplateFileDef] = Field(default_factory=list)
    summary: str = ""


class EvolutionEntry(BaseModel):
    """A single entry in the library's evolution log."""

    task_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    project_path: str
    archetype: str
    action: Literal["created_family", "merged_to_family"]
    family_id: str = ""
    patterns_extracted: int = 0
    patterns_merged: int = 0


class TemplateLibrary(BaseModel):
    """Complete template library with families and evolution log."""

    version: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    meta_template_path: str = ""
    families: list[TemplateFamily] = Field(default_factory=list)
    evolution_log: list[EvolutionEntry] = Field(default_factory=list)
