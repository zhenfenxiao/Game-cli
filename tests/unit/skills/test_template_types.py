"""Tests for Template Skill data models."""

import json

from opengame.skills.template_skill.types import (
    ClassificationResult,
    PhysicsProfile,
    ProjectSnapshot,
    TemplateFamily,
    TemplateLibrary,
)


class TestPhysicsProfile:
    def test_construction(self) -> None:
        pf = PhysicsProfile(has_gravity=True, perspective="side", movement_type="continuous")
        assert pf.has_gravity is True
        assert pf.perspective == "side"

    def test_json_roundtrip(self) -> None:
        pf = PhysicsProfile(has_gravity=False, perspective="top_down", movement_type="grid")
        data = json.loads(pf.model_dump_json())
        pf2 = PhysicsProfile.model_validate(data)
        assert pf2 == pf


class TestTemplateLibrary:
    def test_empty_library(self) -> None:
        lib = TemplateLibrary(version=0)
        assert lib.families == []
        assert lib.evolution_log == []

    def test_with_families(self) -> None:
        fam = TemplateFamily(
            id="fam-platformer-001",
            archetype="platformer",
            physics_profile=PhysicsProfile(has_gravity=True, perspective="side", movement_type="continuous"),
        )
        lib = TemplateLibrary(version=1, families=[fam])
        assert len(lib.families) == 1
        assert lib.families[0].archetype == "platformer"


class TestClassificationResult:
    def test_construction(self) -> None:
        cr = ClassificationResult(
            archetype="platformer",
            physics_profile=PhysicsProfile(has_gravity=True, perspective="side", movement_type="continuous"),
            confidence=0.9,
        )
        assert cr.archetype == "platformer"
        assert cr.confidence == 0.9
