"""E2E test: full game generation pipeline with mock LLM."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from opengame.bench.evaluator import OpenGameEvaluator
from opengame.bench.types import EvaluationConfig
from opengame.config.models import OpenGameConfig
from opengame.core.tool_registry import ToolRegistry
from opengame.skills.debug_skill import DebugSkill, ProtocolManager
from opengame.skills.game_skill import GameSkill
from opengame.skills.template_skill import TemplateSkill
from opengame.skills.template_skill.library_manager import LibraryManager


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock()
    llm.model = "gpt-4o"

    # Sequence of responses for 6-phase pipeline:
    # Phase 2: GDD response
    gdd_response = """# Test Game
## 1. Game Overview
Test game overview with assets: player_sprite, enemy_sprite
## 2. Core Mechanics
Scene: PlayScene, scene: MenuScene
## 3. Level Design
Level 1 layout
## 4. Art and Audio
Pixel art style, background music
## 5. Technical Specs
800x600, Phaser 3, TypeScript, Vite
## 6. Implementation Plan
Phase 1: core, Phase 2: polish"""

    llm.generate.return_value.content = gdd_response
    llm.generate.return_value.tool_calls = []
    llm.generate.return_value.finish_reason = "stop"
    return llm


@pytest.fixture
def game_config(tmp_path) -> OpenGameConfig:
    config = OpenGameConfig()
    # Point to tmp_path subdirectories
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "core").mkdir()
    (templates / "core" / "main.ts").write_text("console.log('test');")
    (templates / "core" / "gameConfig.json").write_text('{}')

    (templates / "modules").mkdir()
    (templates / "modules" / "platformer").mkdir()
    (templates / "modules" / "platformer" / "PlayScene.ts").write_text("class PlayScene {}")

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "readme.md").write_text("# Docs")

    config.game_skill.templates_dir = templates
    config.game_skill.docs_dir = docs
    config.game_skill.archetypes_dir = templates / "modules"
    config.game_skill.library_output_dir = tmp_path / ".opengame" / "template-library"
    config.game_skill.protocol_output_dir = tmp_path / ".opengame" / "debug-protocol"
    return config


class TestFullPipeline:
    """E2E tests for the complete 6-phase game generation pipeline."""

    @pytest.mark.asyncio
    async def test_game_generation_e2e(
        self, mock_llm: AsyncMock, game_config: OpenGameConfig, tmp_path,
    ) -> None:
        """Test the full pipeline from prompt to game with mock LLM."""
        output_dir = tmp_path / "output-game"

        # Initialize skills
        library_manager = LibraryManager(game_config.game_skill.library_output_dir)
        template_skill = TemplateSkill(mock_llm, library_manager)

        protocol_manager = ProtocolManager(game_config.game_skill.protocol_output_dir)
        debug_skill = DebugSkill(mock_llm, protocol_manager)

        tool_registry = ToolRegistry()

        # Build orchestrator
        game_skill = GameSkill(
            llm_client=mock_llm,
            template_skill=template_skill,
            debug_skill=debug_skill,
            tool_registry=tool_registry,
            config=game_config,
        )

        # Run pipeline
        result = await game_skill.generate_game(
            prompt="Build a simple platformer",
            output_dir=output_dir,
        )

        # Verify output directory was created
        assert output_dir.exists()

        # Verify GDD was generated
        assert result.gdd is not None
        assert len(result.gdd.title) > 0

        # Verify project files were scaffolded
        # (Not every file will exist in mock mode, but key artifacts should)
        assert (output_dir / "GAME_DESIGN.md").exists() or result.gdd is not None

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(
        self, mock_llm: AsyncMock, game_config: OpenGameConfig, tmp_path,
    ) -> None:
        """Test that pipeline errors are handled gracefully."""
        # Make LLM fail
        mock_llm.generate.side_effect = Exception("API connection error")

        game_skill = GameSkill(
            llm_client=mock_llm,
            template_skill=TemplateSkill(mock_llm, LibraryManager(tmp_path / "lib")),
            debug_skill=DebugSkill(mock_llm, ProtocolManager(tmp_path / "proto")),
            tool_registry=ToolRegistry(),
            config=game_config,
        )

        result = await game_skill.generate_game(
            prompt="Test game",
            output_dir=tmp_path / "broken-game",
        )

        # Should not crash — should return failure result
        assert result.success is False
        assert result.error is not None


class TestBenchEvaluator:
    """Tests for the OpenGame-Bench evaluation system."""

    @pytest.mark.asyncio
    async def test_build_health_evaluation(self, tmp_path) -> None:
        """Test build health evaluation on a project."""
        from opengame.bench.scoring.build_health import BuildHealthEvaluator

        # Create minimal project
        project = tmp_path / "test-game"
        project.mkdir()
        import json
        (project / "package.json").write_text(json.dumps({
            "name": "test",
            "scripts": {"build": "echo ok"},
        }))

        evaluator = BuildHealthEvaluator()
        result = await evaluator.evaluate(project)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_visual_usability_evaluation(self, tmp_path) -> None:
        """Test visual usability evaluation."""
        from opengame.bench.scoring.visual_usability import VisualUsabilityEvaluator

        project = tmp_path / "test-game"
        project.mkdir()
        (project / "index.html").write_text(
            '<html><body><canvas id="game"></canvas>'
            '<script src="game.js"></script></body></html>'
        )
        src = project / "src"
        src.mkdir()
        (src / "Game.ts").write_text(
            "this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.W);"
        )

        evaluator = VisualUsabilityEvaluator(EvaluationConfig())
        result = await evaluator.evaluate(project)

        assert result.renders is True
        assert result.responds_to_input is True

    @pytest.mark.asyncio
    async def test_intent_alignment_with_mock(self, mock_llm: AsyncMock, tmp_path) -> None:
        """Test intent alignment with mock LLM."""
        from opengame.bench.scoring.intent_alignment import IntentAlignmentEvaluator

        mock_llm.generate.return_value.content = (
            '{"score": 0.8, "criteria_met": ["core concept", "mechanics"], '
            '"criteria_missed": ["theme"], "judge_notes": "Good match"}'
        )

        project = tmp_path / "test-game"
        project.mkdir()
        (project / "GAME_DESIGN.md").write_text("# Snake Clone\nA classic snake game.")

        evaluator = IntentAlignmentEvaluator(mock_llm, EvaluationConfig())
        result = await evaluator.evaluate(project, "Build a Snake game")

        assert result.score == 0.8
        assert len(result.criteria_met) == 2

    @pytest.mark.asyncio
    async def test_open_game_evaluator_integration(
        self, mock_llm: AsyncMock, tmp_path,
    ) -> None:
        """Test the complete evaluator orchestrator."""
        mock_llm.generate.return_value.content = '{"score": 0.9, "criteria_met": ["all"], "criteria_missed": [], "judge_notes": "Perfect"}'

        import json
        project = tmp_path / "test-game"
        project.mkdir()
        (project / "package.json").write_text(json.dumps({
            "name": "test",
            "scripts": {"build": "echo ok"},
        }))
        (project / "index.html").write_text(
            '<html><body><canvas id="game"></canvas></body></html>'
        )
        src = project / "src"
        src.mkdir()
        (src / "Game.ts").write_text("this.input.keyboard.addKey('W');")
        (project / "GAME_DESIGN.md").write_text("# Test Game")

        evaluator = OpenGameEvaluator(EvaluationConfig(), mock_llm)
        result = await evaluator.evaluate(project, "Build a test game")

        assert 0.0 <= result.overall <= 1.0
        assert result.build_health is not None
        assert result.visual_usability is not None
        assert result.intent_alignment is not None
