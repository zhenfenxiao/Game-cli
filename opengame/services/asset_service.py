"""AssetService router — routes asset generation to modality-specific services.

Each modality (image/audio/video) is independently configured, allowing
mixing providers (e.g., Tongyi for images, OpenAI for audio).
"""

from __future__ import annotations

from pathlib import Path

from opengame.config.models import OpenGameConfig
from opengame.services.asset_audio_service import AssetAudioService
from opengame.services.asset_image_service import AssetImageService
from opengame.services.asset_video_service import AssetVideoService
from opengame.utils.errors import AssetError


class AssetService:
    """Routes asset generation requests to the appropriate modality service.

    Usage:
        service = AssetService(config)
        image_path = await service.generate_image(
            prompt="player sprite",
            output_path=Path("./assets/player.png"),
        )
    """

    def __init__(self, config: OpenGameConfig) -> None:
        self.image_service = AssetImageService(config.image) if config.image else None
        self.audio_service = AssetAudioService(config.audio) if config.audio else None
        self.video_service = AssetVideoService(config.video) if config.video else None

    async def generate_image(
        self,
        prompt: str,
        output_path: Path,
        style: str = "pixel_art",
        size: str = "1024x1024",
    ) -> Path:
        """Generate an image asset.

        Args:
            prompt: Text description of the desired image.
            output_path: Where to save the generated image.
            style: Art style hint (pixel_art, realistic, cartoon, etc.).
            size: Image dimensions.

        Returns:
            Path to the generated image file.

        Raises:
            AssetError: If no image provider is configured.
        """
        if not self.image_service:
            raise AssetError("No image provider configured", recoverable=False)
        return await self.image_service.generate(prompt, output_path, style, size)

    async def generate_audio(
        self,
        prompt: str,
        output_path: Path,
        duration: int | None = None,
    ) -> Path:
        """Generate an audio asset.

        Args:
            prompt: Text description of the desired audio.
            output_path: Where to save the audio file.
            duration: Target duration in seconds (for BGM).

        Returns:
            Path to the generated audio file.

        Raises:
            AssetError: If no audio provider is configured.
        """
        if not self.audio_service:
            raise AssetError("No audio provider configured", recoverable=False)
        return await self.audio_service.generate(prompt, output_path, duration)

    async def generate_video(
        self,
        prompt: str,
        output_path: Path,
        duration: int = 5,
    ) -> Path:
        """Generate a video asset.

        Args:
            prompt: Text description of the desired video.
            output_path: Where to save the video file.
            duration: Target duration in seconds.

        Returns:
            Path to the generated video file.

        Raises:
            AssetError: If no video provider is configured.
        """
        if not self.video_service:
            raise AssetError("No video provider configured", recoverable=False)
        return await self.video_service.generate(prompt, output_path, duration)
