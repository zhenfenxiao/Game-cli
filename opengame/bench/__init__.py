"""OpenGame-Bench — evaluation pipeline for agent-generated games.

Scores games along three dimensions:
1. Build Health (33%) — compilation, tests, runtime errors
2. Visual Usability (33%) — rendering, input response, frame rate
3. Intent Alignment (34%) — match with original prompt (VLM judge)
"""

from opengame.bench.evaluator import OpenGameEvaluator
from opengame.bench.types import EvaluationConfig

__all__ = ["OpenGameEvaluator", "EvaluationConfig"]
