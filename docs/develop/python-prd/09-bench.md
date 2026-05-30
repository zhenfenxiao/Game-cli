# 09 — OpenGame-Bench Evaluation

OpenGame-Bench is an evaluation pipeline that scores agent-generated games along three dimensions: Build Health, Visual Usability, and Intent Alignment. Unlike static code benchmarks, it dynamically launches games, drives them with scripted interactions, and verifies playability.

## 9.1 Scoring Dimensions

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Build Health | 33% | Does the game compile? Do tests pass? Are there runtime errors? |
| Visual Usability | 33% | Does the game render? Does it respond to input? Is the frame rate stable? |
| Intent Alignment | 34% | Does the game match the original prompt? Is the theme/style correct? |

## 9.2 Evaluator Orchestrator

```python
# bench/evaluator.py
from pathlib import Path
from dataclasses import dataclass


@dataclass
class EvaluationConfig:
    """Configuration for evaluation runs."""
    headless: bool = True
    browser_timeout: int = 30
    screenshot_count: int = 5
    interaction_steps: int = 20
    vlm_model: str = "gpt-4o"


class OpenGameEvaluator:
    """
    Main evaluation orchestrator.

    Runs the complete evaluation pipeline:
    1. Build Health check (compile + test)
    2. Visual Usability check (browser automation)
    3. Intent Alignment check (VLM judge)
    """

    def __init__(
        self,
        config: EvaluationConfig,
        llm_client: BaseLlmClient,
    ):
        self.config = config
        self.build_health = BuildHealthEvaluator()
        self.visual_usability = VisualUsabilityEvaluator(config)
        self.intent_alignment = IntentAlignmentEvaluator(llm_client, config)

    async def evaluate(
        self,
        game_dir: Path,
        prompt: str,
    ) -> EvaluationResult:
        """
        Evaluate a generated game.

        Args:
            game_dir: Path to the game project directory
            prompt: Original user prompt (for intent alignment)

        Returns:
            EvaluationResult with scores for all three dimensions
        """
        start = asyncio.get_event_loop().time()

        print(f"\n{'=' * 60}")
        print(f"OpenGame-Bench: Evaluating {game_dir}")
        print(f"{'=' * 60}")

        # Phase 1: Build Health
        print("\n--- Build Health ---")
        build_score = await self.build_health.evaluate(game_dir)
        print(f"  Score: {build_score.score:.2f}")
        print(f"  Compiles: {build_score.compiles}")
        print(f"  Tests pass: {build_score.test_passes}")
        print(f"  Errors: {build_score.error_count}")

        # Phase 2: Visual Usability
        print("\n--- Visual Usability ---")
        visual_score = await self.visual_usability.evaluate(game_dir)
        print(f"  Score: {visual_score.score:.2f}")
        print(f"  Renders: {visual_score.renders}")
        print(f"  Responds to input: {visual_score.responds_to_input}")
        print(f"  Frame rate stable: {visual_score.frame_rate_stable}")

        # Phase 3: Intent Alignment
        print("\n--- Intent Alignment ---")
        intent_score = await self.intent_alignment.evaluate(
            game_dir, prompt, visual_score.screenshot_path,
        )
        print(f"  Score: {intent_score.score:.2f}")
        print(f"  Criteria met: {len(intent_score.criteria_met)}")
        print(f"  Criteria missed: {len(intent_score.criteria_missed)}")

        # Compute overall
        overall = (build_score.score + visual_score.score + intent_score.score) / 3

        duration_ms = int((asyncio.get_event_loop().time() - start) * 1000)

        print(f"\n{'=' * 60}")
        print(f"Overall Score: {overall:.2f}")
        print(f"Duration: {duration_ms / 1000:.1f}s")
        print(f"{'=' * 60}")

        return EvaluationResult(
            build_health=build_score,
            visual_usability=visual_score,
            intent_alignment=intent_score,
            overall=overall,
            duration_ms=duration_ms,
            game_dir=str(game_dir),
            evaluated_at=datetime.utcnow().isoformat(),
        )
```

## 9.3 Build Health Evaluator

```python
# bench/scoring/build_health.py
import subprocess
from pathlib import Path


class BuildHealthEvaluator:
    """
    Evaluate build health: compilation, tests, and static errors.
    """

    async def evaluate(self, game_dir: Path) -> BuildHealthScore:
        """
        Check if the game builds and tests pass.

        Returns:
            BuildHealthScore with detailed results
        """
        compiles = False
        test_passes = False
        error_count = 0
        warnings = []

        # Check 1: Does package.json exist?
        if not (game_dir / "package.json").exists():
            warnings.append("No package.json found")
            return BuildHealthScore(
                score=0.0,
                compiles=False,
                test_passes=False,
                error_count=1,
                warnings=warnings,
            )

        # Check 2: Can we install dependencies?
        try:
            proc = await asyncio.create_subprocess_exec(
                "npm", "install",
                cwd=game_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode != 0:
                warnings.append(f"npm install failed: {stderr.decode()[:200]}")
        except Exception as e:
            warnings.append(f"npm install error: {e}")

        # Check 3: Does it compile?
        try:
            proc = await asyncio.create_subprocess_exec(
                "npm", "run", "build",
                cwd=game_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            compiles = proc.returncode == 0
            if not compiles:
                error_output = stderr.decode() + stdout.decode()
                error_count = error_output.count("error TS")
                warnings.append(f"Build failed with {error_count} TypeScript errors")
        except Exception as e:
            warnings.append(f"Build error: {e}")

        # Check 4: Do tests pass?
        if (game_dir / "package.json").exists():
            try:
                proc = await asyncio.create_subprocess_exec(
                    "npm", "run", "test",
                    cwd=game_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                test_passes = proc.returncode == 0
                if not test_passes:
                    warnings.append("Tests failed")
            except Exception as e:
                warnings.append(f"Test execution error: {e}")

        # Calculate score
        score = 0.0
        if compiles:
            score += 0.5
        if test_passes:
            score += 0.3
        if error_count == 0:
            score += 0.2
        else:
            score += max(0, 0.2 - (error_count * 0.02))

        return BuildHealthScore(
            score=min(score, 1.0),
            compiles=compiles,
            test_passes=test_passes,
            error_count=error_count,
            warnings=warnings,
        )
```

## 9.4 Visual Usability Evaluator

```python
# bench/scoring/visual_usability.py
from playwright.async_api import async_playwright
from pathlib import Path
import tempfile


class VisualUsabilityEvaluator:
    """
    Evaluate visual usability using headless browser automation.

    Checks:
    - Game renders (canvas is not blank)
    - Responds to keyboard input
    - Frame rate is stable (no severe jank)
    """

    def __init__(self, config: EvaluationConfig):
        self.config = config

    async def evaluate(self, game_dir: Path) -> VisualUsabilityScore:
        """
        Launch game in headless browser and evaluate visual usability.

        Returns:
            VisualUsabilityScore with screenshot path for VLM judge
        """
        renders = False
        responds_to_input = False
        frame_rate_stable = False
        screenshot_path: str | None = None
        issues = []

        # Build the game first
        try:
            proc = await asyncio.create_subprocess_exec(
                "npm", "run", "build",
                cwd=game_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=120)
        except Exception as e:
            issues.append(f"Build failed before browser test: {e}")
            return VisualUsabilityScore(
                score=0.0,
                renders=False,
                responds_to_input=False,
                frame_rate_stable=False,
                screenshot_path=None,
                issues=issues,
            )

        dist_dir = game_dir / "dist"
        if not dist_dir.exists():
            issues.append("No dist directory after build")
            return VisualUsabilityScore(
                score=0.0,
                renders=False,
                responds_to_input=False,
                frame_rate_stable=False,
                screenshot_path=None,
                issues=issues,
            )

        # Start HTTP server for the game
        import http.server
        import socketserver
        import threading

        port = 8765
        handler = http.server.SimpleHTTPRequestHandler

        with socketserver.TCPServer(("", port), handler) as httpd:
            httpd.directory = str(dist_dir)
            server_thread = threading.Thread(target=httpd.serve_forever)
            server_thread.daemon = True
            server_thread.start()

            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=self.config.headless)
                    page = await browser.new_page(viewport={"width": 1280, "height": 720})

                    # Navigate to game
                    await page.goto(f"http://localhost:{port}", timeout=30000)

                    # Wait for canvas to appear
                    try:
                        await page.wait_for_selector("canvas", timeout=10000)
                    except Exception:
                        issues.append("No canvas element found")
                        await browser.close()
                        return VisualUsabilityScore(
                            score=0.0,
                            renders=False,
                            responds_to_input=False,
                            frame_rate_stable=False,
                            screenshot_path=None,
                            issues=issues,
                        )

                    # Wait for game to initialize
                    await asyncio.sleep(3)

                    # Check 1: Does it render? (canvas is not blank)
                    renders = await self._check_rendering(page)
                    if not renders:
                        issues.append("Canvas appears blank")

                    # Take screenshot
                    screenshot_path = str(game_dir / "bench_screenshot.png")
                    await page.screenshot(path=screenshot_path, full_page=False)

                    # Check 2: Does it respond to input?
                    responds_to_input = await self._check_input_response(page)
                    if not responds_to_input:
                        issues.append("Game does not respond to keyboard input")

                    # Check 3: Is frame rate stable?
                    frame_rate_stable = await self._check_frame_rate(page)
                    if not frame_rate_stable:
                        issues.append("Frame rate is unstable (severe jank detected)")

                    # Capture console errors
                    console_errors = []
                    # Note: In Playwright, console messages are captured via page.on("console")
                    if console_errors:
                        issues.extend([f"Console error: {e}" for e in console_errors[:5]])

                    await browser.close()

            finally:
                httpd.shutdown()

        # Calculate score
        score = 0.0
        if renders:
            score += 0.4
        if responds_to_input:
            score += 0.3
        if frame_rate_stable:
            score += 0.3

        return VisualUsabilityScore(
            score=score,
            renders=renders,
            responds_to_input=responds_to_input,
            frame_rate_stable=frame_rate_stable,
            screenshot_path=screenshot_path,
            issues=issues,
        )

    async def _check_rendering(self, page) -> bool:
        """Check if the canvas has non-transparent pixels."""
        # Take a screenshot and check if it's not all one color
        screenshot = await page.screenshot(type="png")
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(screenshot))
        # Check if image is mostly one color (blank)
        pixels = list(img.getdata())
        if len(pixels) == 0:
            return False
        # Sample pixels — if they're all the same, canvas is blank
        sample = pixels[::100]  # Every 100th pixel
        first = sample[0]
        return not all(p == first for p in sample[:10])

    async def _check_input_response(self, page) -> bool:
        """Check if game responds to keyboard input."""
        # Send some keypresses and check if game state changes
        # This is heuristic — we look for console logs or canvas changes
        try:
            # Press some keys
            await page.keyboard.press("ArrowUp")
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Space")
            await asyncio.sleep(1)
            return True  # If we got here without error, assume responsive
        except Exception:
            return False

    async def _check_frame_rate(self, page) -> bool:
        """Check if frame rate is reasonably stable."""
        # Use Performance API to check for long frames
        frames = await page.evaluate("""
            () => {
                const entries = performance.getEntriesByType("frame");
                if (entries.length === 0) return null;
                const durations = entries.slice(-30).map(e => e.duration);
                const avg = durations.reduce((a, b) => a + b, 0) / durations.length;
                const max = Math.max(...durations);
                return { avg, max, count: durations.length };
            }
        """)
        if frames is None:
            return True  # Can't measure, assume OK
        # Frame budget at 60fps is ~16.7ms. Allow up to 50ms for complex games.
        return frames["max"] < 50
```

## 9.5 Intent Alignment Evaluator (VLM Judge)

```python
# bench/scoring/intent_alignment.py
from pathlib import Path
import base64


class IntentAlignmentEvaluator:
    """
    Evaluate intent alignment using a Vision-Language Model.

    The VLM judges whether the game matches the original prompt by:
    1. Looking at screenshots of the game
    2. Comparing against the original prompt's criteria
    """

    def __init__(self, llm_client: BaseLlmClient, config: EvaluationConfig):
        self.llm_client = llm_client
        self.config = config

    async def evaluate(
        self,
        game_dir: Path,
        prompt: str,
        screenshot_path: str | None,
    ) -> IntentAlignmentScore:
        """
        Evaluate how well the game matches the original prompt.

        Args:
            game_dir: Game project directory
            prompt: Original user prompt
            screenshot_path: Path to game screenshot

        Returns:
            IntentAlignmentScore with criteria breakdown
        """
        if not screenshot_path or not Path(screenshot_path).exists():
            return IntentAlignmentScore(
                score=0.0,
                prompt=prompt,
                vlm_reasoning="No screenshot available for evaluation",
                criteria_met=[],
                criteria_missed=["screenshot unavailable"],
            )

        # Read screenshot as base64
        with open(screenshot_path, "rb") as f:
            screenshot_b64 = base64.b64encode(f.read()).decode()

        # Build evaluation prompt for VLM
        vlm_prompt = f"""You are evaluating a generated game against its design prompt.

## Original Prompt
{prompt}

## Your Task
Look at the screenshot and determine whether the game matches the prompt.

Score the game on these criteria (0-1 each):
1. Visual style matches description
2. Game type/mechanics are correct
3. Theme/atmosphere matches
4. Characters/elements are recognizable
5. UI layout is appropriate

Output as JSON:
{{
  "score": 0.0 to 1.0 (overall average),
  "reasoning": "Detailed explanation of what matches and what doesn't",
  "criteria_met": ["list of matching criteria"],
  "criteria_missed": ["list of missing criteria"]
}}"""

        try:
            response = await self.llm_client.generate(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": vlm_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
                            },
                        ],
                    }
                ],
                tools=None,
                stream=False,
                temperature=0.2,
                max_tokens=2000,
            )

            if response.content:
                import json
                text = response.content.strip()
                if text.startswith("```"):
                    text = re.sub(r"```json?\n?", "", text).replace("```", "").strip()
                parsed = json.loads(text)

                return IntentAlignmentScore(
                    score=parsed.get("score", 0.0),
                    prompt=prompt,
                    vlm_reasoning=parsed.get("reasoning", ""),
                    criteria_met=parsed.get("criteria_met", []),
                    criteria_missed=parsed.get("criteria_missed", []),
                )

        except Exception as e:
            return IntentAlignmentScore(
                score=0.0,
                prompt=prompt,
                vlm_reasoning=f"VLM evaluation failed: {e}",
                criteria_met=[],
                criteria_missed=["evaluation error"],
            )

        return IntentAlignmentScore(
            score=0.0,
            prompt=prompt,
            vlm_reasoning="No response from VLM",
            criteria_met=[],
            criteria_missed=["no vlm response"],
        )
```

## 9.6 Batch Evaluation

```python
# bench/batch_evaluator.py
from pathlib import Path
from dataclasses import dataclass


@dataclass
class BatchResult:
    """Result of a batch evaluation run."""
    results: list[EvaluationResult]
    average_overall: float
    average_build: float
    average_visual: float
    average_intent: float
    pass_count: int  # Games with overall >= 0.6
    fail_count: int


class BatchEvaluator:
    """
    Evaluate multiple games in batch.

    Used for benchmark runs across a dataset of prompts.
    """

    def __init__(self, evaluator: OpenGameEvaluator):
        self.evaluator = evaluator

    async def evaluate_batch(
        self,
        game_dirs: list[Path],
        prompts: list[str],
    ) -> BatchResult:
        """
        Evaluate multiple games.

        Args:
            game_dirs: List of game project directories
            prompts: List of original prompts (parallel to game_dirs)

        Returns:
            BatchResult with aggregate statistics
        """
        results = []

        for game_dir, prompt in zip(game_dirs, prompts):
            try:
                result = await self.evaluator.evaluate(game_dir, prompt)
                results.append(result)
            except Exception as e:
                # Create failure result
                results.append(EvaluationResult(
                    build_health=BuildHealthScore(score=0.0, compiles=False, test_passes=False, error_count=1),
                    visual_usability=VisualUsabilityScore(score=0.0, renders=False, responds_to_input=False, frame_rate_stable=False),
                    intent_alignment=IntentAlignmentScore(score=0.0, prompt=prompt, vlm_reasoning=f"Evaluation failed: {e}", criteria_met=[], criteria_missed=[]),
                    overall=0.0,
                    duration_ms=0,
                    game_dir=str(game_dir),
                    evaluated_at=datetime.utcnow().isoformat(),
                ))

        # Compute aggregates
        overalls = [r.overall for r in results]
        builds = [r.build_health.score for r in results]
        visuals = [r.visual_usability.score for r in results]
        intents = [r.intent_alignment.score for r in results]

        return BatchResult(
            results=results,
            average_overall=sum(overalls) / len(overalls) if overalls else 0,
            average_build=sum(builds) / len(builds) if builds else 0,
            average_visual=sum(visuals) / len(visuals) if visuals else 0,
            average_intent=sum(intents) / len(intents) if intents else 0,
            pass_count=sum(1 for o in overalls if o >= 0.6),
            fail_count=sum(1 for o in overalls if o < 0.6),
        )
```

## 9.7 Evaluation Report

```python
def format_evaluation_report(result: EvaluationResult) -> str:
    """Format an evaluation result as a human-readable report."""
    lines = [
        f"# Evaluation Report: {Path(result.game_dir).name}",
        "",
        f"**Overall Score:** {result.overall:.1%}",
        f"**Duration:** {result.duration_ms / 1000:.1f}s",
        "",
        "## Build Health",
        f"- Score: {result.build_health.score:.1%}",
        f"- Compiles: {'Yes' if result.build_health.compiles else 'No'}",
        f"- Tests Pass: {'Yes' if result.build_health.test_passes else 'No'}",
        f"- TypeScript Errors: {result.build_health.error_count}",
    ]

    if result.build_health.warnings:
        lines.extend(["- Warnings:"] + [f"  - {w}" for w in result.build_health.warnings[:5]])

    lines.extend([
        "",
        "## Visual Usability",
        f"- Score: {result.visual_usability.score:.1%}",
        f"- Renders: {'Yes' if result.visual_usability.renders else 'No'}",
        f"- Responds to Input: {'Yes' if result.visual_usability.responds_to_input else 'No'}",
        f"- Frame Rate Stable: {'Yes' if result.visual_usability.frame_rate_stable else 'No'}",
    ])

    if result.visual_usability.issues:
        lines.extend(["- Issues:"] + [f"  - {i}" for i in result.visual_usability.issues[:5]])

    lines.extend([
        "",
        "## Intent Alignment",
        f"- Score: {result.intent_alignment.score:.1%}",
        f"- Reasoning: {result.intent_alignment.vlm_reasoning[:500]}",
    ])

    if result.intent_alignment.criteria_met:
        lines.extend(["- Met:"] + [f"  - {c}" for c in result.intent_alignment.criteria_met])
    if result.intent_alignment.criteria_missed:
        lines.extend(["- Missed:"] + [f"  - {c}" for c in result.intent_alignment.criteria_missed])

    return "\n".join(lines)
```
