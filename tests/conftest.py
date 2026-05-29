"""Shared test fixtures for all OpenGame tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from opengame.config.models import LlmConfig, OpenGameConfig
from opengame.core.llm_client import LlmResponse
from opengame.core.tool_registry import ToolRegistry


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Temporary directory for file-based tests."""
    return tmp_path


@pytest.fixture
def mock_llm_client() -> AsyncMock:
    """Mock LLM client that returns empty responses."""
    client = AsyncMock()
    client.generate.return_value = LlmResponse(content="Mock response", model="mock-model")
    client.stream_generate.return_value = AsyncMock()
    return client


@pytest.fixture
def mock_tool_registry() -> ToolRegistry:
    """Tool registry pre-populated with a simple test tool."""
    registry = ToolRegistry()

    @registry.tool(name="echo", description="Echo back the input")
    async def echo(message: str) -> str:
        return message

    return registry


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal project directory structure for testing."""
    project = tmp_path / "test-project"
    project.mkdir()

    # Create some files
    (project / "main.ts").write_text("console.log('hello');\n")
    (project / "package.json").write_text(json.dumps({"name": "test-game", "version": "1.0.0"}))
    (project / "src").mkdir()
    (project / "src" / "Game.ts").write_text("class Game {}\n")
    (project / "src" / "scenes").mkdir(parents=True)
    (project / "src" / "scenes" / "MainScene.ts").write_text("class MainScene extends Phaser.Scene {}\n")

    return project


@pytest.fixture
def default_config() -> OpenGameConfig:
    """Default OpenGameConfig with all defaults."""
    return OpenGameConfig()


@pytest.fixture
def custom_config() -> OpenGameConfig:
    """OpenGameConfig with custom LLM settings."""
    return OpenGameConfig(
        llm=LlmConfig(provider="anthropic", model="claude-sonnet-4"),
        approval_mode="yolo",
    )


@pytest.fixture
def empty_library(tmp_path: Path) -> Path:
    """Empty template library directory."""
    lib = tmp_path / "template-library"
    lib.mkdir()
    return lib


@pytest.fixture
def populated_library(tmp_path: Path) -> Path:
    """Template library with some sample families."""
    lib = tmp_path / "template-library"
    lib.mkdir()

    # Create a manifest
    manifest = {
        "version": "0.6.0",
        "families": {
            "platformer": {
                "path": "families/platformer.json",
                "stability": 0.8,
                "sample_count": 5,
            },
        },
    }
    (lib / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (lib / "families").mkdir()

    family_data = {
        "name": "platformer",
        "archetype": "platformer",
        "physics_profile": {
            "has_gravity": True,
            "perspective": "side",
            "movement_type": "continuous",
        },
        "files": [],
        "stability": 0.8,
        "sample_count": 5,
    }
    (lib / "families" / "platformer.json").write_text(json.dumps(family_data, indent=2))

    return lib


@pytest.fixture
def empty_protocol(tmp_path: Path) -> Path:
    """Empty debug protocol directory."""
    proto = tmp_path / "debug-protocol"
    proto.mkdir()
    return proto


@pytest.fixture
def sample_snapshot(sample_project: Path) -> dict:
    """Dict representation of a project snapshot for testing."""
    return {
        "project_path": str(sample_project),
        "files": [
            {
                "relative_path": "main.ts",
                "content": "console.log('hello');",
                "extension": ".ts",
            }
        ],
        "file_tree": ["main.ts", "package.json", "src/Game.ts", "src/scenes/MainScene.ts"],
        "code_summary": "A simple test project",
    }
