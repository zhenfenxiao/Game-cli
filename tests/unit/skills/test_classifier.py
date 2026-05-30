"""Tests for Classifier."""

from unittest.mock import AsyncMock

import pytest

from opengame.skills.template_skill.classifier import Classifier
from opengame.skills.template_skill.types import (
    PhysicsProfile,
    ProjectSnapshot,
    TemplateLibrary,
)


class TestClassifier:
    @pytest.fixture
    def mock_llm(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def classifier(self, mock_llm: AsyncMock) -> Classifier:
        return Classifier(mock_llm)

    def test_heuristic_classify_platformer(self, classifier: Classifier) -> None:
        snapshot = ProjectSnapshot(
            project_path="/test",
            code_summary="A platformer game with gravity, jumping, and side-scroll mechanics",
        )
        library = TemplateLibrary()

        result = classifier._heuristic_classify(snapshot, library)
        assert result.archetype == "platformer"
        assert result.physics_profile.has_gravity is True

    def test_heuristic_classify_grid_logic(self, classifier: Classifier) -> None:
        snapshot = ProjectSnapshot(
            project_path="/test",
            code_summary="A Snake game on a grid with tile-based movement",
        )
        library = TemplateLibrary()

        result = classifier._heuristic_classify(snapshot, library)
        assert result.archetype == "grid_logic"
        assert result.physics_profile.movement_type == "grid"

    def test_heuristic_classify_default(self, classifier: Classifier) -> None:
        snapshot = ProjectSnapshot(
            project_path="/test",
            code_summary="A completely unknown game concept",
        )
        library = TemplateLibrary()

        result = classifier._heuristic_classify(snapshot, library)
        assert result.archetype == "platformer"  # Default
        assert result.confidence < 0.5

    def test_library_aware_new_family(self, classifier: Classifier) -> None:
        snapshot = ProjectSnapshot(
            project_path="/test",
            code_summary="A tower defense with waves and turrets",
        )
        # Empty library — should be new family
        library = TemplateLibrary()

        result = classifier._heuristic_classify(snapshot, library)
        assert result.is_new_family is True

    @pytest.mark.asyncio
    async def test_llm_classify_fallback(self, classifier: Classifier, mock_llm: AsyncMock) -> None:
        mock_llm.generate.side_effect = Exception("API error")
        snapshot = ProjectSnapshot(
            project_path="/test",
            code_summary="A platformer with jumping",
        )
        library = TemplateLibrary()

        # Should fall back to heuristic
        result = await classifier.classify(snapshot, library)
        assert result.archetype == "platformer"
