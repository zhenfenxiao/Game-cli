"""FamilyMerger — merges abstracted templates into the template library.

Creates new families or merges into existing ones with stability tracking.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from opengame.skills.template_skill.types import (
    AbstractedTemplates,
    EvolutionEntry,
    TemplateFamily,
    TemplateLibrary,
)

STABILITY_INCREMENT = 0.1
MAX_STABILITY = 1.0


class FamilyMerger:
    """Merge abstracted templates into the library.

    Either creates a new TemplateFamily or merges into an existing one
    by matching the archetype name.
    """

    def __init__(self) -> None:
        pass

    def merge(
        self,
        abstracted: AbstractedTemplates,
        library: TemplateLibrary,
        project_path: str,
        task_id: str,
    ) -> tuple[TemplateLibrary, str]:
        """Merge abstracted templates into the library.

        Args:
            abstracted: The abstracted templates to merge.
            library: The current template library.
            project_path: Path of the source project.
            task_id: Unique task identifier.

        Returns:
            Tuple of (updated library, family ID that was created/updated).
        """
        # Find matching family by archetype
        existing = None
        for fam in library.families:
            if fam.archetype == abstracted.archetype:
                existing = fam
                break

        if existing:
            family_id = self._merge_into_family(existing, abstracted, project_path)
            action: str = "merged_to_family"
        else:
            family_id = self._create_family(library, abstracted, project_path)
            action = "created_family"

        # Append evolution entry
        library.evolution_log.append(EvolutionEntry(
            task_id=task_id,
            project_path=project_path,
            archetype=abstracted.archetype,
            action=action,  # type: ignore[arg-type]
            family_id=family_id,
            patterns_extracted=len(abstracted.template_files),
            patterns_merged=len(abstracted.template_files),
        ))

        # Bump version
        library.version += 1
        library.updated_at = datetime.now(timezone.utc).isoformat()

        return library, family_id

    # --- Private helpers ---

    def _create_family(
        self,
        library: TemplateLibrary,
        abstracted: AbstractedTemplates,
        project_path: str,
    ) -> str:
        """Create a new TemplateFamily in the library."""
        count = len(library.families) + 1
        family_id = f"fam-{abstracted.archetype}-{count:03d}"

        family = TemplateFamily(
            id=family_id,
            archetype=abstracted.archetype,
            physics_profile=abstracted.template_files[0].content if abstracted.template_files else "",
            discovered_at_task=project_path,
            contributing_projects=[project_path],
            stability=0.1,
            template_files=abstracted.template_files,
            hooks=abstracted.hooks,
            config_extensions=abstracted.config_schema,
            summary=abstracted.summary,
        )
        # Fix physics_profile (was assigned wrong value above)
        # Use a default physics profile based on archetype
        from opengame.skills.template_skill.types import PhysicsProfile
        physics_map = {
            "platformer": PhysicsProfile(has_gravity=True, perspective="side", movement_type="continuous"),
            "top_down": PhysicsProfile(has_gravity=False, perspective="top_down", movement_type="continuous"),
            "grid_logic": PhysicsProfile(has_gravity=False, perspective="top_down", movement_type="grid"),
            "tower_defense": PhysicsProfile(has_gravity=False, perspective="top_down", movement_type="path"),
            "ui_heavy": PhysicsProfile(has_gravity=False, perspective="none", movement_type="ui_only"),
        }
        family.physics_profile = physics_map.get(
            abstracted.archetype,
            PhysicsProfile(has_gravity=False, perspective="top_down", movement_type="continuous"),
        )

        library.families.append(family)
        return family_id

    @staticmethod
    def _merge_into_family(
        family: TemplateFamily,
        abstracted: AbstractedTemplates,
        project_path: str,
    ) -> str:
        """Merge abstracted templates into an existing family."""
        # Add contributing project
        if project_path not in family.contributing_projects:
            family.contributing_projects.append(project_path)

        # Increase stability
        family.stability = min(MAX_STABILITY, family.stability + STABILITY_INCREMENT)

        # Deduplicate and merge hooks
        existing_hook_names = {h.name for h in family.hooks}
        for hook in abstracted.hooks:
            if hook.name in existing_hook_names:
                for existing in family.hooks:
                    if existing.name == hook.name:
                        existing.occurrence_count += 1
            else:
                family.hooks.append(hook)
                existing_hook_names.add(hook.name)

        # Deduplicate and merge config fields
        existing_config_keys = {c.key for c in family.config_extensions}
        for field in abstracted.config_schema:
            if field.key not in existing_config_keys:
                family.config_extensions.append(field)
                existing_config_keys.add(field.key)

        # Deduplicate template files by path
        existing_paths = {t.relative_path for t in family.template_files}
        for tf in abstracted.template_files:
            if tf.relative_path not in existing_paths:
                family.template_files.append(tf)
                existing_paths.add(tf.relative_path)

        family.summary = f"Merged from {len(family.contributing_projects)} projects"
        return family.id
