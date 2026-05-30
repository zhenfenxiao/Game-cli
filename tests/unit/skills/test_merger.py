"""Tests for FamilyMerger."""

from opengame.skills.template_skill.merger import MAX_STABILITY, STABILITY_INCREMENT, FamilyMerger
from opengame.skills.template_skill.types import (
    AbstractedTemplates,
    TemplateLibrary,
)


class TestFamilyMerger:
    def test_create_new_family(self) -> None:
        merger = FamilyMerger()
        abstracted = AbstractedTemplates(
            archetype="platformer",
            summary="A platformer game template",
        )
        library = TemplateLibrary()

        updated, family_id = merger.merge(abstracted, library, "/test/game", "task-001")

        assert len(updated.families) == 1
        assert updated.families[0].archetype == "platformer"
        assert updated.families[0].stability == 0.1
        assert len(updated.evolution_log) == 1
        assert updated.evolution_log[0].action == "created_family"

    def test_merge_existing_family(self) -> None:
        merger = FamilyMerger()
        abstracted = AbstractedTemplates(
            archetype="platformer",
            summary="Updated platformer",
        )
        library = TemplateLibrary()

        # First merge: creates family
        lib1, _ = merger.merge(abstracted, library, "/test/game1", "task-001")
        assert lib1.families[0].stability == 0.1

        # Second merge: increases stability
        lib2, _ = merger.merge(abstracted, lib1, "/test/game2", "task-002")
        assert lib2.families[0].stability == 0.2
        assert len(lib2.evolution_log) == 2
        assert lib2.evolution_log[1].action == "merged_to_family"
        assert len(lib2.families[0].contributing_projects) == 2

    def test_stability_capped_at_max(self) -> None:
        merger = FamilyMerger()
        abstracted = AbstractedTemplates(archetype="platformer", summary="")
        library = TemplateLibrary()

        for i in range(15):
            library, _ = merger.merge(abstracted, library, f"/test/game{i}", f"task-{i:03d}")

        assert library.families[0].stability <= MAX_STABILITY
