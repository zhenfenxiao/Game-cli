"""IntentAlignmentEvaluator — VLM judge for prompt-game alignment.

Uses an LLM (optionally vision-capable) to compare the generated game
against the original user prompt. Falls back to text-only analysis
if no VLM or screenshots are available.
"""

from __future__ import annotations

from pathlib import Path

from opengame.bench.types import EvaluationConfig, IntentAlignmentScore
from opengame.core.llm_client import BaseLlmClient


class IntentAlignmentEvaluator:
    """Evaluate intent alignment using LLM judging.

    Compares the generated game against the original user prompt
    by analyzing GDD content, source code structure, and optionally
    screenshots (VLM mode — requires vision-capable model).
    """

    def __init__(
        self,
        llm_client: BaseLlmClient | None,
        config: EvaluationConfig,
    ) -> None:
        self.llm_client = llm_client
        self.config = config

    async def evaluate(
        self,
        game_dir: Path,
        prompt: str,
        screenshot_path: str | None = None,
    ) -> IntentAlignmentScore:
        """Evaluate how well the game matches the original prompt.

        Args:
            game_dir: Path to the game project.
            prompt: Original user prompt.
            screenshot_path: Optional screenshot for VLM analysis.

        Returns:
            IntentAlignmentScore with criteria evaluation.
        """
        if not self.llm_client:
            # No LLM available — return neutral score
            return IntentAlignmentScore(
                score=0.5,
                criteria_met=["skipped"],
                criteria_missed=["no_llm_available"],
                judge_notes="No LLM client configured; intent alignment check skipped."
            )

        # Gather evidence from the project
        evidence = self._gather_evidence(game_dir)

        system_prompt = """You are a game evaluation judge. Compare the generated game against the user's original prompt and determine how well the game matches the intent.

Evaluate these criteria:
1. **Core concept**: Does the game implement the core concept described in the prompt?
2. **Mechanics**: Are the key mechanics (controls, physics, scoring) present?
3. **Theme/style**: Does the visual/audio style match what was requested?
4. **Completeness**: Is the game feature-complete relative to the prompt scope?
5. **Playability**: Would this be a playable game?

Output a JSON object:
```json
{
  "criteria_met": ["core concept", "mechanics"],
  "criteria_missed": ["theme/style"],
  "score": 0.75,
  "judge_notes": "Brief explanation of the score"
}
```"""

        user_prompt = f"""## Original Prompt
{prompt}

## Generated Game Evidence
{evidence}

Evaluate the alignment between the prompt and the generated game."""

        try:
            response = await self.llm_client.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            return self._parse_response(response.content or "")

        except Exception:
            return IntentAlignmentScore(
                score=0.5,
                criteria_met=["skipped"],
                criteria_missed=["llm_error"],
                judge_notes="LLM judge call failed; returning neutral score."
            )

    @staticmethod
    def _gather_evidence(game_dir: Path) -> str:
        """Gather evidence from the generated project for judging.

        Args:
            game_dir: Path to the game project.

        Returns:
            Formatted evidence string.
        """
        evidence_parts: list[str] = []

        # Check for GDD
        gdd_path = game_dir / "GAME_DESIGN.md"
        if gdd_path.exists():
            gdd_content = gdd_path.read_text("utf-8")[:2000]
            evidence_parts.append(f"### GDD\n{gdd_content}")

        # Check for gameConfig
        config_path = game_dir / "gameConfig.json"
        if config_path.exists():
            evidence_parts.append(f"### gameConfig.json\n{config_path.read_text('utf-8')[:500]}")

        # Check for source files
        src_dir = game_dir / "src"
        if src_dir.exists():
            ts_files = list(src_dir.rglob("*.ts"))
            evidence_parts.append(f"### Source Files ({len(ts_files)} TypeScript files)")
            for f in ts_files[:5]:
                evidence_parts.append(f"  - {f.relative_to(game_dir)}")
                content = f.read_text("utf-8")[:500]
                evidence_parts.append(f"```typescript\n{content}\n```")

        # File tree
        all_files = sorted(
            str(p.relative_to(game_dir))
            for p in game_dir.rglob("*")
            if p.is_file() and "node_modules" not in str(p)
        )[:50]
        evidence_parts.append(f"### File Tree\n" + "\n".join(f"  - {f}" for f in all_files))

        return "\n\n".join(evidence_parts)

    @staticmethod
    def _parse_response(content: str) -> IntentAlignmentScore:
        """Parse LLM JSON response.

        Args:
            content: Raw LLM response.

        Returns:
            Parsed IntentAlignmentScore.
        """
        import json
        import re

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return IntentAlignmentScore(
                    score=float(data.get("score", 0.5)),
                    criteria_met=data.get("criteria_met", []),
                    criteria_missed=data.get("criteria_missed", []),
                    judge_notes=data.get("judge_notes", ""),
                )
            except (json.JSONDecodeError, ValueError):
                pass

        return IntentAlignmentScore(
            score=0.5,
            criteria_met=[],
            criteria_missed=[],
            judge_notes=f"Could not parse judge response: {content[:200]}"
        )
