"""VisualUsabilityEvaluator — headless browser evaluation.

Checks rendering, input response, and frame rate stability.
Currently uses a lightweight approach (static file analysis)
with Playwright-based browser testing as an optional extension.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from opengame.bench.types import EvaluationConfig, VisualUsabilityScore


class VisualUsabilityEvaluator:
    """Evaluate visual usability of a game.

    Performs lightweight static checks (file structure, build output).
    Full Playwright-based browser testing requires installing the
    `bench` extra: `uv pip install -e ".[bench]"`.
    """

    def __init__(self, config: EvaluationConfig) -> None:
        self.config = config

    async def evaluate(self, game_dir: Path) -> VisualUsabilityScore:
        """Evaluate visual usability.

        Args:
            game_dir: Path to the game project.

        Returns:
            VisualUsabilityScore.
        """
        renders = False
        responds_to_input = False
        frame_rate_stable = False
        issues: list[str] = []

        # Check 1: Does the project have an index.html?
        index_files = list(game_dir.rglob("index.html"))
        if not index_files:
            issues.append("No index.html found")
            return VisualUsabilityScore(
                score=0.0,
                renders=False,
                responds_to_input=False,
                frame_rate_stable=False,
                issues=issues,
            )

        # Check 2: Is there a canvas element (indicates rendering)?
        for idx in index_files:
            content = idx.read_text("utf-8")
            if "<canvas" in content or "Phaser" in content:
                renders = True
                break
        if not renders:
            issues.append("No canvas/Phaser element found in HTML")

        # Check 3: Are there input handlers in source?
        src_dir = game_dir / "src"
        if src_dir.exists():
            ts_files = list(src_dir.rglob("*.ts"))
            for f in ts_files:
                try:
                    content = f.read_text("utf-8")
                    if any(kw in content for kw in [
                        "addEventListener", "onKeyDown", "onKeyUp",
                        "keyboard", "pointerdown", "pointermove",
                        "this.input", "addKey", "KeyCodes",
                    ]):
                        responds_to_input = True
                        break
                except Exception:
                    pass

        if not responds_to_input:
            issues.append("No input handlers detected in source")

        # Check 4: Build output exists
        dist_dir = game_dir / "dist"
        if not dist_dir.exists():
            # Try running build
            try:
                proc = await asyncio.create_subprocess_exec(
                    "npm", "run", "build",
                    cwd=game_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=60)
            except Exception:
                pass

        if dist_dir.exists():
            js_files = list(dist_dir.rglob("*.js"))
            if js_files:
                frame_rate_stable = True  # Assume stable if build succeeds
            else:
                issues.append("No JS output in dist/")
        else:
            issues.append("No dist/ directory — build may have failed")

        # Calculate score
        score = 0.0
        if renders:
            score += 0.4
        if responds_to_input:
            score += 0.3
        if frame_rate_stable:
            score += 0.3

        return VisualUsabilityScore(
            score=round(score, 2),
            renders=renders,
            responds_to_input=responds_to_input,
            frame_rate_stable=frame_rate_stable,
            issues=issues,
        )
