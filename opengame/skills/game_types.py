"""Pydantic v2 data models for game generation.

Defines all models from PRD section 3.4:
GameDesignDocument, AssetSpec, GeneratedAsset, GameResult.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class GddSection(BaseModel):
    """A single section of the Game Design Document."""

    section_number: int
    title: str
    content: str


class GameDesignDocument(BaseModel):
    """Complete Game Design Document with 6 sections."""

    title: str = ""
    archetype: str = ""
    sections: list[GddSection] = Field(default_factory=list)
    asset_registry: list[dict] = Field(default_factory=list)
    config_schema: list[dict] = Field(default_factory=list)
    scene_registry: list[dict] = Field(default_factory=list)
    level_maps: list[dict] = Field(default_factory=list)
    implementation_roadmap: list[dict] = Field(default_factory=list)


class AssetSpec(BaseModel):
    """Specification for a single game asset to generate."""

    key: str = Field(description="Asset identifier, e.g. 'player_sprite'")
    type: Literal["image", "audio", "video", "tileset", "spritesheet"] = "image"
    description: str = ""
    size: str = "64x64"
    format: str = "png"
    output_path: str = ""


class GeneratedAsset(BaseModel):
    """Result of generating an asset."""

    spec: AssetSpec
    output_path: Path
    generation_time_ms: int = 0
    provider: str = ""


class GameResult(BaseModel):
    """Final result of a game generation pipeline run."""

    success: bool = False
    project_dir: Path = Field(default_factory=Path)
    gdd: GameDesignDocument | None = None
    assets: list[GeneratedAsset] = Field(default_factory=list)
    debug_trace: object | None = None
    duration_ms: int = 0
    error: str | None = None
