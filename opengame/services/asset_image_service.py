"""AssetImageService — image generation via provider HTTP APIs.

Supported providers:
- tongyi: Alibaba Tongyi Wanx (DashScope)
- openai-compat: Any OpenAI-compatible image generation API
- doubao: ByteDance Doubao (stub)
- fal: fal.ai (stub)
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import aiofiles
import httpx

from opengame.config.models import AssetProviderConfig
from opengame.utils.errors import AssetError

# Style hints for game asset generation
STYLE_HINTS: dict[str, str] = {
    "pixel_art": "pixel art, retro game style, 16-bit, crisp pixels, clean edges",
    "realistic": "realistic, detailed, high quality, photorealistic rendering",
    "cartoon": "cartoon style, colorful, 2D game art, vibrant colors",
    "chibi": "chibi style, cute, kawaii, big heads, small bodies",
    "dark": "dark theme, moody lighting, gothic atmosphere, shadows",
    "minimalist": "minimalist, flat design, simple shapes, clean lines",
}


class AssetImageService:
    """Image generation via provider HTTP APIs.

    Handles prompt enhancement, provider routing, async task polling
    (for Tongyi), and image download.
    """

    def __init__(self, config: AssetProviderConfig | None) -> None:
        self.config = config
        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate(
        self,
        prompt: str,
        output_path: Path,
        style: str = "pixel_art",
        size: str = "1024x1024",
    ) -> Path:
        """Generate an image from a text prompt.

        Args:
            prompt: Text description of the desired image.
            output_path: Where to save the generated image.
            style: Art style hint (pixel_art, realistic, cartoon, etc.).
            size: Image dimensions ("1024x1024", "512x512", etc.).

        Returns:
            Path to the generated image file.
        """
        if not self.config:
            raise AssetError("Image provider not configured", recoverable=False)

        enhanced_prompt = self._enhance_prompt(prompt, style)
        provider = self.config.provider.lower()

        if provider == "tongyi":
            image_url = await self._generate_tongyi(enhanced_prompt, size)
        elif provider in ("openai", "openai-compat"):
            image_url = await self._generate_openai(enhanced_prompt, size)
        elif provider == "doubao":
            image_url = await self._generate_doubao(enhanced_prompt, size)
        elif provider == "fal":
            image_url = await self._generate_fal(enhanced_prompt, size)
        else:
            raise AssetError(f"Unknown image provider: {provider}", recoverable=False)

        await self._download_image(image_url, output_path)
        return output_path

    def _enhance_prompt(self, prompt: str, style: str) -> str:
        """Add game-specific style hints to the prompt."""
        hint = STYLE_HINTS.get(style, style)
        return (
            f"{prompt}. {hint}. Game asset, sprite, "
            f"transparent background if character or item, "
            f"centered composition, clean silhouette."
        )

    # --- Provider implementations ---

    async def _generate_tongyi(self, prompt: str, size: str) -> str:
        """Generate via Alibaba Tongyi Wanx (DashScope) API.

        Uses the async task-based API flow: submit → poll → get result URL.
        Tongyi uses "1024*1024" format (asterisk), not "1024x1024" (letter x).
        """
        base_url = self.config.base_url or "https://dashscope.aliyuncs.com"
        api_url = f"{base_url}/api/v1/services/aigc/text2image/image-synthesis"

        # Tongyi uses "*" not "x" for size format
        tongyi_size = size.replace("x", "*")

        payload = {
            "model": self.config.model or "wan2.5-t2i-preview",
            "input": {"prompt": prompt},
            "parameters": {
                "size": tongyi_size,
                "n": 1,
            },
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",  # Required: sync API returns 403
        }

        response = await self.client.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Check for async task (Tongyi returns task_id for async processing)
        output = data.get("output", {})
        if "task_id" in output:
            task_id = output["task_id"]
            return await self._poll_tongyi_task(task_id)

        # Sync response (results directly available)
        if "results" in output:
            return output["results"][0]["url"]

        raise AssetError(
            f"Unexpected Tongyi response: {json.dumps(data, ensure_ascii=False)[:500]}",
            context={"provider": "tongyi"},
        )

    async def _poll_tongyi_task(self, task_id: str) -> str:
        """Poll Tongyi async task until completion."""
        base_url = self.config.base_url or "https://dashscope.aliyuncs.com"
        task_url = f"{base_url}/api/v1/tasks/{task_id}"
        headers = {"Authorization": f"Bearer {self.config.api_key}"}

        max_retries = 60
        for attempt in range(max_retries):
            await asyncio.sleep(2)

            response = await self.client.get(task_url, headers=headers)
            response.raise_for_status()
            data = response.json()

            task_status = data.get("output", {}).get("task_status", "")

            if task_status == "SUCCEEDED":
                results = data.get("output", {}).get("results", [])
                if results:
                    return results[0]["url"]
                raise AssetError("Tongyi task succeeded but no image URL returned")

            if task_status == "FAILED":
                raise AssetError(
                    f"Tongyi task {task_id} failed: {json.dumps(data, ensure_ascii=False)[:300]}",
                    context={"provider": "tongyi", "task_id": task_id},
                )

        raise AssetError(
            f"Tongyi task {task_id} timed out after {max_retries * 2}s",
            context={"provider": "tongyi", "task_id": task_id},
        )

    async def _generate_openai(self, prompt: str, size: str) -> str:
        """Generate via OpenAI-compatible image API.

        Uses POST /images/generations with DALL-E-compatible payload.
        """
        base_url = self.config.base_url or "https://api.openai.com/v1"
        api_url = f"{base_url}/images/generations"

        payload = {
            "model": self.config.model or "dall-e-3",
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "url",
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        response = await self.client.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        images = data.get("data", [])
        if images:
            return images[0]["url"]

        raise AssetError(
            f"OpenAI image API returned no data: {json.dumps(data, ensure_ascii=False)[:300]}",
            context={"provider": "openai-compat"},
        )

    async def _generate_doubao(self, prompt: str, size: str) -> str:
        """Generate via ByteDance Doubao (Seedream) API."""
        raise NotImplementedError(
            "Doubao image generation not yet implemented. "
            "Use 'tongyi' or 'openai-compat' provider instead."
        )

    async def _generate_fal(self, prompt: str, size: str) -> str:
        """Generate via fal.ai API."""
        raise NotImplementedError(
            "fal.ai image generation not yet implemented. "
            "Use 'tongyi' or 'openai-compat' provider instead."
        )

    # --- Image download ---

    async def _download_image(self, url: str, output_path: Path) -> None:
        """Download image from URL and save to disk."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if url.startswith(("http://", "https://")):
            response = await self.client.get(url)
            response.raise_for_status()
            async with aiofiles.open(output_path, "wb") as f:
                await f.write(response.content)
        else:
            # Treat as local path
            import shutil
            shutil.copy(url, output_path)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
