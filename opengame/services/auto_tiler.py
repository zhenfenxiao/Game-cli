"""AutoTiler — automatically generate tilesets from source images.

Splits a large source image into uniform tiles for use in tilemaps.
Uses PIL (Pillow) for image processing.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


class AutoTiler:
    """Auto-generate tilesets from source images.

    Splits a large image into uniform tiles and outputs a tileset
    image suitable for Phaser tilemap systems.
    """

    def __init__(self, tile_size: int = 32) -> None:
        self.tile_size = tile_size

    async def generate_tileset(
        self,
        source_image: Path,
        output_path: Path,
        tile_width: int | None = None,
        tile_height: int | None = None,
    ) -> Path:
        """Generate a tileset from a source image.

        Args:
            source_image: Path to the source image.
            output_path: Where to save the tileset image.
            tile_width: Width of each tile (default: 32).
            tile_height: Height of each tile (default: 32).

        Returns:
            Path to the generated tileset image.
        """
        tw = tile_width or self.tile_size
        th = tile_height or self.tile_size

        img = Image.open(source_image)
        width, height = img.size

        cols = width // tw
        rows = height // th

        if cols == 0 or rows == 0:
            raise ValueError(
                f"Source image ({width}x{height}) is smaller than tile size ({tw}x{th})"
            )

        # Create tileset (arranges tiles in a single row for Phaser compatibility)
        tileset = Image.new("RGBA", (cols * tw, rows * th))

        for row in range(rows):
            for col in range(cols):
                left = col * tw
                upper = row * th
                right = left + tw
                lower = upper + th

                tile = img.crop((left, upper, right, lower))
                tileset.paste(tile, (col * tw, row * th))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        tileset.save(output_path)

        return output_path
