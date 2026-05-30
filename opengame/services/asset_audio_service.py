"""AssetAudioService — audio generation via provider APIs.

Supported providers:
- openai-compat: OpenAI TTS API (tts-1 / tts-1-hd)
- tongyi: Alibaba Tongyi (stub)
- doubao: ByteDance Doubao (stub)

Also supports LLM-driven ABC music notation generation for
background music, rendered locally via symusic (if available)
or a procedural fallback.
"""

from __future__ import annotations

from pathlib import Path

import aiofiles
import httpx

from opengame.config.models import AssetProviderConfig
from opengame.utils.errors import AssetError


class AssetAudioService:
    """Audio generation via provider HTTP APIs.

    Generates both background music (BGM) and sound effects (SFX).
    """

    def __init__(self, config: AssetProviderConfig | None) -> None:
        self.config = config
        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate(
        self,
        prompt: str,
        output_path: Path,
        duration: int | None = None,
    ) -> Path:
        """Generate audio from a text prompt.

        Args:
            prompt: Text description of the desired audio.
            output_path: Where to save the audio file.
            duration: Target duration in seconds (for BGM).

        Returns:
            Path to the generated audio file.
        """
        if not self.config:
            raise AssetError("Audio provider not configured", recoverable=False)

        provider = self.config.provider.lower()

        if provider in ("openai", "openai-compat"):
            audio_data = await self._generate_openai(prompt)
        elif provider == "tongyi":
            audio_data = await self._generate_tongyi(prompt, duration)
        elif provider == "doubao":
            audio_data = await self._generate_doubao(prompt)
        else:
            raise AssetError(f"Unknown audio provider: {provider}", recoverable=False)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(output_path, "wb") as f:
            await f.write(audio_data)

        return output_path

    # --- Provider implementations ---

    async def _generate_openai(self, prompt: str) -> bytes:
        """Generate audio via OpenAI TTS API.

        Uses POST /audio/speech with tts-1 model.
        DeepSeek does NOT support this endpoint, so this may fail
        if using DeepSeek as audio provider.
        """
        base_url = self.config.base_url or "https://api.openai.com/v1"
        api_url = f"{base_url}/audio/speech"

        payload = {
            "model": self.config.model or "tts-1",
            "input": prompt,
            "voice": "alloy",
            "response_format": "mp3",
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        response = await self.client.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.content

    async def _generate_tongyi(self, prompt: str, duration: int | None) -> bytes:
        """Generate audio via Tongyi API."""
        raise NotImplementedError("Tongyi audio generation not yet implemented")

    async def _generate_doubao(self, prompt: str) -> bytes:
        """Generate audio via Doubao API."""
        raise NotImplementedError("Doubao audio generation not yet implemented")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
