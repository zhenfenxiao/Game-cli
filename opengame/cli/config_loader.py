"""ConfigLoader — 5-layer configuration merging.

Priority (highest to lowest):
1. CLI flags
2. Environment variables
3. Project settings (.opengame/settings.json)
4. User settings (~/.opengame/settings.json)
5. Built-in defaults
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from opengame.config.constants import (
    PROJECT_SETTINGS_DIR,
    PROJECT_SETTINGS_FILE,
    USER_SETTINGS_DIR,
    USER_SETTINGS_FILE,
)
from opengame.config.models import OpenGameConfig


class ConfigLoader:
    """Load configuration from all sources and merge them.

    Usage:
        loader = ConfigLoader()
        loader.set_cli_override("llm.model", "gpt-4o")
        config = loader.load()
    """

    def __init__(self) -> None:
        self.cli_overrides: dict[str, Any] = {}

    def set_cli_override(self, key: str, value: Any) -> None:
        """Set a CLI override value using dot-notation key.

        Args:
            key: Dotted path like "llm.model" or "approval_mode".
            value: The override value.
        """
        self._set_nested(self.cli_overrides, key, value)

    def load(self, load_dotenv: bool = False) -> OpenGameConfig:
        """Load and merge all configuration sources.

        Args:
            load_dotenv: If True, load .env file before reading env vars.

        Returns:
            Merged OpenGameConfig from all 5 layers.
        """
        # Load .env file into os.environ before reading env vars
        if load_dotenv:
            self._load_dotenv_file()

        # Start with defaults (Layer 5)
        config = OpenGameConfig()

        # Layer 4: User settings (~/.opengame/settings.json)
        user_settings = self._load_json_file(USER_SETTINGS_FILE)
        if user_settings:
            config = self._merge_settings(config, user_settings)

        # Layer 3: Project settings (.opengame/settings.json)
        project_settings = self._load_json_file(PROJECT_SETTINGS_FILE)
        if project_settings:
            config = self._merge_settings(config, project_settings)

        # Layer 2: Environment variables
        env_settings = self._load_from_env()
        if env_settings:
            config = self._merge_settings(config, env_settings)

        # Layer 1: CLI overrides
        if self.cli_overrides:
            config = self._merge_settings(config, self.cli_overrides)

        return config

    def ensure_directories(self) -> None:
        """Create settings directories if they don't exist."""
        USER_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        PROJECT_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

    def create_user_settings_template(self) -> Path:
        """Create a user settings file with template content.

        Returns:
            Path to the created settings file.
        """
        USER_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

        template = {
            "llm": {
                "provider": "openai",
                "api_key": "your-api-key-here",
                "model": "gpt-4o",
            },
            "image": {
                "provider": "tongyi",
                "api_key": "your-image-api-key",
            },
        }

        with open(USER_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
            f.write("\n")

        return USER_SETTINGS_FILE

    # --- Private helpers ---

    def _load_json_file(self, path: Path) -> dict | None:
        """Load a JSON settings file, returning None on any failure."""
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _load_from_env(self) -> dict[str, Any]:
        """Load configuration from environment variables."""
        from opengame.config.constants import ENV_MAPPINGS

        settings: dict[str, Any] = {}

        for env_var, (section, field) in ENV_MAPPINGS.items():
            value = os.getenv(env_var)
            if value:
                settings.setdefault(section, {})[field] = value

        return settings

    def _merge_settings(self, config: OpenGameConfig, overrides: dict) -> OpenGameConfig:
        """Merge override dict into existing config, returning a new config."""
        # Get the current config as a dict (with defaults)
        current = config.model_dump()
        merged = self._deep_merge(current, overrides)
        return OpenGameConfig.model_validate(merged)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge override into base. Returns a new dict."""
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = ConfigLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _load_dotenv_file() -> None:
        """Load .env file from current directory into os.environ.

        Uses python-dotenv to parse and load environment variables.
        Silently skips if the file doesn't exist or dotenv is unavailable.
        """
        try:
            from dotenv import load_dotenv
            env_path = Path(".env")
            if env_path.exists():
                load_dotenv(env_path, override=False)
        except ImportError:
            pass  # python-dotenv not installed

    @staticmethod
    def _set_nested(d: dict, key: str, value: Any) -> None:
        """Set a nested value using dot notation (e.g., 'llm.model')."""
        parts = key.split(".")
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = value
