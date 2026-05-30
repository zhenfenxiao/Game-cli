"""Tests for ConfigLoader with multi-source merging."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from opengame.cli.config_loader import ConfigLoader
from opengame.config.constants import PROJECT_SETTINGS_FILE, USER_SETTINGS_FILE

# Env vars that .env might set — clear them for clean test runs
_ENV_VARS_TO_CLEAR = [
    "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL",
    "OPENGAME_IMAGE_PROVIDER", "OPENGAME_IMAGE_API_KEY", "OPENGAME_IMAGE_BASE_URL", "OPENGAME_IMAGE_MODEL",
    "OPENGAME_AUDIO_PROVIDER", "OPENGAME_AUDIO_API_KEY", "OPENGAME_AUDIO_BASE_URL", "OPENGAME_AUDIO_MODEL",
    "OPENGAME_VIDEO_PROVIDER", "OPENGAME_VIDEO_API_KEY",
    "OPENGAME_REASONING_PROVIDER", "OPENGAME_REASONING_API_KEY", "OPENGAME_REASONING_BASE_URL", "OPENGAME_REASONING_MODEL",
    "GAME_TEMPLATES_DIR", "GAME_DOCS_DIR",
]


@pytest.fixture(autouse=True)
def clear_dotenv_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear .env-loaded env vars for clean test runs."""
    for var in _ENV_VARS_TO_CLEAR:
        monkeypatch.delenv(var, raising=False)


class TestConfigLoaderBasics:
    """Tests for basic ConfigLoader behavior."""

    def test_load_returns_default_config(self) -> None:
        """With no overrides, returns the default config."""
        loader = ConfigLoader()
        config = loader.load()
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o"

    def test_cli_override_simple_field(self) -> None:
        """CLI override on a top-level field."""
        loader = ConfigLoader()
        loader.set_cli_override("approval_mode", "yolo")
        config = loader.load()
        assert config.approval_mode == "yolo"

    def test_cli_override_nested_field(self) -> None:
        """CLI override using dot notation for nested fields."""
        loader = ConfigLoader()
        loader.set_cli_override("llm.model", "gpt-4o-mini")
        config = loader.load()
        assert config.llm.model == "gpt-4o-mini"
        # Other fields remain at defaults
        assert config.llm.provider == "openai"

    def test_cli_override_deeply_nested(self) -> None:
        """CLI override for game skill settings."""
        loader = ConfigLoader()
        loader.set_cli_override("game_skill.max_debug_iterations", 50)
        config = loader.load()
        assert config.game_skill.max_debug_iterations == 50


class TestConfigLoaderDeepMerge:
    """Tests for deep merge behavior."""

    def test_deep_merge_preserves_unrelated(self) -> None:
        """Merging nested dicts doesn't overwrite unrelated fields."""
        from opengame.config.models import OpenGameConfig

        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 99}}
        result = ConfigLoader._deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"]["c"] == 99
        assert result["b"]["d"] == 3  # preserved

    def test_deep_merge_adds_new_keys(self) -> None:
        """Override adds keys not present in base."""
        base = {"a": 1}
        override = {"b": 2}
        result = ConfigLoader._deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_deep_merge_overwrites_non_dict(self) -> None:
        """Override overwrites non-dict values entirely."""
        base = {"a": 1}
        override = {"a": 99}
        result = ConfigLoader._deep_merge(base, override)
        assert result["a"] == 99


class TestConfigLoaderEnvVars:
    """Tests for environment variable loading."""

    def test_env_var_in_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables are picked up by config loader."""
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
        monkeypatch.setenv("GAME_DOCS_DIR", "/custom/docs")

        loader = ConfigLoader()
        config = loader.load()
        assert config.llm.model == "gpt-4o-mini"
        assert str(config.game_skill.docs_dir) == "/custom/docs"


class TestConfigLoaderFileSettings:
    """Tests for JSON file settings loading."""

    def test_user_settings_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """User settings file is loaded and merged."""
        user_dir = tmp_path / "user-opengame"
        user_dir.mkdir()
        settings_file = user_dir / "settings.json"
        settings_file.write_text(json.dumps({
            "llm": {"model": "custom-model"},
            "approval_mode": "ask",
        }))

        # Override the user settings path
        import opengame.cli.config_loader as cl
        monkeypatch.setattr(cl, "USER_SETTINGS_FILE", settings_file)

        loader = ConfigLoader()
        config = loader.load()
        assert config.llm.model == "custom-model"
        assert config.approval_mode == "ask"

    def test_project_settings_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Project settings override user settings."""
        user_dir = tmp_path / "user-opengame"
        user_dir.mkdir()
        user_file = user_dir / "settings.json"
        user_file.write_text(json.dumps({"llm": {"model": "user-model"}}))

        proj_dir = tmp_path / "proj-opengame"
        proj_dir.mkdir()
        proj_file = proj_dir / "settings.json"
        proj_file.write_text(json.dumps({"llm": {"model": "project-model"}}))

        import opengame.cli.config_loader as cl
        monkeypatch.setattr(cl, "USER_SETTINGS_FILE", user_file)
        monkeypatch.setattr(cl, "PROJECT_SETTINGS_FILE", proj_file)

        loader = ConfigLoader()
        config = loader.load()
        # Project overrides user
        assert config.llm.model == "project-model"
