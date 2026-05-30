"""Score dataclasses and config for OpenGame-Bench evaluation.

Separated from evaluator.py to avoid circular imports with scoring modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvaluationConfig:
    """Configuration for evaluation runs."""

    headless: bool = True
    browser_timeout: int = 30
    screenshot_count: int = 5
    interaction_steps: int = 20
    vlm_model: str = "gpt-4o"


@dataclass
class BuildHealthScore:
    """Score for the Build Health dimension (33% weight)."""

    score: float = 0.0
    compiles: bool = False
    test_passes: bool = False
    error_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class VisualUsabilityScore:
    """Score for the Visual Usability dimension (33% weight)."""

    score: float = 0.0
    renders: bool = False
    responds_to_input: bool = False
    frame_rate_stable: bool = False
    screenshot_path: str | None = None
    issues: list[str] = field(default_factory=list)


@dataclass
class IntentAlignmentScore:
    """Score for the Intent Alignment dimension (34% weight)."""

    score: float = 0.0
    criteria_met: list[str] = field(default_factory=list)
    criteria_missed: list[str] = field(default_factory=list)
    judge_notes: str = ""


@dataclass
class EvaluationResult:
    """Complete evaluation result for a single game."""

    build_health: BuildHealthScore
    visual_usability: VisualUsabilityScore
    intent_alignment: IntentAlignmentScore
    overall: float = 0.0
    duration_ms: int = 0
    game_dir: str = ""
    evaluated_at: str = ""
