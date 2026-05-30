"""Classifier — determines a game's archetype from physics signals.

Uses LLM-first classification with keyword-based heuristic fallback.
Library-aware: checks existing families before minting new archetypes.
"""

from __future__ import annotations

import json
import re
from typing import Any

from opengame.core.llm_client import BaseLlmClient
from opengame.skills.template_skill.types import (
    ClassificationResult,
    PhysicsProfile,
    ProjectSnapshot,
    TemplateLibrary,
)

# Keyword patterns for 5 archetypes (reused from game_tools.py)
ARCHETYPE_KEYWORDS: dict[str, dict[str, Any]] = {
    "platformer": {
        "keywords": ["platform", "jump", "gravity", "side-scroll", "side view",
                      "runner", "mario", "ledge", "falling", "wall jump"],
        "physics": {"has_gravity": True, "perspective": "side", "movement_type": "continuous"},
    },
    "top_down": {
        "keywords": ["top-down", "top down", "topdown", "bird's eye", "overhead",
                      "zelda", "rpg", "shooter", "bullet hell", "roguelike"],
        "physics": {"has_gravity": False, "perspective": "top_down", "movement_type": "continuous"},
    },
    "grid_logic": {
        "keywords": ["grid", "puzzle", "match-3", "match three", "tetris",
                      "snake", "sudoku", "minesweeper", "tile", "board",
                      "chess", "checkers", "turn-based", "turn based"],
        "physics": {"has_gravity": False, "perspective": "top_down", "movement_type": "grid"},
    },
    "tower_defense": {
        "keywords": ["tower defense", "tower defence", "tower-defense", "td",
                      "wave", "path", "enemy wave", "defend", "turrets", "maze"],
        "physics": {"has_gravity": False, "perspective": "top_down", "movement_type": "path"},
    },
    "ui_heavy": {
        "keywords": ["idle", "clicker", "incremental", "management", "sim",
                      "tycoon", "visual novel", "text-based", "card game",
                      "menu-driven", "quiz", "trivia", "menu"],
        "physics": {"has_gravity": False, "perspective": "none", "movement_type": "ui_only"},
    },
}


class Classifier:
    """Classify a game project into one of 5 archetypes.

    Strategy: LLM-first with library awareness, falling back to
    keyword-based heuristic if the LLM call fails.
    """

    def __init__(self, llm_client: BaseLlmClient) -> None:
        self.llm_client = llm_client

    async def classify(
        self,
        snapshot: ProjectSnapshot,
        library: TemplateLibrary,
    ) -> ClassificationResult:
        """Classify a project snapshot.

        Args:
            snapshot: The project to classify.
            library: Current template library for family matching.

        Returns:
            ClassificationResult with archetype, confidence, and physics profile.
        """
        # Try LLM-first
        try:
            return await self._try_llm_classify(snapshot, library)
        except Exception:
            pass

        # Fallback to heuristic
        return self._heuristic_classify(snapshot, library)

    # --- LLM classification ---

    async def _try_llm_classify(
        self,
        snapshot: ProjectSnapshot,
        library: TemplateLibrary,
    ) -> ClassificationResult:
        """Attempt LLM-based classification."""
        system_prompt = self._build_system_prompt(library)
        user_prompt = self._build_user_prompt(snapshot)

        response = await self.llm_client.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=500,
        )

        return self._parse_llm_response(response.content or "", snapshot, library)

    def _build_system_prompt(self, library: TemplateLibrary) -> str:
        """Build the classifier system prompt with library families."""
        families_section = self._build_families_section(library)

        return f"""You are a game archetype classifier. Analyze the provided code and determine the game's archetype.

## Available Archetypes
- platformer: Has gravity, side-view perspective, continuous movement (jumping, running)
- top_down: No gravity, top-down perspective, continuous movement (shooting, exploring)
- grid_logic: No gravity, top-down perspective, discrete grid movement (puzzles, snake)
- tower_defense: No gravity, top-down perspective, path-based movement (waves, turrets)
- ui_heavy: No gravity, no perspective, UI-only interaction (clickers, management)

## Physics Signals to Look For
1. **Gravity**: Look for gravity/velocityY/gravityScale in config or physics code
2. **Perspective**: Side-view (platformer), top-down, or none
3. **Movement**: Continuous, grid-discrete, path-based, or UI-only

{families_section}

Output ONLY a JSON object with:
- archetype: string (one of the 5 archetypes above)
- reasoning: string (cite specific code evidence)
- physics_profile: {{has_gravity: bool, perspective: string, movement_type: string}}
- confidence: number (0.0 to 1.0)
- is_new_family: bool

## JSON Output"""

    def _build_families_section(self, library: TemplateLibrary) -> str:
        """Build a section describing existing library families."""
        if not library.families:
            return "## Existing Families\nNo existing families. This will be the first."

        lines = ["## Existing Families"]
        for fam in library.families:
            lines.append(
                f"- **{fam.archetype}** (stability: {fam.stability:.1f}, "
                f"projects: {len(fam.contributing_projects)})"
            )
        return "\n".join(lines)

    def _build_user_prompt(self, snapshot: ProjectSnapshot) -> str:
        """Build the user prompt with project code summary."""
        return f"""## Project to Classify

Code Summary:
{snapshot.code_summary}

File Tree:
{chr(10).join(snapshot.file_tree[:30])}

Please classify this project."""

    def _parse_llm_response(
        self, content: str, snapshot: ProjectSnapshot, library: TemplateLibrary,
    ) -> ClassificationResult:
        """Parse the LLM's JSON response into a ClassificationResult."""
        # Strip markdown fences
        content = re.sub(r"```(?:json)?\s*", "", content)
        content = content.strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from text
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return self._heuristic_classify(snapshot, library)
            else:
                return self._heuristic_classify(snapshot, library)

        return ClassificationResult(
            archetype=data.get("archetype", "platformer"),
            reasoning=data.get("reasoning", ""),
            physics_profile=PhysicsProfile(**data.get("physics_profile", {
                "has_gravity": True,
                "perspective": "side",
                "movement_type": "continuous",
            })),
            confidence=data.get("confidence", 0.5),
            is_new_family=data.get("is_new_family", True),
        )

    # --- Heuristic classification ---

    def _heuristic_classify(
        self,
        snapshot: ProjectSnapshot,
        library: TemplateLibrary,
    ) -> ClassificationResult:
        """Keyword-based heuristic classification with library matching."""
        # Combine all text content for keyword matching
        all_text = snapshot.code_summary.lower()
        for f in snapshot.files[:20]:  # Sample first 20 files
            all_text += " " + f.content.lower()[:1000]

        scores: dict[str, int] = {}
        for archetype, info in ARCHETYPE_KEYWORDS.items():
            score = sum(1 for kw in info["keywords"] if kw in all_text)
            scores[archetype] = score

        best = max(scores, key=scores.get)
        best_score = scores[best]

        if best_score == 0:
            best = "platformer"
            confidence = 0.3
            reasoning = "No strong physics signals detected; defaulting to platformer"
        else:
            total = sum(scores.values()) or 1
            confidence = min(0.9, best_score / max(1, total / len(scores)))
            matched_keywords = [kw for kw in ARCHETYPE_KEYWORDS[best]["keywords"] if kw in all_text]
            reasoning = f"Keyword matches: {', '.join(matched_keywords[:5])}"

        physics_info = ARCHETYPE_KEYWORDS[best]["physics"]
        physics = PhysicsProfile(**physics_info)

        # Check if this matches an existing family
        is_new = True
        for fam in library.families:
            if fam.archetype == best:
                is_new = False
                break

        return ClassificationResult(
            archetype=best,
            reasoning=reasoning,
            physics_profile=physics,
            confidence=round(confidence, 2),
            is_new_family=is_new,
        )
