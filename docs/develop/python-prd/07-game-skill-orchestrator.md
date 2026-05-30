# 07 — Game Skill Orchestrator

The Game Skill Orchestrator combines Template Skill, Debug Skill, Asset Pipeline, and Agent Runtime into the complete 6-phase game generation workflow.

## 7.1 Orchestrator Interface

```python
# skills/game_skill.py
from pathlib import Path
from typing import Literal


class GameSkill:
    """
    Main orchestrator for end-to-end game generation from a prompt.

    Combines:
    - Template Skill (scaffolding from templates)
    - Debug Skill (build → diagnose → repair loop)
    - Asset Pipeline (image/audio/video generation)
    - Agent Runtime (LLM-driven code implementation)

    Pipeline:
    Phase 1: Classification and Scaffolding
    Phase 2: Game Design (GDD generation)
    Phase 3: Asset Generation
    Phase 4: Config and Registration
    Phase 5: Code Implementation (agent loop)
    Phase 6: Debug and Verification
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        template_skill: TemplateSkill,
        debug_skill: DebugSkill,
        asset_service: AssetService,
        tool_registry: ToolRegistry,
        config: OpenGameConfig,
    ):
        self.llm_client = llm_client
        self.template_skill = template_skill
        self.debug_skill = debug_skill
        self.asset_service = asset_service
        self.tool_registry = tool_registry
        self.config = config
        self.turn_loop = TurnLoop(llm_client, tool_registry)

    async def generate_game(
        self,
        prompt: str,
        output_dir: Path,
    ) -> GameResult:
        """
        Generate a complete game from a natural language prompt.

        Args:
            prompt: User's game description
            output_dir: Directory where the game project will be created

        Returns:
            GameResult with success flag, project path, GDD, assets, and debug trace
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # Phase 1: Classification and Scaffolding
            archetype = await self._phase_1_classify_and_scaffold(prompt, output_dir)

            # Phase 2: Game Design Document
            gdd = await self._phase_2_generate_gdd(prompt, archetype, output_dir)

            # Phase 3: Asset Generation
            assets = await self._phase_3_generate_assets(gdd, output_dir)

            # Phase 4: Config and Registration
            await self._phase_4_config_and_registration(gdd, output_dir)

            # Phase 5: Code Implementation (agent loop)
            await self._phase_5_implement_code(gdd, archetype, output_dir)

            # Phase 6: Debug and Verification
            debug_result = await self._phase_6_debug(output_dir)

            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

            return GameResult(
                success=debug_result.success,
                project_dir=output_dir,
                gdd=gdd,
                assets=assets,
                debug_trace=debug_result.trace,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            return GameResult(
                success=False,
                project_dir=output_dir,
                gdd=GameDesignDocument(title="", archetype="", sections=[]),
                assets=[],
                debug_trace=None,
                duration_ms=duration_ms,
                error=str(e),
            )
```

## 7.2 Phase 1: Classification and Scaffolding

```python
    async def _phase_1_classify_and_scaffold(
        self,
        prompt: str,
        output_dir: Path,
    ) -> str:
        """
        Phase 1: Determine game archetype and scaffold project.

        Steps:
        1. Use LLM to classify the game type from the prompt
        2. Copy core template (M0) to output directory
        3. Copy archetype-specific module templates into src/
        4. Copy documentation (GDD templates, protocols)
        """
        print("\n=== Phase 1: Classification and Scaffolding ===")

        # Step 1: Classify using prompt (not code, since no code exists yet)
        archetype = await self._classify_from_prompt(prompt)
        print(f"  Archetype: {archetype}")

        # Step 2: Scaffold project
        output_dir.mkdir(parents=True, exist_ok=True)

        templates_dir = self.config.game_skill.templates_dir
        docs_dir = self.config.game_skill.docs_dir
        archetypes_dir = self.config.game_skill.archetypes_dir

        # Copy core template (M0)
        core_dir = templates_dir / "core"
        if core_dir.exists():
            await self._copy_tree(core_dir, output_dir)
            print(f"  Copied core template: {core_dir} -> {output_dir}")

        # Copy archetype module
        module_dir = archetypes_dir / archetype
        if module_dir.exists():
            module_src = module_dir / "src"
            if module_src.exists():
                await self._copy_tree(module_src, output_dir / "src")
                print(f"  Copied module source: {module_src} -> {output_dir / 'src'}")

        # Copy documentation
        docs_output = output_dir / "docs"
        docs_output.mkdir(exist_ok=True)

        # Core docs
        gdd_dir = docs_dir / "gdd"
        if gdd_dir.exists():
            await self._copy_tree(gdd_dir, docs_output / "gdd")

        for doc_file in ["asset_protocol.md", "debug_protocol.md"]:
            src = docs_dir / doc_file
            if src.exists():
                await self._copy_file(src, docs_output / doc_file)

        # Module docs
        module_docs = docs_dir / "modules" / archetype
        if module_docs.exists():
            await self._copy_tree(module_docs, docs_output / "modules" / archetype)

        print(f"  Documentation copied to: {docs_output}")

        return archetype

    async def _classify_from_prompt(self, prompt: str) -> str:
        """
        Classify game archetype from the user's prompt (before code exists).

        Uses a simplified heuristic based on keywords in the prompt.
        Falls back to LLM if ambiguous.
        """
        prompt_lower = prompt.lower()

        # Keyword-based classification (fast, no API call)
        keywords = {
            "platformer": ["platform", "jump", "gravity", "side-scrolling", "mario"],
            "top_down": ["top-down", "overhead", "zelda", "shooter", "dungeon"],
            "grid_logic": ["grid", "puzzle", "match", "sokoban", "chess", "board"],
            "tower_defense": ["tower defense", "td", "wave", "enemy path", "turret"],
            "ui_heavy": ["card game", "visual novel", "dialogue", "quiz", "menu"],
        }

        scores = {arch: sum(1 for kw in kws if kw in prompt_lower) for arch, kws in keywords.items()}
        best = max(scores, key=scores.get)

        if scores[best] > 0:
            return best

        # Fallback: ask LLM
        classify_prompt = f"""Classify this game description into one of: platformer, top_down, grid_logic, tower_defense, ui_heavy.

Description: {prompt}

Respond with ONLY the archetype name."""

        response = await self.llm_client.generate(
            messages=[{"role": "user", "content": classify_prompt}],
            tools=None,
            stream=False,
            temperature=0.1,
            max_tokens=50,
        )

        if response.content:
            result = response.content.strip().lower()
            for arch in keywords:
                if arch in result:
                    return arch

        return "grid_logic"  # Default fallback

    async def _copy_tree(self, src: Path, dst: Path) -> None:
        """Recursively copy a directory tree."""
        import shutil
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    async def _copy_file(self, src: Path, dst: Path) -> None:
        """Copy a single file."""
        import shutil
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
```

## 7.3 Phase 2: Game Design Document

```python
    async def _phase_2_generate_gdd(
        self,
        prompt: str,
        archetype: str,
        output_dir: Path,
    ) -> GameDesignDocument:
        """
        Phase 2: Generate Game Design Document.

        The GDD has 6 sections that feed downstream phases:
        - Section 0: Architecture → Phase 4 (scene registration)
        - Section 1: Assets → Phase 3 (asset generation)
        - Section 2: Config → Phase 4 (gameConfig.json)
        - Section 3: Entities/Scenes → Phase 5 (code implementation)
        - Section 4: Levels/Content → Phase 3 (tilemap) + Phase 5 (content)
        - Section 5: Roadmap → Phase 5 (todo list)
        """
        print("\n=== Phase 2: Game Design Document ===")

        # Load template documentation
        docs_dir = output_dir / "docs"
        gdd_core = ""
        design_rules = ""
        template_api = ""

        core_md = docs_dir / "gdd" / "core.md"
        if core_md.exists():
            async with aiofiles.open(core_md, "r") as f:
                gdd_core = await f.read()

        rules_md = docs_dir / "modules" / archetype / "design_rules.md"
        if rules_md.exists():
            async with aiofiles.open(rules_md, "r") as f:
                design_rules = await f.read()

        api_md = docs_dir / "modules" / archetype / "template_api.md"
        if api_md.exists():
            async with aiofiles.open(api_md, "r") as f:
                template_api = await f.read()

        # Generate GDD via LLM
        gdd_prompt = f"""You are a game designer. Create a comprehensive Game Design Document based on the user's request.

## User Request
{prompt}

## Game Archetype
{archetype}

## GDD Format Reference
{gdd_core[:5000]}

## Design Rules for This Archetype
{design_rules[:5000]}

## Available Template APIs
{template_api[:5000]}

## Your Task
Generate a complete GDD with these 6 sections:

### Section 0: Architecture
- Scene hierarchy and flow
- Scene keys and transitions
- Which base classes are used

### Section 1: Asset Registry
Complete table of ALL assets needed:
| Key | Type | Description | Size |
Include every texture, sprite, audio, and animation.

### Section 2: Game Configuration
All config fields in gameConfig.json format with {{ "value": X, "type": "...", "description": "..." }} wrapper.

### Section 3: Entities and Scenes
- List all game entities (player, enemies, items, etc.)
- For each: base class, custom hooks, properties
- List all custom scenes extending base classes

### Section 4: Levels and Content
- Level progression
- ASCII tilemaps (if applicable)
- Wave configurations (if applicable)
- Dialogue trees (if applicable)

### Section 5: Implementation Roadmap
Ordered list of file operations:
- COPY _TemplateX.ts → CustomX.ts (which hooks to override)
- EXTEND BaseX.ts → CustomX.ts (which methods to implement)
- CREATE new files
- UPDATE existing files (main.ts, LevelManager.ts, gameConfig.json)

Output as a structured markdown document."""

        response = await self.llm_client.generate(
            messages=[{"role": "user", "content": gdd_prompt}],
            tools=None,
            stream=False,
            temperature=0.7,
            max_tokens=8000,
        )

        gdd_content = response.content or ""

        # Parse into structured GDD
        gdd = self._parse_gdd(gdd_content, archetype)

        # Save GDD to disk
        gdd_path = output_dir / "GAME_DESIGN.md"
        async with aiofiles.open(gdd_path, "w") as f:
            await f.write(gdd_content)
        print(f"  GDD saved to: {gdd_path}")

        return gdd

    def _parse_gdd(self, content: str, archetype: str) -> GameDesignDocument:
        """Parse markdown GDD into structured model."""
        import re

        # Extract title (first heading)
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else "Untitled Game"

        # Split into sections
        sections = []
        section_pattern = re.compile(r"^#{2,3}\s+Section\s*(\d+):?\s*(.+)$", re.MULTILINE)
        for match in section_pattern.finditer(content):
            num = int(match.group(1))
            sec_title = match.group(2).strip()
            start = match.end()
            end_match = section_pattern.search(content, start)
            end = end_match.start() if end_match else len(content)
            sec_content = content[start:end].strip()
            sections.append(GddSection(
                section_number=num,
                title=sec_title,
                content=sec_content,
            ))

        # Extract asset registry
        assets = []
        asset_table = re.search(r"\|[^\n]*Key[^\n]*\|[^\n]*Type[^\n]*\|([^\n]*\n)*", content)
        if asset_table:
            # Parse markdown table
            pass

        return GameDesignDocument(
            title=title,
            archetype=archetype,
            sections=sections,
        )
```

## 7.4 Phase 3: Asset Generation

```python
    async def _phase_3_generate_assets(
        self,
        gdd: GameDesignDocument,
        output_dir: Path,
    ) -> list[GeneratedAsset]:
        """
        Phase 3: Generate game assets.

        Steps:
        1. Parse asset registry from GDD Section 1
        2. Generate images (backgrounds, sprites, tilesets)
        3. Generate audio (BGM, SFX)
        4. Generate animations/video (if needed)
        5. Build asset-pack.json
        """
        print("\n=== Phase 3: Asset Generation ===")

        assets: list[GeneratedAsset] = []
        assets_dir = output_dir / "public" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Parse asset specs from GDD
        specs = self._parse_asset_specs(gdd)
        print(f"  {len(specs)} assets to generate")

        # Generate in parallel (with batching for rate limits)
        batch_size = 4
        for i in range(0, len(specs), batch_size):
            batch = specs[i:i + batch_size]
            tasks = [self._generate_single_asset(spec, assets_dir) for spec in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for spec, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    print(f"  ! Failed to generate {spec.key}: {result}")
                elif result:
                    assets.append(result)
                    print(f"  Generated: {spec.key} ({spec.type})")

        # Build asset-pack.json
        await self._build_asset_pack(assets, assets_dir)

        return assets

    def _parse_asset_specs(self, gdd: GameDesignDocument) -> list[AssetSpec]:
        """Parse asset specifications from GDD Section 1."""
        specs = []

        # Find Section 1 (Assets)
        asset_section = next(
            (s for s in gdd.sections if "asset" in s.title.lower()),
            None,
        )
        if not asset_section:
            return specs

        # Parse markdown table
        import re
        table_pattern = re.compile(
            r"\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|"
        )

        for match in table_pattern.finditer(asset_section.content):
            key = match.group(1).strip()
            type_str = match.group(2).strip().lower()
            description = match.group(3).strip()
            size = match.group(4).strip() if len(match.groups()) > 3 else None

            if key in ("Key", "---", "--"):
                continue

            # Map type string to enum
            type_map = {
                "image": "image", "img": "image", "sprite": "image",
                "texture": "image", "background": "image", "bg": "image",
                "audio": "audio", "sound": "audio", "sfx": "audio",
                "bgm": "audio", "music": "audio",
                "video": "video", "animation": "video",
                "tileset": "tileset", "tile": "tileset",
                "spritesheet": "spritesheet", "sheet": "spritesheet",
            }
            asset_type = type_map.get(type_str, "image")

            specs.append(AssetSpec(
                key=key,
                type=asset_type,  # type: ignore[arg-type]
                description=description,
                size=size,
                output_path=f"assets/{key}.png" if asset_type == "image" else f"assets/{key}.wav",
            ))

        return specs

    async def _generate_single_asset(
        self,
        spec: AssetSpec,
        output_dir: Path,
    ) -> GeneratedAsset | None:
        """Generate a single asset."""
        output_path = output_dir / spec.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        start = asyncio.get_event_loop().time()

        try:
            if spec.type == "image":
                result_path = await self.asset_service.generate_image(
                    prompt=spec.description,
                    output_path=output_path,
                    size=spec.size or "1024x1024",
                )
            elif spec.type == "audio":
                result_path = await self.asset_service.generate_audio(
                    prompt=spec.description,
                    output_path=output_path,
                )
            elif spec.type == "video":
                result_path = await self.asset_service.generate_video(
                    prompt=spec.description,
                    output_path=output_path,
                )
            else:
                return None

            duration_ms = int((asyncio.get_event_loop().time() - start) * 1000)

            return GeneratedAsset(
                spec=spec,
                output_path=result_path,
                generation_time_ms=duration_ms,
                provider=self.config.image.provider if self.config.image else "unknown",
            )

        except Exception as e:
            print(f"  Asset generation failed for {spec.key}: {e}")
            return None

    async def _build_asset_pack(self, assets: list[GeneratedAsset], assets_dir: Path) -> None:
        """Build asset-pack.json from generated assets."""
        asset_pack = {
            "assets": []
        }

        for asset in assets:
            rel_path = str(asset.output_path.relative_to(assets_dir.parent))
            entry = {
                "key": asset.spec.key,
                "type": asset.spec.type,
                "url": rel_path,
            }
            if asset.spec.type == "spritesheet":
                entry["frameWidth"] = 32
                entry["frameHeight"] = 32
            asset_pack["assets"].append(entry)

        pack_path = assets_dir / "asset-pack.json"
        async with aiofiles.open(pack_path, "w") as f:
            await f.write(json.dumps(asset_pack, indent=2))
        print(f"  Asset pack saved: {pack_path}")
```

## 7.5 Phase 4: Config and Registration

```python
    async def _phase_4_config_and_registration(
        self,
        gdd: GameDesignDocument,
        output_dir: Path,
    ) -> None:
        """
        Phase 4: Update config files and register scenes.

        Files updated:
        - src/gameConfig.json (merge game-specific config with M0 baseline)
        - src/LevelManager.ts (set LEVEL_ORDER)
        - src/main.ts (import and register scenes)
        - src/scenes/TitleScreen.ts (update game title)
        """
        print("\n=== Phase 4: Config and Registration ===")

        # Update gameConfig.json
        config_path = output_dir / "src" / "gameConfig.json"
        if config_path.exists():
            async with aiofiles.open(config_path, "r") as f:
                existing = json.loads(await f.read())

            # Merge game-specific config from GDD Section 2
            game_config = self._extract_config_from_gdd(gdd)
            merged = {**existing, **game_config}

            async with aiofiles.open(config_path, "w") as f:
                await f.write(json.dumps(merged, indent=2))
            print(f"  Updated: {config_path}")

        # Update LevelManager.ts
        level_manager = output_dir / "src" / "LevelManager.ts"
        if level_manager.exists():
            scene_keys = self._extract_scene_keys(gdd)
            content = await self._read_file(level_manager)
            # Replace LEVEL_ORDER
            content = re.sub(
                r"LEVEL_ORDER\s*=\s*\[[^\]]*\]",
                f'LEVEL_ORDER = {json.dumps(scene_keys)}',
                content,
            )
            await self._write_file(level_manager, content)
            print(f"  Updated: {level_manager}")

        # Update main.ts
        main_file = output_dir / "src" / "main.ts"
        if main_file.exists():
            content = await self._read_file(main_file)
            # Add scene imports and registrations
            content = self._update_main_ts(content, gdd)
            await self._write_file(main_file, content)
            print(f"  Updated: {main_file}")

        # Update TitleScreen.ts
        title_screen = output_dir / "src" / "scenes" / "TitleScreen.ts"
        if title_screen.exists():
            content = await self._read_file(title_screen)
            content = content.replace("GAME TITLE", gdd.title)
            content = content.replace("TODO-TITLE", gdd.title)
            await self._write_file(title_screen, content)
            print(f"  Updated: {title_screen}")

    def _extract_config_from_gdd(self, gdd: GameDesignDocument) -> dict:
        """Extract game-specific config from GDD Section 2."""
        config = {}
        config_section = next(
            (s for s in gdd.sections if "config" in s.title.lower()),
            None,
        )
        if config_section:
            # Parse config fields from markdown
            import re
            for match in re.finditer(
                r'"([^"]+)"\s*:\s*\{\s*"value"\s*:\s*([^,\}]+)',
                config_section.content,
            ):
                key = match.group(1)
                value = match.group(2).strip()
                # Try to parse as JSON
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
                config[key] = {"value": value}
        return config

    def _extract_scene_keys(self, gdd: GameDesignDocument) -> list[str]:
        """Extract scene keys from GDD Section 0."""
        keys = []
        arch_section = next(
            (s for s in gdd.sections if s.section_number == 0),
            None,
        )
        if arch_section:
            import re
            for match in re.finditer(r"`([^`]+Scene)`", arch_section.content):
                keys.append(match.group(1))
        return keys or ["TitleScreen", "Level1"]

    def _update_main_ts(self, content: str, gdd: GameDesignDocument) -> str:
        """Update main.ts with scene imports and registrations."""
        # This is simplified — actual implementation would parse AST
        scene_keys = self._extract_scene_keys(gdd)

        # Add imports
        imports = "\n".join(
            f'import {{ {key} }} from "./scenes/{key}";'
            for key in scene_keys
        )

        # Add scene registrations
        registrations = "\n".join(
            f'game.scene.add("{key}", {key});'
            for key in scene_keys
        )

        # Replace TODO comments
        content = content.replace(
            "// TODO: Import game scenes",
            imports,
        )
        content = content.replace(
            "// TODO: Register game scenes",
            registrations,
        )

        return content

    async def _read_file(self, path: Path) -> str:
        async with aiofiles.open(path, "r") as f:
            return await f.read()

    async def _write_file(self, path: Path, content: str) -> None:
        async with aiofiles.open(path, "w") as f:
            await f.write(content)
```

## 7.6 Phase 5: Code Implementation

```python
    async def _phase_5_implement_code(
        self,
        gdd: GameDesignDocument,
        archetype: str,
        output_dir: Path,
    ) -> None:
        """
        Phase 5: Implement game code using the agent loop.

        The agent reads template source files, then implements custom game files
        by copying _Template*.ts files and overriding hooks.

        Strategy:
        1. Read template API summary (low context cost)
        2. Read targeted source files (files to copy/extend)
        3. Read module manual (implementation guide)
        4. Implement file by file following GDD Section 5 roadmap
        """
        print("\n=== Phase 5: Code Implementation ===")

        # Build system prompt for code implementation
        system_prompt = await self._build_implementation_prompt(gdd, archetype, output_dir)

        # Build user message with implementation instructions
        user_message = f"""Implement the game "{gdd.title}" according to the GAME_DESIGN.md.

Follow the 6-phase workflow in your instructions:
1. Read template API summary
2. Read targeted source files
3. Read module manual
4. Implement files one by one
5. Verify consistency

Key constraints:
- NEVER modify KEEP files (Base*.ts, behaviors/*, systems/*, ui/*, utils.ts)
- ALWAYS base code on _Template*.ts (COPY) or Base*.ts (EXTEND)
- Call super.create() / super.update() when overriding lifecycle methods
- Use asset keys exactly as defined in asset-pack.json
- Use scene keys consistently across main.ts, LevelManager.ts, and scene.start() calls

The gameConfig.json, LevelManager.ts, and main.ts have already been configured in Phase 4.
Focus on implementing the game-specific scenes, entities, and content."""

        # Run agent loop for implementation
        result = await self.turn_loop.run(
            system_prompt=system_prompt,
            user_message=user_message,
        )

        print(f"  Implementation complete. Turns: {result.token_usage}")

    async def _build_implementation_prompt(
        self,
        gdd: GameDesignDocument,
        archetype: str,
        output_dir: Path,
    ) -> str:
        """Build the system prompt for code implementation phase."""
        # Load custom game prompt
        custom_prompt_path = Path("opengame/prompts/custom.md")
        if custom_prompt_path.exists():
            async with aiofiles.open(custom_prompt_path, "r") as f:
                base = await f.read()
        else:
            base = self._default_game_prompt()

        # Inject project context
        file_tree = []
        for path in sorted(output_dir.rglob("*")):
            rel = str(path.relative_to(output_dir))
            if "node_modules" not in rel and ".git" not in rel:
                file_tree.append(rel)

        context = f"""
# Current Project Context

## File Tree
```
{"\n".join(file_tree[:100])}
```

## Game Archetype: {archetype}
## Game Title: {gdd.title}

## Asset Keys Available
{self._list_asset_keys(output_dir)}
"""

        return base + context

    def _default_game_prompt(self) -> str:
        return """You are a game coding agent specializing in 2D game development."""

    def _list_asset_keys(self, output_dir: Path) -> str:
        """List all asset keys from asset-pack.json."""
        pack_path = output_dir / "public" / "assets" / "asset-pack.json"
        if pack_path.exists():
            try:
                with open(pack_path) as f:
                    pack = json.load(f)
                return "\n".join(
                    f"- {a['key']} ({a['type']}): {a['url']}"
                    for a in pack.get("assets", [])
                )
            except Exception:
                pass
        return "(asset pack not yet created)"
```

## 7.7 Phase 6: Debug and Verification

```python
    async def _phase_6_debug(self, output_dir: Path) -> DebugLoopResult:
        """
        Phase 6: Run the debug loop to verify and fix the game.

        Steps:
        1. Run debug loop (build → diagnose → repair)
        2. If successful, optionally run dev server probe
        3. Return result
        """
        print("\n=== Phase 6: Debug and Verification ===")

        result = await self.debug_skill.debug(
            project_dir=output_dir,
            run_dev=False,  # Dev server probe can hang
            evolve_after=True,
        )

        if result.success:
            print(f"  Debug loop succeeded in {result.trace.total_iterations} iterations")
        else:
            print(f"  Debug loop failed after {result.trace.total_iterations} iterations")
            print(f"  Errors remain — game may not be playable")

        return result
```

## 7.8 Complete Pipeline Flow

```
User Prompt
    │
    ▼
┌─────────────────┐
│  Phase 1        │ ──► Classify archetype from prompt
│  Scaffold       │ ──► Copy core template + module template + docs
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Phase 2        │ ──► Generate GDD (6 sections) via LLM
│  Game Design    │ ──► Save GAME_DESIGN.md
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Phase 3        │ ──► Parse asset registry from GDD Section 1
│  Assets         │ ──► Generate images/audio/video in parallel
│                 │ ──► Build asset-pack.json
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Phase 4        │ ──► Merge game-specific config into gameConfig.json
│  Config + Reg   │ ──► Set LEVEL_ORDER in LevelManager.ts
│                 │ ──► Register scenes in main.ts
│                 │ ──► Update title in TitleScreen.ts
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Phase 5        │ ──► Agent reads template API + source files
│  Implement      │ ──► Agent implements files following GDD roadmap
│                 │ ──► COPY _Template*.ts → Custom*.ts
│                 │ ──► EXTEND Base*.ts → Custom*.ts
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Phase 6        │ ──► Run build → diagnose → repair loop
│  Debug          │ ──► Repeat until build + test pass
│                 │ ──► Evolve protocol with new learnings
└────────┬────────┘
         │
         ▼
    Playable Game
```
