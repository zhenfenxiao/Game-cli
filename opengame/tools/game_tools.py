"""Game-specific tools: classify_game_type, generate_gdd, generate_game_assets, generate_tilemap.

Some tools require LLM client injection for content generation.
"""

from __future__ import annotations

import json
from typing import Any

import aiofiles

from opengame.core.llm_client import BaseLlmClient
from opengame.core.tool_registry import ToolParameter, ToolRegistry

# Keyword-based classifier patterns for 5 game archetypes
ARCHETYPE_PATTERNS: dict[str, list[str]] = {
    "platformer": [
        "platform", "jump", "gravity", "side-scroll", "side view",
        "runner", "mario", "platformer", "ledge", "falling",
    ],
    "top_down": [
        "top-down", "top down", "topdown", "bird's eye", "overhead",
        "zelda-like", "rpg", "shooter", "bullet hell",
    ],
    "grid_logic": [
        "grid", "puzzle", "match-3", "match three", "tetris",
        "snake", "sudoku", "2048", "minesweeper", "tile", "board",
        "chess", "checkers", "turn-based", "turn based",
    ],
    "tower_defense": [
        "tower defense", "tower defence", "tower-defense", "td",
        "wave", "path", "enemy wave", "defend", "turrets",
    ],
    "ui_heavy": [
        "idle", "clicker", "incremental", "management", "sim",
        "tycoon", "visual novel", "text-based", "text based",
        "card game", "menu", "ui", "quiz", "trivia",
    ],
}


def _classify_prompt(prompt: str) -> dict[str, Any]:
    """Classify a game prompt using keyword-based heuristics.

    Args:
        prompt: Natural language game description.

    Returns:
        Dict with archetype, confidence, and physics_profile.
    """
    prompt_lower = prompt.lower()
    scores: dict[str, int] = {}

    for archetype, keywords in ARCHETYPE_PATTERNS.items():
        score = sum(1 for kw in keywords if kw in prompt_lower)
        scores[archetype] = score

    # Pick the highest-scoring archetype
    best = max(scores, key=scores.get)
    best_score = scores[best]

    if best_score == 0:
        best = "platformer"  # Default
        confidence = 0.3
    else:
        total = sum(scores.values()) or 1
        confidence = min(0.9, best_score / max(1, total / len(scores)))

    # Build physics profile
    physics_profiles = {
        "platformer": {"has_gravity": True, "perspective": "side", "movement_type": "continuous"},
        "top_down": {"has_gravity": False, "perspective": "top_down", "movement_type": "continuous"},
        "grid_logic": {"has_gravity": False, "perspective": "top_down", "movement_type": "grid"},
        "tower_defense": {"has_gravity": False, "perspective": "top_down", "movement_type": "path"},
        "ui_heavy": {"has_gravity": False, "perspective": "none", "movement_type": "ui_only"},
    }

    return {
        "archetype": best,
        "confidence": round(confidence, 2),
        "physics_profile": physics_profiles[best],
        "keyword_matches": scores[best],
    }


def register_game_tools(
    registry: ToolRegistry,
    llm_client: BaseLlmClient | None = None,
) -> None:
    """Register game-specific tools.

    Args:
        registry: ToolRegistry to register tools with.
        llm_client: Optional LLM client for GDD generation (closure-injected).
    """

    # --- classify_game_type ---
    @registry.tool(
        name="classify_game_type",
        description="Classify a game description into one of 5 archetypes based on "
        "physics signals (gravity, perspective, movement type).",
        parameters=[
            ToolParameter(
                name="prompt",
                type="string",
                description="The natural language game description to classify",
                required=True,
            ),
        ],
    )
    async def classify_game_type(prompt: str) -> str:
        result = _classify_prompt(prompt)
        return json.dumps(result, ensure_ascii=False, indent=2)

    # --- generate_gdd ---
    if llm_client:

        async def generate_gdd(raw_user_requirement: str, archetype: str) -> str:
            """Generate a complete Game Design Document using the LLM."""
            prompt = f"""You are a game designer. Create a comprehensive Game Design Document (GDD) based on the following requirements.

Game Type: {archetype}
Requirements: {raw_user_requirement}

The GDD must have these 6 sections:
1. Game Overview (title, concept, target audience)
2. Core Mechanics (controls, physics, scoring, game loop)
3. Level Design (layout, progression, difficulty curve)
4. Art and Audio (visual style, color palette, sound effects, music)
5. Technical Specs (resolution 800x600, Phaser 3, TypeScript, performance targets)
6. Implementation Plan (development phases, key milestones)

Format the output as a well-structured Markdown document."""
            try:
                response = await llm_client.generate(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=2000,
                )
                return response.content or "GDD generation returned empty response."
            except Exception as e:
                return f"Error generating GDD: {e}"

        registry.register(
            name="generate_gdd",
            func=generate_gdd,
            description="Generate a complete Game Design Document (GDD) with 6 sections: "
            "overview, mechanics, level design, art/audio, technical specs, and implementation plan.",
            parameters=[
                ToolParameter(
                    name="raw_user_requirement",
                    type="string",
                    description="The user's original game requirements in natural language",
                    required=True,
                ),
                ToolParameter(
                    name="archetype",
                    type="string",
                    description="The game archetype from classify_game_type",
                    required=True,
                ),
            ],
        )

    # --- generate_game_assets ---
    @registry.tool(
        name="generate_game_assets",
        description="Generate image, audio, and video assets for a game. "
        "This is a placeholder — full asset pipeline will be implemented in Phase 4.",
        parameters=[
            ToolParameter(
                name="assets",
                type="string",
                description="JSON string of asset specifications with type, name, and description",
                required=True,
            ),
        ],
    )
    async def generate_game_assets(assets: str) -> str:
        try:
            asset_list = json.loads(assets) if isinstance(assets, str) else assets
            count = len(asset_list) if isinstance(asset_list, list) else 0
        except json.JSONDecodeError:
            count = 0

        return json.dumps({
            "status": "placeholder",
            "message": f"Asset generation is not yet implemented. {count} assets requested. "
            "Full asset pipeline coming in Phase 4.",
            "assets_requested": count,
        }, ensure_ascii=False, indent=2)

    # --- generate_tilemap ---
    @registry.tool(
        name="generate_tilemap",
        description="Convert an ASCII art map into a Phaser-compatible tilemap JSON file.",
        parameters=[
            ToolParameter(
                name="ascii_map",
                type="string",
                description="ASCII representation of the map (one character per tile)",
                required=True,
            ),
            ToolParameter(
                name="tile_mapping",
                type="string",
                description="JSON mapping of ASCII characters to tile IDs, e.g. "
                "{\"#\": 1, \".\": 0, \"P\": 2}",
                required=True,
            ),
            ToolParameter(
                name="output_path",
                type="string",
                description="Path to write the tilemap JSON file",
                required=True,
            ),
        ],
    )
    async def generate_tilemap(ascii_map: str, tile_mapping: str, output_path: str) -> str:
        try:
            mapping = json.loads(tile_mapping)
        except json.JSONDecodeError as e:
            return f"Error parsing tile_mapping JSON: {e}"

        lines = ascii_map.strip().split("\n")
        height = len(lines)
        width = max(len(line) for line in lines) if lines else 0

        # Build the tile data array
        tile_data: list[list[int]] = []
        for line in lines:
            row: list[int] = []
            for char in line:
                row.append(mapping.get(char, 0))
            # Pad shorter rows
            while len(row) < width:
                row.append(0)
            tile_data.append(row)

        tilemap = {
            "height": height,
            "width": width,
            "tileheight": 32,
            "tilewidth": 32,
            "layers": [
                {
                    "name": "ground",
                    "data": tile_data,
                    "height": height,
                    "width": width,
                },
            ],
        }

        try:
            import os
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            async with aiofiles.open(output_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(tilemap, ensure_ascii=False, indent=2))
            return json.dumps({
                "status": "created",
                "path": output_path,
                "dimensions": f"{width}x{height}",
                "tile_count": width * height,
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Error writing tilemap: {e}"
