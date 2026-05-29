"""Memory tool: save_memory — persists information to ~/.opengame/memory/.

Stores memory entries as markdown files with YAML frontmatter for structured recall.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import aiofiles

from opengame.core.tool_registry import ToolParameter, ToolRegistry

MEMORY_DIR = Path.home() / ".opengame" / "memory"


def register_memory_tools(registry: ToolRegistry) -> None:
    """Register memory persistence tool.

    Args:
        registry: ToolRegistry to register tools with.
    """

    @registry.tool(
        name="save_memory",
        description="Save a piece of information to persistent memory. Useful for "
        "remembering user preferences, project conventions, and important facts.",
        parameters=[
            ToolParameter(
                name="content",
                type="string",
                description="The content to remember (markdown format supported)",
                required=True,
            ),
            ToolParameter(
                name="category",
                type="string",
                description="Memory category",
                enum=["user", "project", "feedback", "reference"],
                required=True,
            ),
            ToolParameter(
                name="title",
                type="string",
                description="Short title for this memory (used as filename slug)",
                required=False,
            ),
        ],
    )
    async def save_memory(content: str, category: str, title: str = "") -> str:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

        # Generate a filename based on title or timestamp
        slug = _slugify(title) if title else datetime.now(timezone.utc).strftime("memory-%Y%m%d-%H%M%S")
        filepath = MEMORY_DIR / f"{category}_{slug}.md"

        # Build frontmatter
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        frontmatter = f"""---
category: {category}
title: {title or "Untitled"}
timestamp: {timestamp}
---

{content}
"""
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(frontmatter)

        return json.dumps({
            "saved": True,
            "file": str(filepath),
            "category": category,
        }, ensure_ascii=False, indent=2)


def _slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:64] if slug else "memory"
