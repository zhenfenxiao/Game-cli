"""AssetVideoService — video/animation generation via provider APIs.

Currently ALL providers are stubs. Video generation APIs (Sora, Veo,
Wan video, Seedance) are either not publicly available or not yet
stable enough for programmatic use.

Used for: cutscenes, title sequences, animated backgrounds.
"""

from __future__ import annotations

from pathlib import Path

import aiofiles
import httpx

from opengame.config.models import AssetProviderConfig
from opengame.utils.errors import AssetError


class AssetVideoService:
    """Video/animation generation (all stubs for now)."""

    def __init__(self, config: AssetProviderConfig | None) -> None:
        self.config = config
        self.client = httpx.AsyncClient(timeout=300.0)

    async def generate(
        self,
        prompt: str,
        output_path: Path,
        duration: int = 5,
    ) -> Path:
        """Generate a video from a text prompt (stub — generates placeholder).

        Args:
            prompt: Text description of the desired video.
            output_path: Where to save the video file.
            duration: Target duration in seconds.

        Returns:
            Path to the generated video file.
        """
        if not self.config:
            raise AssetError("Video provider not configured", recoverable=False)

        provider = self.config.provider.lower()

        if provider in ("openai", "openai-compat"):
            video_url = await self._generate_openai(prompt, duration)
        elif provider == "tongyi":
            video_url = await self._generate_tongyi(prompt, duration)
        elif provider == "doubao":
            video_url = await self._generate_doubao(prompt, duration)
        else:
            raise AssetError(f"Unknown video provider: {provider}", recoverable=False)

        response = await self.client.get(video_url)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(output_path, "wb") as f:
            await f.write(response.content)

        return output_path

    async def _generate_openai(self, prompt: str, duration: int) -> str:
        raise NotImplementedError(
            "OpenAI video (Sora) not yet available via API. "
            "Video generation is expected in Phase 5+."
        )

    async def _generate_tongyi(self, prompt: str, duration: int) -> str:
        raise NotImplementedError("Tongyi video generation not yet implemented")

    async def _generate_doubao(self, prompt: str, duration: int) -> str:
        raise NotImplementedError("Doubao video generation not yet implemented")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
