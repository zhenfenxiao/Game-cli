"""LibraryManager — CRUD operations for the template library.

Handles JSON persistence of TemplateLibrary and individual
family files on disk.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import aiofiles

from opengame.skills.template_skill.types import TemplateFamily, TemplateLibrary


class LibraryManager:
    """Manage template library persistence.

    Stores the library manifest as library.json and individual
    family data as separate JSON files under families/.
    """

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.library_path = self.output_dir / "library.json"
        self.families_dir = self.output_dir / "families"

    async def initialize(self) -> TemplateLibrary:
        """Create a new empty template library.

        Returns:
            A fresh TemplateLibrary with version 0.
        """
        now = datetime.now(timezone.utc).isoformat()
        return TemplateLibrary(
            version=0,
            created_at=now,
            updated_at=now,
            meta_template_path=str(self.output_dir),
        )

    async def load(self) -> TemplateLibrary | None:
        """Load the library from disk.

        Returns:
            TemplateLibrary if the file exists and is valid, None otherwise.
        """
        if not self.library_path.exists():
            return None

        try:
            async with aiofiles.open(self.library_path, "r", encoding="utf-8") as f:
                data = await f.read()
            return TemplateLibrary.model_validate(json.loads(data))
        except (json.JSONDecodeError, OSError, ValueError):
            return None

    async def load_or_init(self) -> TemplateLibrary:
        """Load the library or create a new one if not found.

        Returns:
            Existing or new TemplateLibrary.
        """
        library = await self.load()
        if library is None:
            library = await self.initialize()
        return library

    async def save(self, library: TemplateLibrary) -> None:
        """Save the library to disk.

        Saves the manifest (with family metadata but not full template content)
        to library.json. Individual family template files are saved under
        families/{archetype}/.

        Args:
            library: The template library to persist.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Build a light manifest (exclude full template file content)
        manifest = library.model_dump()

        # Truncate template file content in manifest (stored separately)
        for fam in manifest.get("families", []):
            for tf in fam.get("template_files", []):
                tf["content"] = tf["content"][:200] + "..." if len(tf.get("content", "")) > 200 else tf.get("content", "")

        # Save manifest
        async with aiofiles.open(self.library_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(manifest, ensure_ascii=False, indent=2))

        # Save individual families
        self.families_dir.mkdir(parents=True, exist_ok=True)
        for family in library.families:
            family_dir = self.families_dir / family.archetype
            family_dir.mkdir(parents=True, exist_ok=True)

            family_data = family.model_dump()
            async with aiofiles.open(
                family_dir / "family.json", "w", encoding="utf-8",
            ) as f:
                await f.write(json.dumps(family_data, ensure_ascii=False, indent=2))

    def get_summary(self, library: TemplateLibrary) -> str:
        """Generate a human-readable library summary.

        Args:
            library: The template library.

        Returns:
            Summary string suitable for display or LLM context.
        """
        if not library.families:
            return "Template library is empty. No families have been discovered yet."

        lines = [f"Template Library v{library.version}"]
        lines.append(f"Families: {len(library.families)}")
        lines.append(f"Evolution entries: {len(library.evolution_log)}")
        lines.append("")

        for fam in library.families:
            lines.append(
                f"  [{fam.id}] {fam.archetype} "
                f"(stability: {fam.stability:.1f}, "
                f"projects: {len(fam.contributing_projects)}, "
                f"hooks: {len(fam.hooks)})"
            )

        return "\n".join(lines)

    @staticmethod
    def find_family(library: TemplateLibrary, archetype: str) -> TemplateFamily | None:
        """Find a family by archetype name.

        Args:
            library: The template library.
            archetype: Archetype name to search for.

        Returns:
            Matching TemplateFamily or None.
        """
        for fam in library.families:
            if fam.archetype == archetype:
                return fam
        return None
