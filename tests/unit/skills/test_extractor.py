"""Tests for PatternExtractor."""

from opengame.skills.template_skill.extractor import PatternExtractor
from opengame.skills.template_skill.types import (
    ClassificationResult,
    FileEntry,
    PhysicsProfile,
    ProjectSnapshot,
)


class TestPatternExtractor:
    def test_extract_classes(self) -> None:
        extractor = PatternExtractor()
        snapshot = ProjectSnapshot(
            project_path="/test",
            files=[
                FileEntry(
                    relative_path="Game.ts",
                    content="export class Game extends Phaser.Game {\n  constructor() {}\n  public start(): void {}\n}",
                    extension=".ts",
                ),
            ],
        )

        result = extractor.extract(
            snapshot,
            ClassificationResult(
                archetype="platformer",
                physics_profile=PhysicsProfile(has_gravity=True, perspective="side", movement_type="continuous"),
                confidence=0.8,
            ),
        )

        assert len(result.classes) >= 1

    def test_extract_hooks(self) -> None:
        extractor = PatternExtractor()
        snapshot = ProjectSnapshot(
            project_path="/test",
            files=[
                FileEntry(
                    relative_path="PlayScene.ts",
                    content="class PlayScene { protected override create(): void { super.create(); } }",
                    extension=".ts",
                ),
            ],
        )

        result = extractor.extract(
            snapshot,
            ClassificationResult(
                archetype="platformer",
                physics_profile=PhysicsProfile(has_gravity=True, perspective="side", movement_type="continuous"),
                confidence=0.8,
            ),
        )

        assert len(result.hooks) >= 1

    def test_extract_imports(self) -> None:
        extractor = PatternExtractor()
        snapshot = ProjectSnapshot(
            project_path="/test",
            files=[
                FileEntry(
                    relative_path="main.ts",
                    content='import { Game } from "phaser";\nimport { PlayScene } from "./scenes/PlayScene";',
                    extension=".ts",
                ),
            ],
        )

        result = extractor.extract(
            snapshot,
            ClassificationResult(
                archetype="platformer",
                physics_profile=PhysicsProfile(has_gravity=True, perspective="side", movement_type="continuous"),
                confidence=0.8,
            ),
        )

        assert len(result.imports) >= 1
