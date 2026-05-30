# 11 — Configuration System

The configuration system manages settings through a layered priority model: CLI flags override environment variables, which override project settings, which override user settings, which override built-in defaults.

## 11.1 Configuration Layers

```
┌─────────────────────────────────────┐
│  Layer 1: CLI Flags                 │  Highest priority
│  (--model, --yolo, -p, etc.)        │
├─────────────────────────────────────┤
│  Layer 2: Environment Variables     │
│  (OPENAI_API_KEY, etc.)             │
├─────────────────────────────────────┤
│  Layer 3: Project Settings          │
│  (.opengame/settings.json)          │
├─────────────────────────────────────┤
│  Layer 4: User Settings             │
│  (~/.opengame/settings.json)        │
├─────────────────────────────────────┤
│  Layer 5: Built-in Defaults         │  Lowest priority
│  (defined in Pydantic models)       │
└─────────────────────────────────────┘
```

## 11.2 Configuration Files

### User Settings

Path: `~/.opengame/settings.json`

```json
{
  "llm": {
    "provider": "openai",
    "api_key": "sk-...",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 4096,
    "timeout": 120
  },
  "image": {
    "provider": "tongyi",
    "api_key": "sk-...",
    "model": "wanx-v1"
  },
  "audio": {
    "provider": "openai",
    "api_key": "sk-...",
    "model": "tts-1"
  },
  "video": {
    "provider": "doubao",
    "api_key": "sk-..."
  },
  "reasoning": {
    "provider": "openai",
    "api_key": "sk-...",
    "model": "o3-mini"
  },
  "game_skill": {
    "templates_dir": "/path/to/templates",
    "docs_dir": "/path/to/docs",
    "max_debug_iterations": 20,
    "evolve_after_debug": true
  },
  "approval_mode": "auto-edit",
  "verbose": false,
  "telemetry": true
}
```

### Project Settings

Path: `.opengame/settings.json` (in current working directory)

Same schema as user settings. Overrides user settings for the current project.

## 11.3 Environment Variables

| Variable | Maps To | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | `llm.api_key` | Primary LLM API key |
| `OPENAI_BASE_URL` | `llm.base_url` | LLM API base URL |
| `OPENAI_MODEL` | `llm.model` | Default LLM model |
| `OPENGAME_IMAGE_PROVIDER` | `image.provider` | Image generation provider |
| `OPENGAME_IMAGE_API_KEY` | `image.api_key` | Image API key |
| `OPENGAME_IMAGE_BASE_URL` | `image.base_url` | Image API base URL |
| `OPENGAME_IMAGE_MODEL` | `image.model` | Image generation model |
| `OPENGAME_AUDIO_PROVIDER` | `audio.provider` | Audio generation provider |
| `OPENGAME_AUDIO_API_KEY` | `audio.api_key` | Audio API key |
| `OPENGAME_VIDEO_PROVIDER` | `video.provider` | Video generation provider |
| `OPENGAME_VIDEO_API_KEY` | `video.api_key` | Video API key |
| `OPENGAME_REASONING_PROVIDER` | `reasoning.provider` | Reasoning model provider |
| `OPENGAME_REASONING_API_KEY` | `reasoning.api_key` | Reasoning API key |
| `GAME_TEMPLATES_DIR` | `game_skill.templates_dir` | Template directory |
| `GAME_DOCS_DIR` | `game_skill.docs_dir` | Documentation directory |

## 11.4 Config Loader

```python
# cli/config_loader.py
import os
import json
from pathlib import Path
from typing import Any


class ConfigLoader:
    """
    Load configuration from all sources and merge them.

    Priority (highest to lowest):
    1. CLI flags
    2. Environment variables
    3. Project settings (.opengame/settings.json)
    4. User settings (~/.opengame/settings.json)
    5. Built-in defaults
    """

    USER_SETTINGS_DIR = Path.home() / ".opengame"
    PROJECT_SETTINGS_DIR = Path(".opengame")
    USER_SETTINGS_FILE = USER_SETTINGS_DIR / "settings.json"
    PROJECT_SETTINGS_FILE = PROJECT_SETTINGS_DIR / "settings.json"

    def __init__(self):
        self.cli_overrides: dict[str, Any] = {}

    def set_cli_override(self, key: str, value: Any) -> None:
        """Set a CLI override value."""
        self._set_nested(self.cli_overrides, key, value)

    def load(self) -> OpenGameConfig:
        """Load and merge all configuration sources."""
        # Start with defaults (Pydantic handles this)
        config = OpenGameConfig()

        # Layer 4: User settings
        user_settings = self._load_json_file(self.USER_SETTINGS_FILE)
        if user_settings:
            config = self._merge_settings(config, user_settings)

        # Layer 3: Project settings
        project_settings = self._load_json_file(self.PROJECT_SETTINGS_FILE)
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

    def _load_json_file(self, path: Path) -> dict | None:
        """Load a JSON settings file."""
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _load_from_env(self) -> dict:
        """Load configuration from environment variables."""
        settings: dict[str, Any] = {}

        # LLM settings
        if os.getenv("OPENAI_API_KEY"):
            settings.setdefault("llm", {})["api_key"] = os.getenv("OPENAI_API_KEY")
        if os.getenv("OPENAI_BASE_URL"):
            settings.setdefault("llm", {})["base_url"] = os.getenv("OPENAI_BASE_URL")
        if os.getenv("OPENAI_MODEL"):
            settings.setdefault("llm", {})["model"] = os.getenv("OPENAI_MODEL")

        # Image settings
        for key in ["PROVIDER", "API_KEY", "BASE_URL", "MODEL"]:
            env_val = os.getenv(f"OPENGAME_IMAGE_{key}")
            if env_val:
                settings.setdefault("image", {})[key.lower()] = env_val

        # Audio settings
        for key in ["PROVIDER", "API_KEY", "BASE_URL", "MODEL"]:
            env_val = os.getenv(f"OPENGAME_AUDIO_{key}")
            if env_val:
                settings.setdefault("audio", {})[key.lower()] = env_val

        # Video settings
        for key in ["PROVIDER", "API_KEY", "BASE_URL", "MODEL"]:
            env_val = os.getenv(f"OPENGAME_VIDEO_{key}")
            if env_val:
                settings.setdefault("video", {})[key.lower()] = env_val

        # Reasoning settings
        for key in ["PROVIDER", "API_KEY", "BASE_URL", "MODEL"]:
            env_val = os.getenv(f"OPENGAME_REASONING_{key}")
            if env_val:
                settings.setdefault("reasoning", {})[key.lower()] = env_val

        # Game skill settings
        if os.getenv("GAME_TEMPLATES_DIR"):
            settings.setdefault("game_skill", {})["templates_dir"] = os.getenv("GAME_TEMPLATES_DIR")
        if os.getenv("GAME_DOCS_DIR"):
            settings.setdefault("game_skill", {})["docs_dir"] = os.getenv("GAME_DOCS_DIR")

        return settings

    def _merge_settings(self, config: OpenGameConfig, overrides: dict) -> OpenGameConfig:
        """Merge override dict into existing config."""
        # Convert config to dict, merge, then recreate
        current = config.model_dump()
        merged = self._deep_merge(current, overrides)
        return OpenGameConfig(**merged)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Recursively merge override into base."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _set_nested(self, d: dict, key: str, value: Any) -> None:
        """Set a nested value using dot notation."""
        parts = key.split(".")
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = value

    def ensure_directories(self) -> None:
        """Create settings directories if they don't exist."""
        self.USER_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        self.PROJECT_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

    def create_user_settings_template(self) -> Path:
        """Create a user settings file with template content."""
        self.USER_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

        template = {
            "llm": {
                "provider": "openai",
                "api_key": "your-api-key-here",
                "model": "gpt-4o"
            },
            "image": {
                "provider": "tongyi",
                "api_key": "your-image-api-key"
            }
        }

        with open(self.USER_SETTINGS_FILE, "w") as f:
            json.dump(template, f, indent=2)

        return self.USER_SETTINGS_FILE
```

## 11.5 CLI Configuration Commands

```python
# cli/commands/config.py
import typer
import json

app = typer.Typer()


@app.command()
def show(
    raw: bool = typer.Option(False, "--raw", help="Show raw config values"),
):
    """Show the effective configuration (merged from all sources)."""
    loader = ConfigLoader()
    config = loader.load()

    if raw:
        print(json.dumps(config.model_dump(), indent=2))
    else:
        print("# OpenGame Configuration")
        print()
        print(f"LLM Provider: {config.llm.provider}")
        print(f"LLM Model: {config.llm.model}")
        print(f"LLM Base URL: {config.llm.base_url}")
        print(f"Approval Mode: {config.approval_mode}")
        print()
        print("Asset Providers:")
        for name, provider in [
            ("Image", config.image),
            ("Audio", config.audio),
            ("Video", config.video),
            ("Reasoning", config.reasoning),
        ]:
            status = provider.provider if provider else "not configured"
            print(f"  {name}: {status}")
        print()
        print("Game Skill:")
        print(f"  Templates: {config.game_skill.templates_dir}")
        print(f"  Docs: {config.game_skill.docs_dir}")
        print(f"  Max Debug Iterations: {config.game_skill.max_debug_iterations}")


@app.command()
def init():
    """Create a user settings file with template content."""
    loader = ConfigLoader()
    loader.ensure_directories()
    path = loader.create_user_settings_template()
    print(f"Created settings template at: {path}")
    print("Edit this file to add your API keys.")


@app.command()
def validate():
    """Validate the current configuration."""
    loader = ConfigLoader()
    config = loader.load()

    errors = []
    warnings = []

    # Validate LLM config
    if not config.llm.api_key:
        errors.append("LLM API key is not configured (OPENAI_API_KEY)")

    # Check provider connectivity (optional)
    print("# Configuration Validation")
    print()

    if errors:
        print("Errors:")
        for e in errors:
            print(f"  [X] {e}")

    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  [!] {w}")

    if not errors and not warnings:
        print("Configuration is valid.")
```

## 11.6 Settings JSON Schema

```python
# config/models.py (excerpt)

# The complete schema is defined in 03-data-models.md
# This section documents the on-disk JSON format

"""
settings.json format:

{
  "llm": {
    "provider": "openai" | "anthropic" | "dashscope" | "deepseek" | "openrouter",
    "api_key": "string (optional — can use env var)",
    "base_url": "string (optional)",
    "model": "string",
    "temperature": 0.0-2.0,
    "max_tokens": integer,
    "timeout": integer (seconds)
  },
  "image": {
    "provider": "tongyi" | "doubao" | "openai-compat" | "fal",
    "api_key": "string",
    "base_url": "string (optional)",
    "model": "string (optional)"
  },
  "audio": {
    "provider": "string",
    "api_key": "string",
    "base_url": "string (optional)",
    "model": "string (optional)"
  },
  "video": {
    "provider": "string",
    "api_key": "string",
    "base_url": "string (optional)",
    "model": "string (optional)"
  },
  "reasoning": {
    "provider": "string",
    "api_key": "string",
    "base_url": "string (optional)",
    "model": "string (optional)"
  },
  "game_skill": {
    "templates_dir": "path string",
    "docs_dir": "path string",
    "archetypes_dir": "path string",
    "library_output_dir": "path string",
    "protocol_output_dir": "path string",
    "max_debug_iterations": integer,
    "evolve_after_debug": boolean
  },
  "approval_mode": "ask" | "auto-edit" | "yolo",
  "sandbox": boolean,
  "verbose": boolean,
  "telemetry": boolean
}
"""
```

## 11.7 Environment Variable to Config Mapping

```
OPENAI_API_KEY              →  llm.api_key
OPENAI_BASE_URL             →  llm.base_url
OPENAI_MODEL                →  llm.model

OPENGAME_IMAGE_PROVIDER     →  image.provider
OPENGAME_IMAGE_API_KEY      →  image.api_key
OPENGAME_IMAGE_BASE_URL     →  image.base_url
OPENGAME_IMAGE_MODEL        →  image.model

OPENGAME_AUDIO_PROVIDER     →  audio.provider
OPENGAME_AUDIO_API_KEY      →  audio.api_key
OPENGAME_AUDIO_BASE_URL     →  audio.base_url
OPENGAME_AUDIO_MODEL        →  audio.model

OPENGAME_VIDEO_PROVIDER     →  video.provider
OPENGAME_VIDEO_API_KEY      →  video.api_key
OPENGAME_VIDEO_BASE_URL     →  video.base_url
OPENGAME_VIDEO_MODEL        →  video.model

OPENGAME_REASONING_PROVIDER  →  reasoning.provider
OPENGAME_REASONING_API_KEY   →  reasoning.api_key
OPENGAME_REASONING_BASE_URL  →  reasoning.base_url
OPENGAME_REASONING_MODEL     →  reasoning.model

GAME_TEMPLATES_DIR          →  game_skill.templates_dir
GAME_DOCS_DIR               →  game_skill.docs_dir
```
