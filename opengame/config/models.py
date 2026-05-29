"""Pydantic v2 configuration models for OpenGame.

Defines all configuration data models with validation, serialization,
and sensible defaults. These are the central data contract for the framework.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LlmConfig(BaseModel):
    """Configuration for LLM API access."""

    provider: Literal["openai", "anthropic", "dashscope", "deepseek", "openrouter"] = "openai"
    api_key: str | None = None
    base_url: str | None = Field(
        default="https://api.openai.com/v1", description="API base URL"
    )
    model: str = "gpt-4o"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    timeout: int = Field(default=120, ge=1, description="Request timeout in seconds")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """Validate API key format (lenient — allows custom providers)."""
        if v is not None and len(v.strip()) == 0:
            return None
        return v


class AssetProviderConfig(BaseModel):
    """Configuration for a single asset modality provider."""

    provider: str = Field(default="", description="Provider name: tongyi, doubao, openai-compat, fal")
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class GameSkillConfig(BaseModel):
    """Paths and settings for Game Skill."""

    templates_dir: Path = Field(default=Path("agent-test/templates"))
    docs_dir: Path = Field(default=Path("agent-test/docs"))
    archetypes_dir: Path = Field(default=Path("agent-test/templates/modules"))
    library_output_dir: Path = Field(default=Path(".opengame/template-library"))
    protocol_output_dir: Path = Field(default=Path(".opengame/debug-protocol"))
    max_debug_iterations: int = Field(default=20, ge=1, le=100)
    evolve_after_debug: bool = True


class OpenGameConfig(BaseModel):
    """Top-level configuration — loaded from CLI flags, env vars, and settings.json."""

    llm: LlmConfig = Field(default_factory=LlmConfig)
    image: AssetProviderConfig | None = None
    audio: AssetProviderConfig | None = None
    video: AssetProviderConfig | None = None
    reasoning: AssetProviderConfig | None = None
    game_skill: GameSkillConfig = Field(default_factory=GameSkillConfig)
    approval_mode: Literal["ask", "auto-edit", "yolo"] = "auto-edit"
    sandbox: bool = False
    verbose: bool = False
    telemetry: bool = True
