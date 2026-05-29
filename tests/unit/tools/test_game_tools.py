"""Tests for game-specific tools."""

import json

import pytest

from opengame.core.tool_registry import ToolRegistry
from opengame.tools.game_tools import _classify_prompt, register_game_tools


class TestClassifyPrompt:
    def test_classify_platformer(self) -> None:
        result = _classify_prompt("Build a platformer game with jumping and gravity")
        assert result["archetype"] == "platformer"
        assert result["physics_profile"]["has_gravity"] is True

    def test_classify_top_down(self) -> None:
        result = _classify_prompt("A top-down shooter with bullet hell mechanics")
        assert result["archetype"] == "top_down"
        assert result["physics_profile"]["has_gravity"] is False

    def test_classify_grid_logic(self) -> None:
        result = _classify_prompt("A Snake game on a grid with tiles")
        assert result["archetype"] == "grid_logic"
        assert result["physics_profile"]["movement_type"] == "grid"

    def test_classify_tower_defense(self) -> None:
        result = _classify_prompt("A tower defense game with waves of enemies")
        assert result["archetype"] == "tower_defense"

    def test_classify_ui_heavy(self) -> None:
        result = _classify_prompt("An idle clicker incremental game")
        assert result["archetype"] == "ui_heavy"

    def test_classify_defaults_to_platformer(self) -> None:
        result = _classify_prompt("A completely random unknown game concept")
        assert result["archetype"] == "platformer"
        assert result["confidence"] < 0.5


class TestGameTools:
    @pytest.fixture
    def registry(self) -> ToolRegistry:
        reg = ToolRegistry()
        register_game_tools(reg)
        return reg

    @pytest.mark.asyncio
    async def test_classify_game_type_tool(self, registry: ToolRegistry) -> None:
        result = await registry.execute("classify_game_type", {"prompt": "Build a Snake game"})
        assert result.success
        data = json.loads(result.output)
        assert "archetype" in data
        assert "confidence" in data

    @pytest.mark.asyncio
    async def test_generate_tilemap(self, registry: ToolRegistry, tmp_path) -> None:
        ascii_map = "###\n#.#\n###"
        tile_mapping = json.dumps({"#": 1, ".": 0})
        output = tmp_path / "tilemap.json"

        result = await registry.execute("generate_tilemap", {
            "ascii_map": ascii_map,
            "tile_mapping": tile_mapping,
            "output_path": str(output),
        })
        assert result.success
        assert output.exists()
        data = json.loads(output.read_text())
        assert data["width"] == 3
        assert data["height"] == 3

    @pytest.mark.asyncio
    async def test_generate_game_assets_stub(self, registry: ToolRegistry) -> None:
        result = await registry.execute("generate_game_assets", {
            "assets": json.dumps([{"type": "image", "name": "player"}])
        })
        assert result.success
        assert "placeholder" in result.output.lower()
