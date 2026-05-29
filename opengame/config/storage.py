"""Configuration persistence — save and load config to/from JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from opengame.config.models import OpenGameConfig


def save_config(config: OpenGameConfig, path: Path) -> None:
    """Save an OpenGameConfig to a JSON file.

    Creates parent directories if they don't exist.

    Args:
        config: The configuration to save.
        path: Path to write the JSON file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump()
    # Convert Path objects to strings for JSON serialization
    serialized = _prepare_for_json(data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_config(path: Path) -> OpenGameConfig | None:
    """Load an OpenGameConfig from a JSON file.

    Args:
        path: Path to the JSON settings file.

    Returns:
        OpenGameConfig if the file exists and is valid JSON, None otherwise.
    """
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return OpenGameConfig.model_validate(data)
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _prepare_for_json(data: dict) -> dict:
    """Convert non-JSON-serializable values in a dict to JSON-safe types."""
    result: dict = {}
    for key, value in data.items():
        if isinstance(value, Path):
            result[key] = str(value)
        elif isinstance(value, dict):
            result[key] = _prepare_for_json(value)
        elif value is None:
            continue  # Skip None values for cleaner output
        else:
            result[key] = value
    return result
