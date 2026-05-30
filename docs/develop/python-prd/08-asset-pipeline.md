# 08 — Asset Pipeline

The Asset Pipeline generates game assets (images, audio, video) from text descriptions using provider APIs.

## 8.1 Architecture

```
AssetService (router)
    │
    ├── AssetImageService ──► Image Provider API (HTTP)
    │
    ├── AssetAudioService ──► Audio Provider API (HTTP)
    │
    └── AssetVideoService ──► Video Provider API (HTTP)
```

## 8.2 Asset Service Router

```python
# services/asset_service.py
from pathlib import Path
from typing import Literal


class AssetService:
    """
    Routes asset generation requests to the appropriate modality service.

    Each modality is configured independently, allowing mixing providers:
    - Image: Tongyi
    - Audio: Doubao
    - Video: OpenAI
    """

    def __init__(self, config: OpenGameConfig):
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
        """Generate an image asset."""
        if not self.image_service:
            raise AssetError("No image provider configured")
        return await self.image_service.generate(prompt, output_path, style, size)

    async def generate_audio(
        self,
        prompt: str,
        output_path: Path,
        duration: int | None = None,
    ) -> Path:
        """Generate an audio asset."""
        if not self.audio_service:
            raise AssetError("No audio provider configured")
        return await self.audio_service.generate(prompt, output_path, duration)

    async def generate_video(
        self,
        prompt: str,
        output_path: Path,
        duration: int = 5,
    ) -> Path:
        """Generate a video asset."""
        if not self.video_service:
            raise AssetError("No video provider configured")
        return await self.video_service.generate(prompt, output_path, duration)
```

## 8.3 Image Generation

```python
# services/asset_image_service.py
import httpx
from pathlib import Path


class AssetImageService:
    """
    Image generation via provider HTTP APIs.

    Supported providers:
    - tongyi: Alibaba Tongyi Wanx
    - doubao: ByteDance Doubao
    - openai-compat: Any OpenAI-compatible image API
    - fal: fal.ai
    """

    def __init__(self, config: AssetProviderConfig | None):
        self.config = config
        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate(
        self,
        prompt: str,
        output_path: Path,
        style: str = "pixel_art",
        size: str = "1024x1024",
    ) -> Path:
        """
        Generate an image from a text prompt.

        Args:
            prompt: Text description of the desired image
            output_path: Where to save the generated image
            style: Art style hint (pixel_art, realistic, cartoon, etc.)
            size: Image dimensions ("1024x1024", "512x512", etc.)

        Returns:
            Path to the generated image file
        """
        if not self.config:
            raise AssetError("Image provider not configured")

        # Enhance prompt with style
        enhanced_prompt = self._enhance_prompt(prompt, style)

        # Route to appropriate provider
        provider = self.config.provider.lower()

        if provider == "tongyi":
            image_url = await self._generate_tongyi(enhanced_prompt, size)
        elif provider == "doubao":
            image_url = await self._generate_doubao(enhanced_prompt, size)
        elif provider in ("openai", "openai-compat"):
            image_url = await self._generate_openai(enhanced_prompt, size)
        elif provider == "fal":
            image_url = await self._generate_fal(enhanced_prompt, size)
        else:
            raise AssetError(f"Unknown image provider: {provider}")

        # Download and save
        await self._download_image(image_url, output_path)

        return output_path

    def _enhance_prompt(self, prompt: str, style: str) -> str:
        """Enhance prompt with game-specific style hints."""
        style_hints = {
            "pixel_art": "pixel art, retro game style, 16-bit, crisp pixels",
            "realistic": "realistic, detailed, high quality",
            "cartoon": "cartoon style, colorful, 2D game art",
            "chibi": "chibi style, cute, kawaii, big heads",
            "dark": "dark theme, moody lighting, gothic atmosphere",
        }
        hint = style_hints.get(style, style)
        return f"{prompt}. {hint}. Game asset, transparent background if character/item, centered composition."

    async def _generate_openai(self, prompt: str, size: str) -> str:
        """Generate image via OpenAI DALL-E API."""
        response = await self.client.post(
            f"{self.config.base_url or 'https://api.openai.com/v1'}/images/generations",
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            json={
                "model": self.config.model or "dall-e-3",
                "prompt": prompt,
                "size": size,
                "n": 1,
                "response_format": "url",
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["url"]

    async def _generate_tongyi(self, prompt: str, size: str) -> str:
        """Generate image via Tongyi Wanx API."""
        # Tongyi-specific API call
        # See: https://help.aliyun.com/document_detail/XXXXX.html
        response = await self.client.post(
            f"{self.config.base_url or 'https://dashscope.aliyuncs.com/api/v1'}/services/aigc/text2image/image-synthesis",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.config.model or "wanx-v1",
                "input": {"prompt": prompt},
                "parameters": {
                    "size": size,
                    "n": 1,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        # Poll for result if async
        if "output" in data and "task_id" in data["output"]:
            return await self._poll_task_result(data["output"]["task_id"])
        return data["output"]["results"][0]["url"]

    async def _generate_doubao(self, prompt: str, size: str) -> str:
        """Generate image via Doubao (ByteDance) API."""
        # Doubao-specific API
        raise NotImplementedError("Doubao image generation not yet implemented")

    async def _generate_fal(self, prompt: str, size: str) -> str:
        """Generate image via fal.ai API."""
        # fal.ai-specific API
        raise NotImplementedError("fal.ai image generation not yet implemented")

    async def _poll_task_result(self, task_id: str) -> str:
        """Poll for async task result."""
        import asyncio
        for _ in range(60):  # Max 60 retries
            await asyncio.sleep(2)
            response = await self.client.get(
                f"{self.config.base_url}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
            )
            data = response.json()
            if data.get("output", {}).get("task_status") == "SUCCEEDED":
                return data["output"]["results"][0]["url"]
        raise AssetError(f"Image generation timed out for task {task_id}")

    async def _download_image(self, url: str, output_path: Path) -> None:
        """Download image from URL and save to disk."""
        if url.startswith("http"):
            response = await self.client.get(url)
            response.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(output_path, "wb") as f:
                await f.write(response.content)
        else:
            # Local path — copy
            import shutil
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(url, output_path)

    async def close(self) -> None:
        await self.client.aclose()
```

## 8.4 Audio Generation

```python
# services/asset_audio_service.py
import httpx
from pathlib import Path


class AssetAudioService:
    """
    Audio generation via provider APIs.

    Generates both background music (BGM) and sound effects (SFX).
    """

    def __init__(self, config: AssetProviderConfig | None):
        self.config = config
        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate(
        self,
        prompt: str,
        output_path: Path,
        duration: int | None = None,
    ) -> Path:
        """
        Generate audio from a text prompt.

        Args:
            prompt: Text description of desired audio
            output_path: Where to save the audio file
            duration: Target duration in seconds (for BGM)

        Returns:
            Path to the generated audio file
        """
        if not self.config:
            raise AssetError("Audio provider not configured")

        # Route to provider
        provider = self.config.provider.lower()

        if provider in ("openai", "openai-compat"):
            audio_data = await self._generate_openai(prompt)
        elif provider == "tongyi":
            audio_data = await self._generate_tongyi(prompt, duration)
        elif provider == "doubao":
            audio_data = await self._generate_doubao(prompt)
        else:
            raise AssetError(f"Unknown audio provider: {provider}")

        # Save audio data
        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(output_path, "wb") as f:
            await f.write(audio_data)

        return output_path

    async def _generate_openai(self, prompt: str) -> bytes:
        """Generate audio via OpenAI API."""
        response = await self.client.post(
            f"{self.config.base_url or 'https://api.openai.com/v1'}/audio/speech",
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            json={
                "model": self.config.model or "tts-1",
                "input": prompt,
                "voice": "alloy",
            },
        )
        response.raise_for_status()
        return response.content

    async def _generate_tongyi(self, prompt: str, duration: int | None) -> bytes:
        """Generate audio via Tongyi API."""
        # Tongyi audio generation
        raise NotImplementedError("Tongyi audio generation not yet implemented")

    async def _generate_doubao(self, prompt: str) -> bytes:
        """Generate audio via Doubao API."""
        # Doubao audio generation
        raise NotImplementedError("Doubao audio generation not yet implemented")

    async def close(self) -> None:
        await self.client.aclose()
```

## 8.5 Video Generation

```python
# services/asset_video_service.py
import httpx
from pathlib import Path


class AssetVideoService:
    """
    Video/animation generation via provider APIs.

    Used for cutscenes, title sequences, and animated backgrounds.
    """

    def __init__(self, config: AssetProviderConfig | None):
        self.config = config
        self.client = httpx.AsyncClient(timeout=300.0)  # Longer timeout for video

    async def generate(
        self,
        prompt: str,
        output_path: Path,
        duration: int = 5,
    ) -> Path:
        """
        Generate a video from a text prompt.

        Args:
            prompt: Text description of desired video
            output_path: Where to save the video file
            duration: Target duration in seconds

        Returns:
            Path to the generated video file
        """
        if not self.config:
            raise AssetError("Video provider not configured")

        provider = self.config.provider.lower()

        if provider in ("openai", "openai-compat"):
            video_url = await self._generate_openai(prompt, duration)
        elif provider == "tongyi":
            video_url = await self._generate_tongyi(prompt, duration)
        elif provider == "doubao":
            video_url = await self._generate_doubao(prompt, duration)
        else:
            raise AssetError(f"Unknown video provider: {provider}")

        # Download video
        response = await self.client.get(video_url)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(output_path, "wb") as f:
            await f.write(response.content)

        return output_path

    async def _generate_openai(self, prompt: str, duration: int) -> str:
        """Generate video via OpenAI Sora API (when available)."""
        raise NotImplementedError("OpenAI video generation not yet implemented")

    async def _generate_tongyi(self, prompt: str, duration: int) -> str:
        """Generate video via Tongyi API."""
        raise NotImplementedError("Tongyi video generation not yet implemented")

    async def _generate_doubao(self, prompt: str, duration: int) -> str:
        """Generate video via Doubao API."""
        raise NotImplementedError("Doubao video generation not yet implemented")

    async def close(self) -> None:
        await self.client.aclose()
```

## 8.6 Auto-Tiler

```python
# services/auto_tiler.py
from PIL import Image
from pathlib import Path


class AutoTiler:
    """
    Automatically generate tilesets from source images.

    Splits a large image into uniform tiles for use in tilemaps.
    """

    def __init__(self, tile_size: int = 32):
        self.tile_size = tile_size

    async def generate_tileset(
        self,
        source_image: Path,
        output_path: Path,
        tile_width: int | None = None,
        tile_height: int | None = None,
    ) -> Path:
        """
        Generate a tileset from a source image.

        Args:
            source_image: Path to the source image
            output_path: Where to save the tileset
            tile_width: Width of each tile (default: 32)
            tile_height: Height of each tile (default: 32)

        Returns:
            Path to the generated tileset
        """
        tw = tile_width or self.tile_size
        th = tile_height or self.tile_size

        # Open image
        img = Image.open(source_image)
        width, height = img.size

        # Calculate grid dimensions
        cols = width // tw
        rows = height // th

        # Create tileset image
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
```

## 8.7 Tileset Processor

```python
# services/tileset-processor.py
from pathlib import Path
import json


class TilesetProcessor:
    """
    Process tileset images into Phaser-compatible tileset data.

    Generates tileset.json metadata for use with Phaser's tilemap system.
    """

    def __init__(self, tile_width: int = 32, tile_height: int = 32):
        self.tile_width = tile_width
        self.tile_height = tile_height

    async def process(
        self,
        tileset_image: Path,
        output_path: Path,
        tile_properties: dict[int, dict] | None = None,
    ) -> Path:
        """
        Process a tileset image and generate metadata.

        Args:
            tileset_image: Path to the tileset image
            output_path: Where to save the tileset JSON
            tile_properties: Optional properties per tile index

        Returns:
            Path to the generated tileset JSON
        """
        from PIL import Image
        img = Image.open(tileset_image)
        width, height = img.size

        cols = width // self.tile_width
        rows = height // self.tile_height

        tileset_data = {
            "name": tileset_image.stem,
            "image": str(tileset_image.name),
            "tileWidth": self.tile_width,
            "tileHeight": self.tile_height,
            "columns": cols,
            "tileCount": cols * rows,
            "margin": 0,
            "spacing": 0,
            "tiles": [],
        }

        for i in range(cols * rows):
            tile_data = {"id": i}
            if tile_properties and i in tile_properties:
                tile_data["properties"] = tile_properties[i]
            tileset_data["tiles"].append(tile_data)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(output_path, "w") as f:
            await f.write(json.dumps(tileset_data, indent=2))

        return output_path
```

## 8.8 Provider Status Display

At startup, OpenGame prints a one-line provider status banner:

```python
def print_provider_status(config: OpenGameConfig) -> None:
    """Print provider status at startup."""
    statuses = []

    for name, provider in [
        ("LLM", config.llm),
        ("Image", config.image),
        ("Audio", config.audio),
        ("Video", config.video),
        ("Reasoning", config.reasoning),
    ]:
        if provider and provider.api_key:
            statuses.append(f"{name}: {provider.provider}")
        else:
            statuses.append(f"{name}: [not configured]")

    print(f"Providers: {' | '.join(statuses)}")
```

Example output:
```
Providers: LLM: openai | Image: tongyi | Audio: [not configured] | Video: [not configured] | Reasoning: openai
```
