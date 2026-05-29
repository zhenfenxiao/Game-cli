"""Tests for Pydantic configuration models."""

import json

from opengame.config.models import (
    AssetProviderConfig,
    GameSkillConfig,
    LlmConfig,
    OpenGameConfig,
)


class TestLlmConfig:
    """Tests for LlmConfig."""

    def test_default_values(self) -> None:
        """Default config has sensible values."""
        config = LlmConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.timeout == 120

    def test_custom_values(self) -> None:
        """Custom values override defaults."""
        config = LlmConfig(
            provider="anthropic",
            model="claude-sonnet-4",
            temperature=0.3,
        )
        assert config.provider == "anthropic"
        assert config.model == "claude-sonnet-4"
        assert config.temperature == 0.3

    def test_empty_api_key_set_to_none(self) -> None:
        """Empty string API key is treated as None."""
        config = LlmConfig(api_key="   ")
        assert config.api_key is None

    def test_valid_api_key_preserved(self) -> None:
        """Valid API key is preserved."""
        config = LlmConfig(api_key="sk-test123")
        assert config.api_key == "sk-test123"

    def test_json_roundtrip(self) -> None:
        """Config can be serialized and deserialized."""
        original = LlmConfig(model="gpt-4o-mini", temperature=0.5)
        json_str = original.model_dump_json()
        restored = LlmConfig.model_validate_json(json_str)
        assert restored.model == original.model
        assert restored.temperature == original.temperature


class TestOpenGameConfig:
    """Tests for the top-level OpenGameConfig."""

    def test_default_config(self) -> None:
        """Default config creates all nested objects."""
        config = OpenGameConfig()
        assert config.llm.provider == "openai"
        assert config.game_skill.max_debug_iterations == 20
        assert config.approval_mode == "auto-edit"

    def test_json_roundtrip(self) -> None:
        """Full config roundtrip through JSON."""
        original = OpenGameConfig()
        json_str = original.model_dump_json()
        restored = OpenGameConfig.model_validate_json(json_str)
        assert restored == original

    def test_partial_override(self) -> None:
        """Partial JSON can be loaded and merged with defaults."""
        data = {
            "llm": {"model": "gpt-4o-mini"},
            "approval_mode": "yolo",
        }
        config = OpenGameConfig.model_validate(data)
        assert config.llm.model == "gpt-4o-mini"
        assert config.llm.provider == "openai"  # unchanged default
        assert config.approval_mode == "yolo"


class TestAssetProviderConfig:
    """Tests for AssetProviderConfig."""

    def test_all_fields_optional(self) -> None:
        """Can create with no arguments."""
        config = AssetProviderConfig()
        assert config.provider == ""
        assert config.api_key is None


class TestGameSkillConfig:
    """Tests for GameSkillConfig."""

    def test_default_paths_are_paths(self) -> None:
        """Directory fields are Path objects."""
        from pathlib import Path

        config = GameSkillConfig()
        assert isinstance(config.templates_dir, Path)
        assert isinstance(config.docs_dir, Path)
