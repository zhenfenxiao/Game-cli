"""OpenGameEvaluator — main evaluation orchestrator.

Runs the complete 3-phase evaluation pipeline on a generated game.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from opengame.bench.scoring.build_health import BuildHealthEvaluator
from opengame.bench.scoring.intent_alignment import IntentAlignmentEvaluator
from opengame.bench.scoring.visual_usability import VisualUsabilityEvaluator
from opengame.bench.types import (
    BuildHealthScore,
    EvaluationConfig,
    EvaluationResult,
    IntentAlignmentScore,
    VisualUsabilityScore,
)
from opengame.core.llm_client import BaseLlmClient


class OpenGameEvaluator:
    """Main evaluation orchestrator for OpenGame-Bench.

    Usage:
        evaluator = OpenGameEvaluator(config, llm_client)
        result = await evaluator.evaluate(game_dir, prompt)
    """

    def __init__(
        self,
        config: EvaluationConfig,
        llm_client: BaseLlmClient | None = None,
    ) -> None:
        self.config = config

        self.build_health = BuildHealthEvaluator()
        # Visual usability requires Playwright (Phase 6 optional)
        self.visual_usability = VisualUsabilityEvaluator(config)
        self.intent_alignment = IntentAlignmentEvaluator(llm_client, config)

    async def evaluate(
        self,
        game_dir: str | Path,
        prompt: str,
    ) -> EvaluationResult:
        """Evaluate a generated game across all three dimensions.

        Args:
            game_dir: Path to the game project directory.
            prompt: Original user prompt (for intent alignment).

        Returns:
            EvaluationResult with scores for all dimensions.
        """
        root = Path(game_dir).resolve()
        start = asyncio.get_event_loop().time()

        # Phase 1: Build Health
        build_score = await self.build_health.evaluate(root)

        # Phase 2: Visual Usability
        visual_score = await self.visual_usability.evaluate(root)

        # Phase 3: Intent Alignment (VLM judge)
        intent_score = await self.intent_alignment.evaluate(
            root, prompt, visual_score.screenshot_path,
        )

        # Overall score (weighted average)
        overall = (
            build_score.score * 0.33
            + visual_score.score * 0.33
            + intent_score.score * 0.34
        )

        duration_ms = int((asyncio.get_event_loop().time() - start) * 1000)

        return EvaluationResult(
            build_health=build_score,
            visual_usability=visual_score,
            intent_alignment=intent_score,
            overall=round(overall, 2),
            duration_ms=duration_ms,
            game_dir=str(root),
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )


def format_evaluation_report(result: EvaluationResult) -> str:
    """Format an EvaluationResult as a human-readable report.

    Args:
        result: The evaluation result.

    Returns:
        Formatted report string.
    """
    lines = [
        "=" * 60,
        f"OpenGame-Bench Evaluation Report",
        f"Game: {result.game_dir}",
        f"Evaluated: {result.evaluated_at}",
        f"Duration: {result.duration_ms / 1000:.1f}s",
        "=" * 60,
        "",
        f"Overall Score: {result.overall:.2f} / 1.00",
        "",
        "--- Build Health (33%) ---",
        f"  Score: {result.build_health.score:.2f}",
        f"  Compiles: {result.build_health.compiles}",
        f"  Tests pass: {result.build_health.test_passes}",
        f"  Errors: {result.build_health.error_count}",
        f"  Warnings: {len(result.build_health.warnings)}",
        "",
        "--- Visual Usability (33%) ---",
        f"  Score: {result.visual_usability.score:.2f}",
        f"  Renders: {result.visual_usability.renders}",
        f"  Input response: {result.visual_usability.responds_to_input}",
        f"  Frame rate: {'stable' if result.visual_usability.frame_rate_stable else 'unstable'}",
        f"  Issues: {len(result.visual_usability.issues)}",
        "",
        "--- Intent Alignment (34%) ---",
        f"  Score: {result.intent_alignment.score:.2f}",
        f"  Criteria met: {len(result.intent_alignment.criteria_met)}",
        f"  Criteria missed: {len(result.intent_alignment.criteria_missed)}",
    ]

    return "\n".join(lines)
