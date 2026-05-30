"""GameSkill — 6-phase game generation orchestrator.

Phases:
  1. Classification & Scaffolding — classify prompt, copy core + archetype templates
  2. GDD Generation — LLM-generated 6-section Game Design Document
  3. Asset Generation — parse specs, generate images/audio/video (stub for Phase 4)
  4. Config & Registration — update gameConfig.json, main.ts, LevelManager.ts
  5. Code Implementation — delegate to TurnLoop agent with tools
  6. Debug & Verification — delegate to DebugSkill REPEAT...UNTIL loop
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from opengame.config.models import OpenGameConfig
from opengame.core.llm_client import BaseLlmClient
from opengame.core.tool_registry import ToolRegistry
from opengame.core.turn_loop import TurnLoop
from opengame.skills.debug_skill import DebugSkill, ProtocolManager
from opengame.skills.debug_skill.types import DebugTrace
from opengame.skills.game_types import (
    AssetSpec,
    GameDesignDocument,
    GameResult,
    GddSection,
    GeneratedAsset,
)
from opengame.skills.template_skill import TemplateSkill
from opengame.skills.template_skill.library_manager import LibraryManager

# Archetype classification keywords (shared with tools/game_tools.py)
ARCHETYPE_KEYWORDS: dict[str, list[str]] = {
    "platformer": ["platform", "jump", "gravity", "side-scroll", "mario", "runner"],
    "top_down": ["top-down", "top down", "shooter", "zelda", "rpg", "overhead"],
    "grid_logic": ["grid", "puzzle", "snake", "tetris", "match-3", "tile", "turn-based"],
    "tower_defense": ["tower defense", "tower defence", "wave", "defend", "turret"],
    "ui_heavy": ["idle", "clicker", "incremental", "management", "visual novel", "quiz"],
}


class GameSkill:
    """6-phase game generation orchestrator.

    Takes a natural language prompt and produces a complete
    Phaser 3 + TypeScript + Vite web game.

    Usage:
        skill = GameSkill(llm_client, template_skill, debug_skill, tool_registry, config)
        result = await skill.generate_game(
            prompt="Build a Snake clone with WASD controls",
            output_dir=Path("./my-game"),
        )
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        template_skill: TemplateSkill,
        debug_skill: DebugSkill,
        tool_registry: ToolRegistry,
        config: OpenGameConfig,
    ) -> None:
        self.llm_client = llm_client
        self.template_skill = template_skill
        self.debug_skill = debug_skill
        self.tool_registry = tool_registry
        self.config = config
        self._tracer = None  # injected via set_tracer()

    def set_tracer(self, tracer: Any) -> None:
        """Inject a TraceSession for event recording."""
        self._tracer = tracer

    async def generate_game(
        self,
        prompt: str,
        output_dir: str | Path,
    ) -> GameResult:
        """Run the full 6-phase game generation pipeline.

        Args:
            prompt: Natural language game description.
            output_dir: Directory to create the game project in.

        Returns:
            GameResult with success status, GDD, assets, and debug trace.
        """
        root = Path(output_dir).resolve()
        start_time = time.monotonic()

        def _log(msg: str) -> None:
            from rich.console import Console
            Console().print(msg)

        trace = self._tracer

        try:
            # Phase 1: Classify and scaffold
            _log("[bold cyan]Phase 1/6[/] Classifying & scaffolding...")
            if trace: trace.phase_start("scaffold", prompt[:100])
            archetype = self._phase_1_classify_and_scaffold(prompt, root)
            _log(f"  → Archetype: [green]{archetype}[/green]")
            if trace: trace.phase_end("scaffold", archetype)

            # Phase 2: Generate GDD
            _log("[bold cyan]Phase 2/6[/] Generating Game Design Document...")
            if trace: trace.phase_start("gdd", f"archetype={archetype}")
            gdd = await self._phase_2_generate_gdd(prompt, archetype, root)
            _log(f"  → GDD: [green]{gdd.title}[/green] ({len(gdd.sections)} sections)")
            if trace: trace.phase_end("gdd", gdd.title, {"sections": len(gdd.sections)})

            # Phase 3: Generate assets
            _log("[bold cyan]Phase 3/6[/] Generating assets...")
            if trace: trace.phase_start("assets")
            assets = await self._phase_3_generate_assets(gdd, root)
            _log(f"  → Assets: [green]{len(assets)} generated[/green]")
            if trace: trace.phase_end("assets", "", {"count": len(assets)})

            # Phase 4: Config and registration
            _log("[bold cyan]Phase 4/6[/] Updating config & registration...")
            if trace: trace.phase_start("config")
            self._phase_4_config_and_registration(gdd, archetype, root)
            _log("  → [green]Done[/green]")
            if trace: trace.phase_end("config")

            # Phase 5: Code implementation
            _log("[bold cyan]Phase 5/6[/] Implementing game code (TurnLoop agent)...")
            if trace: trace.phase_start("implementation")
            await self._phase_5_implement_code(prompt, gdd, archetype, root)
            _log("  → [green]Implementation complete[/green]")
            if trace: trace.phase_end("implementation")

            # Phase 6: Debug and verification
            _log("[bold cyan]Phase 6/6[/] Debugging & verifying...")
            if trace: trace.phase_start("debug")
            debug_result = await self._phase_6_debug(root)
            _log(f"  → {'[green]PASSED[/green]' if debug_result.success else '[yellow]FAILED[/yellow]'} "
                 f"({debug_result.trace.total_iterations} iterations)")
            if trace: trace.phase_end("debug", str(debug_result.success),
                {"iterations": debug_result.trace.total_iterations})

            # Phase 7: Evolve template library (learn from the generated game)
            if self.config.game_skill.evolve_after_debug:
                _log("[bold cyan]Evolving template library[/] from generated game...")
                if trace: trace.phase_start("evolve")
                try:
                    import uuid
                    task_id = f"gen-{uuid.uuid4()!s:.8}"
                    library = await self.template_skill.evolve(root, task_id)
                    _log(f"  → Library v{library.version}, {len(library.families)} families")
                    if trace: trace.phase_end("evolve", "", {"library_version": library.version, "families": len(library.families)})
                except Exception as e:
                    _log(f"  → [yellow]Evolution skipped: {e}[/yellow]")
                    if trace: trace.error("evolve", str(e))

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            return GameResult(
                success=debug_result.success,
                project_dir=root,
                gdd=gdd,
                assets=assets,
                debug_trace=debug_result.trace,
                duration_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            if trace: trace.error("pipeline", str(e), type(e).__name__)
            return GameResult(
                success=False,
                project_dir=root,
                duration_ms=elapsed_ms,
                error=str(e),
            )

    # --- Phase 1: Classification & Scaffolding ---

    def _phase_1_classify_and_scaffold(self, prompt: str, output_dir: Path) -> str:
        """Classify the game prompt and scaffold the project."""
        archetype = self._classify_from_prompt(prompt)

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Copy core template
        core_dir = self.config.game_skill.templates_dir / "core"
        if core_dir.exists():
            self._copy_tree(core_dir, output_dir)

        # Copy archetype module
        archetype_dir = self.config.game_skill.archetypes_dir / archetype
        target_src = output_dir / "src"
        target_src.mkdir(parents=True, exist_ok=True)
        if archetype_dir.exists():
            self._copy_tree(archetype_dir, target_src)

        # Copy docs
        docs_dir = self.config.game_skill.docs_dir
        target_docs = output_dir / "docs"
        if docs_dir.exists():
            target_docs.mkdir(parents=True, exist_ok=True)
            self._copy_tree(docs_dir, target_docs)

        return archetype

    def _classify_from_prompt(self, prompt: str) -> str:
        """Classify a game prompt using keyword heuristics."""
        prompt_lower = prompt.lower()
        scores: dict[str, int] = {}

        for archetype, keywords in ARCHETYPE_KEYWORDS.items():
            scores[archetype] = sum(1 for kw in keywords if kw in prompt_lower)

        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "platformer"

    @staticmethod
    def _copy_tree(src: Path, dst: Path) -> None:
        """Copy directory tree, creating destination if needed."""
        if not src.exists():
            return
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)

    # --- Phase 2: GDD Generation ---

    async def _phase_2_generate_gdd(
        self, prompt: str, archetype: str, output_dir: Path,
    ) -> GameDesignDocument:
        """Generate a 6-section Game Design Document."""
        system_prompt = """You are a game designer. Create a comprehensive Game Design Document (GDD).

The GDD must have exactly 6 sections, each with a clear ## header:
## 1. Game Overview — title, concept, target audience
## 2. Core Mechanics — controls, physics, scoring, game loop
## 3. Level Design — layout, progression, difficulty
## 4. Art and Audio — visual style, color palette, sound effects, music
## 5. Technical Specs — resolution 800x600, Phaser 3, TypeScript, Vite, performance
## 6. Implementation Plan — development phases, milestones

Include specific details: control keys, scoring rules, level layouts, asset lists."""

        user_prompt = f"""Create a Game Design Document for the following game:

**Prompt:** {prompt}
**Archetype:** {archetype}

Be specific and detailed. Include concrete control schemes, scoring formulas, and level layouts."""

        response = await self.llm_client.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
        )

        gdd_content = response.content or ""
        gdd = self._parse_gdd(gdd_content, archetype)

        # Save GDD to output
        (output_dir / "GAME_DESIGN.md").write_text(gdd_content, encoding="utf-8")

        return gdd

    @staticmethod
    def _parse_gdd(content: str, archetype: str) -> GameDesignDocument:
        """Parse GDD markdown into structured sections."""
        # Extract title: first # heading that is NOT a section number
        title = "Untitled Game"
        for match in re.finditer(r"#\s*(.+)", content):
            candidate = match.group(1).strip()
            # Skip if it looks like "1. Game Overview" (section header)
            if not re.match(r"\d+\.\s", candidate):
                title = candidate
                break

        # Split into 6 sections (only valid section numbers 1-6)
        sections: list[GddSection] = []
        seen_numbers: set[int] = set()
        section_pattern = re.compile(
            r"##\s*(\d+)\.?\s*(.+?)\n(.*?)(?=##\s*\d|\Z)", re.DOTALL,
        )
        for match in section_pattern.finditer(content):
            num = int(match.group(1))
            if num < 1 or num > 6 or num in seen_numbers:
                continue
            seen_numbers.add(num)
            sec_title = match.group(2).strip()
            sec_content = match.group(3).strip()
            sections.append(GddSection(section_number=num, title=sec_title, content=sec_content))

        return GameDesignDocument(
            title=title,
            archetype=archetype,
            sections=sections,
        )

    # --- Phase 3: Asset Generation ---

    async def _phase_3_generate_assets(
        self, gdd: GameDesignDocument, output_dir: Path,
    ) -> list[GeneratedAsset]:
        """Parse asset specs from GDD and generate them via AssetService.

        Falls back to placeholder files if no asset service is available
        or if generation fails for individual assets.
        """
        specs = self._parse_asset_specs(gdd)

        if not specs:
            return []

        assets_dir = output_dir / "public" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        generated: list[GeneratedAsset] = []

        # Try to use AssetService if available
        asset_service = getattr(self, "_asset_service", None)

        for spec in specs:
            output_path = assets_dir / (spec.key + "." + spec.format)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                if asset_service and spec.type == "image":
                    start_time = int(time.monotonic() * 1000)
                    image_path = await asset_service.generate_image(
                        prompt=spec.description or spec.key,
                        output_path=output_path,
                        style="pixel_art",
                        size=spec.size or "512x512",
                    )
                    elapsed = int(time.monotonic() * 1000) - start_time
                    generated.append(GeneratedAsset(
                        spec=spec,
                        output_path=image_path,
                        generation_time_ms=elapsed,
                        provider="tongyi" if self.config.image else "placeholder",
                    ))
                elif asset_service and spec.type == "audio":
                    start_time = int(time.monotonic() * 1000)
                    audio_path = await asset_service.generate_audio(
                        prompt=spec.description or spec.key,
                        output_path=output_path,
                    )
                    elapsed = int(time.monotonic() * 1000) - start_time
                    generated.append(GeneratedAsset(
                        spec=spec,
                        output_path=audio_path,
                        generation_time_ms=elapsed,
                        provider="openai-compat",
                    ))
                else:
                    # Placeholder for video/tileset/spritesheet
                    placeholder_content = (
                        f"# Asset: {spec.key}\n"
                        f"# Type: {spec.type}\n"
                        f"# Description: {spec.description}\n"
                        f"# Placeholder — asset generation not available\n"
                    )
                    output_path.write_text(placeholder_content, encoding="utf-8")
                    generated.append(GeneratedAsset(
                        spec=spec,
                        output_path=output_path,
                        generation_time_ms=0,
                        provider="placeholder",
                    ))
            except Exception as e:
                # Individual asset failure shouldn't block the pipeline
                placeholder_content = (
                    f"# Asset: {spec.key}\n"
                    f"# Error: {e}\n"
                    f"# This is a fallback placeholder.\n"
                )
                output_path.write_text(placeholder_content, encoding="utf-8")
                generated.append(GeneratedAsset(
                    spec=spec,
                    output_path=output_path,
                    generation_time_ms=0,
                    provider="error",
                ))

        # Build asset pack
        self._build_asset_pack(generated, assets_dir)

        return generated

    def set_asset_service(self, asset_service) -> None:
        """Inject an AssetService for asset generation.

        Args:
            asset_service: AssetService instance.
        """
        self._asset_service = asset_service

    @staticmethod
    def _parse_asset_specs(gdd: GameDesignDocument) -> list[AssetSpec]:
        """Extract asset specifications from GDD."""
        specs: list[AssetSpec] = []

        for section in gdd.sections:
            if section.section_number == 4:  # Art and Audio
                # Look for asset mentions
                image_pattern = re.compile(
                    r"(?:sprite|image|texture|icon)\s+(?:for|of)?\s*['\"]?(\w+)['\"]?",
                    re.IGNORECASE,
                )
                matches = image_pattern.findall(section.content)
                for key in matches[:10]:  # Limit
                    specs.append(AssetSpec(
                        key=key,
                        type="image",
                        description=f"Sprite for {key}",
                    ))

        return specs

    @staticmethod
    def _build_asset_pack(assets: list[GeneratedAsset], assets_dir: Path) -> None:
        """Write asset-pack.json manifest."""
        pack = {
            "version": "1.0",
            "assets": [
                {
                    "key": a.spec.key,
                    "type": a.spec.type,
                    "path": str(a.output_path.relative_to(assets_dir)),
                }
                for a in assets
            ],
        }
        (assets_dir / "asset-pack.json").write_text(
            json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8",
        )

    # --- Phase 4: Config & Registration ---

    def _phase_4_config_and_registration(
        self, gdd: GameDesignDocument, archetype: str, output_dir: Path,
    ) -> None:
        """Update gameConfig.json, main.ts, LevelManager.ts."""
        # Update gameConfig.json
        self._update_game_config(gdd, archetype, output_dir)

        # Update main.ts
        self._update_main_ts(gdd, output_dir)

        # Update TitleScreen.ts
        self._update_title_screen(gdd, output_dir)

    @staticmethod
    def _update_game_config(gdd: GameDesignDocument, archetype: str, output_dir: Path) -> None:
        """Merge GDD config into gameConfig.json."""
        config_path = output_dir / "gameConfig.json"
        if not config_path.exists():
            return

        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["gameTitle"] = gdd.title

            # Add archetype-specific physics
            physics = {}
            if archetype == "platformer":
                physics = {"gravity": {"y": 800}}
            elif archetype in ("top_down", "grid_logic"):
                physics = {"gravity": {"y": 0}}

            if physics:
                config.setdefault("physics", {}).update(physics)

            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        except (json.JSONDecodeError, OSError):
            pass

    @staticmethod
    def _update_main_ts(gdd: GameDesignDocument, output_dir: Path) -> None:
        """Update main.ts with scene registrations based on GDD."""
        main_path = output_dir / "src" / "main.ts"
        if not main_path.exists():
            main_path = output_dir / "main.ts"

        if not main_path.exists():
            return

        content = main_path.read_text(encoding="utf-8")

        # Replace TODO comments with scene keys from GDD
        scene_keys = []
        scene_section = next((s for s in gdd.sections if s.section_number == 2), None)
        if scene_section:
            scene_pattern = re.compile(r"(?:scene|level|screen)\s+['\"]?(\w+)['\"]?", re.IGNORECASE)
            scene_keys = list(set(scene_pattern.findall(scene_section.content)))

        if scene_keys:
            for key in scene_keys[:5]:
                content = content.replace(
                    f"// TODO: Register {key} scene",
                    f"this.scene.add('{key}', {key}Scene);",
                )

        main_path.write_text(content, encoding="utf-8")

    @staticmethod
    def _update_title_screen(gdd: GameDesignDocument, output_dir: Path) -> None:
        """Update TitleScreen.ts with the actual game title."""
        title_paths = [
            output_dir / "src" / "scenes" / "TitleScreen.ts",
            output_dir / "src" / "TitleScreen.ts",
        ]

        for title_path in title_paths:
            if title_path.exists():
                content = title_path.read_text(encoding="utf-8")
                content = content.replace("GAME_TITLE", gdd.title)
                content = content.replace("TODO-TITLE", gdd.title)
                title_path.write_text(content, encoding="utf-8")
                break

    # --- Phase 5: Code Implementation (delegate to TurnLoop) ---

    async def _phase_5_implement_code(
        self,
        prompt: str,
        gdd: GameDesignDocument,
        archetype: str,
        output_dir: Path,
    ) -> None:
        """Delegate code implementation to the TurnLoop agent."""
        system_prompt = f"""You are an expert Phaser 3 game developer. Build the game based on the GDD.

## Project Info
- Archetype: {archetype}
- Output Directory: {output_dir}
- Framework: Phaser 3 + TypeScript + Vite
- Resolution: 800x600

## GDD Summary
{gdd.title}

Use the available tools to read existing files, write code, and build the game.
Follow the 3-layer reading strategy: API summary → targeted source → module manual."""

        user_message = f"""Build the game based on these requirements:

{prompt}

The GDD has been saved to {output_dir}/GAME_DESIGN.md. Read it for full specifications.
Start by reading the existing template files, then implement game-specific scenes and logic."""

        loop = TurnLoop(
            llm_client=self.llm_client,
            tool_registry=self.tool_registry,
        )

        result = await loop.run(
            system_prompt=system_prompt,
            user_message=user_message,
        )

        if not result.finished:
            # Max turns reached — game may not be complete
            pass

    # --- Phase 6: Debug & Verification ---

    async def _phase_6_debug(self, output_dir: Path) -> DebugLoopResult:
        """Run the debug loop on the generated game."""
        return await self.debug_skill.debug(
            project_dir=output_dir,
            run_dev=False,
            evolve_after=self.config.game_skill.evolve_after_debug,
        )
