"""TilesetProcessor — generate Phaser-compatible tileset metadata.

Processes tileset images and creates JSON metadata for use with
Phaser's tilemap system.
"""

from __future__ import annotations

import json
from pathlib import Path

import aiofiles
from PIL import Image


class TilesetProcessor:
    """Process tileset images into Phaser-compatible JSON metadata.

    Generates tileset.json with dimensions, tile counts, margin/spacing,
    and optional per-tile properties for collision, damage, etc.
    """

    def __init__(self, tile_width: int = 32, tile_height: int = 32) -> None:
        self.tile_width = tile_width
        self.tile_height = tile_height

    async def process(
        self,
        tileset_image: Path,
        output_path: Path,
        tile_properties: dict[int, dict] | None = None,
    ) -> Path:
        """Process a tileset image and generate metadata.

        Args:
            tileset_image: Path to the tileset image.
            output_path: Where to save the tileset JSON.
            tile_properties: Optional per-tile property overrides
                (e.g., {0: {"collides": True}, 5: {"damage": 10}}).

        Returns:
            Path to the generated tileset JSON.
        """
        img = Image.open(tileset_image)
        width, height = img.size

        cols = width // self.tile_width
        rows = height // self.tile_height

        # Build tileset metadata
        tileset_data: dict = {
            "name": tileset_image.stem,
            "image": str(tileset_image.name),
            "tileWidth": self.tile_width,
            "tileHeight": self.tile_height,
            "columns": cols,
            "tileCount": cols * rows,
            "rows": rows,
            "imageWidth": width,
            "imageHeight": height,
            "margin": 0,
            "spacing": 0,
        }

        # Add per-tile properties if provided
        if tile_properties:
            tiles = {}
            for idx, props in tile_properties.items():
                tiles[str(idx)] = props
            tileset_data["tiles"] = tiles

        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(output_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(tileset_data, ensure_ascii=False, indent=2))

        return output_path
