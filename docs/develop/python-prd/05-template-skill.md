# 05 — Template Skill

The Template Skill learns and maintains a library of reusable project skeletons. It observes completed projects, extracts their patterns, generalizes them into templates, and accumulates them into families.

## 5.1 Core Principle

**No predefined archetypes.** The library starts empty. Archetypes emerge dynamically as the agent accumulates experience. A label like "platformer" is discovered from code, not assumed.

## 5.2 Pipeline Overview

```
Completed Project ──► Collector ──► Snapshot
                                    │
                                    ▼
                              Classifier ──► Archetype + PhysicsProfile
                                    │
                                    ▼
                              Extractor ──► Patterns (classes, hooks, config)
                                    │
                                    ▼
                              Abstractor ──► Generalized Templates
                                    │
                                    ▼
                              Merger ──► TemplateFamily
                                    │
                                    ▼
                         Library Manager ──► TemplateLibrary (persisted)
                                    │
                                    ▼
                              Evolve ──► Library growth over time
```

## 5.3 Collector

```python
# skills/template_skill/collector.py
from pathlib import Path
import aiofiles


class ProjectCollector:
    """Collect a complete snapshot of a project for analysis."""

    # Files to exclude from snapshots
    IGNORE_PATTERNS = [
        "node_modules",
        ".git",
        "dist",
        "build",
        ".DS_Store",
        "*.log",
    ]

    async def collect(self, project_dir: Path) -> ProjectSnapshot:
        """
        Walk the project directory and create a complete snapshot.

        Returns:
            ProjectSnapshot with all source files, file tree, and a code summary.
        """
        files = []
        file_tree = []
        game_config = None

        for path in self._walk_project(project_dir):
            rel = str(path.relative_to(project_dir))
            file_tree.append(rel)

            if path.is_file() and self._should_include(rel):
                async with aiofiles.open(path, "r", encoding="utf-8") as f:
                    content = await f.read()
                files.append(FileEntry(
                    relative_path=rel,
                    content=content,
                    extension=path.suffix,
                ))

                # Extract gameConfig.json if present
                if rel.endswith("gameConfig.json"):
                    import json
                    try:
                        game_config = json.loads(content)
                    except json.JSONDecodeError:
                        pass

        # Generate code summary for LLM context
        code_summary = self._generate_code_summary(files)

        return ProjectSnapshot(
            project_path=str(project_dir),
            files=files,
            file_tree=file_tree,
            game_config=game_config,
            code_summary=code_summary,
        )

    def _walk_project(self, project_dir: Path):
        """Walk project directory, respecting ignore patterns."""
        for path in project_dir.rglob("*"):
            rel = str(path.relative_to(project_dir))
            if any(pat in rel for pat in self.IGNORE_PATTERNS):
                continue
            yield path

    def _should_include(self, rel_path: str) -> bool:
        """Determine if a file should be included in the snapshot."""
        if any(pat in rel_path for pat in self.IGNORE_PATTERNS):
            return False
        # Include source code and config files
        return rel_path.endswith((".ts", ".js", ".json", ".html", ".css", ".md"))

    def _generate_code_summary(self, files: list[FileEntry]) -> str:
        """Generate a human-readable summary of code structure."""
        lines = []

        # Summarize class hierarchy
        classes = []
        for f in files:
            if not f.relative_path.endswith(".ts"):
                continue
            for match in re.finditer(r"(export\s+)?(abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?", f.content):
                name = match.group(3)
                parent = match.group(4)
                classes.append(f"  - {name}" + (f" extends {parent}" if parent else ""))

        if classes:
            lines.append("Classes:")
            lines.extend(classes[:30])  # Limit to 30 classes

        # Summarize file structure
        dirs = set()
        for f in files:
            parts = f.relative_path.split("/")
            if len(parts) > 1:
                dirs.add(parts[0])
        lines.append(f"\nTop-level directories: {', '.join(sorted(dirs))}")

        # Count files by type
        type_counts = {}
        for f in files:
            ext = f.extension or "no_ext"
            type_counts[ext] = type_counts.get(ext, 0) + 1
        lines.append(f"\nFile counts:")
        for ext, count in sorted(type_counts.items()):
            lines.append(f"  {ext}: {count}")

        return "\n".join(lines)
```

## 5.4 Classifier

The classifier determines a project's archetype based on its physics regime, not genre names.

### Algorithm

```python
# skills/template_skill/classifier.py
import re
from typing import Final


# Physics signals detected in source code.
# These are NOT archetype definitions — they are heuristics that suggest
# a physics regime. The actual archetype label is either matched against
# existing families or invented by the LLM.
PHYSICS_SIGNALS: Final[list[dict]] = [
    {
        "name": "gravity",
        "patterns": [
            re.compile(r"setGravityY", re.I),
            re.compile(r"jumpPower", re.I),
            re.compile(r"PlatformerMovement", re.I),
            re.compile(r"coyoteTime", re.I),
            re.compile(r"gravity\s*[:=]\s*\{?\s*y\s*:", re.I),
        ],
        "profile": {"has_gravity": True, "perspective": "side", "movement_type": "continuous"},
    },
    {
        "name": "free_movement",
        "patterns": [
            re.compile(r"EightWayMovement", re.I),
            re.compile(r"DashAbility", re.I),
            re.compile(r"ySortGroup", re.I),
            re.compile(r"FaceTarget", re.I),
        ],
        "profile": {"has_gravity": False, "perspective": "top_down", "movement_type": "continuous"},
    },
    {
        "name": "grid_discrete",
        "patterns": [
            re.compile(r"BoardManager", re.I),
            re.compile(r"cellSize", re.I),
            re.compile(r"gridCols", re.I),
            re.compile(r"BaseGridScene", re.I),
            re.compile(r"worldToGrid", re.I),
        ],
        "profile": {"has_gravity": False, "perspective": "top_down", "movement_type": "grid"},
    },
    {
        "name": "path_wave",
        "patterns": [
            re.compile(r"WaveManager", re.I),
            re.compile(r"EconomyManager", re.I),
            re.compile(r"BaseTDScene", re.I),
            re.compile(r"BaseTower", re.I),
            re.compile(r"waypoints", re.I),
        ],
        "profile": {"has_gravity": False, "perspective": "top_down", "movement_type": "path"},
    },
    {
        "name": "ui_state",
        "patterns": [
            re.compile(r"DialogueManager", re.I),
            re.compile(r"CardManager", re.I),
            re.compile(r"QuizManager", re.I),
            re.compile(r"BaseBattleScene", re.I),
            re.compile(r"ComboManager", re.I),
        ],
        "profile": {"has_gravity": False, "perspective": "none", "movement_type": "ui_only"},
    },
]


class Classifier:
    """
    Library-aware, emergent archetype classification.

    Key design principle: NO predefined archetype categories.
    - When the library is empty, the LLM freely names the physics regime.
    - When the library has families, the LLM compares against existing profiles.
    - A rule-based fallback uses physics signals when the LLM is unavailable.
    """

    def __init__(self, llm_client: BaseLlmClient):
        self.llm_client = llm_client

    async def classify(
        self,
        snapshot: ProjectSnapshot,
        library: TemplateLibrary,
    ) -> ClassificationResult:
        """
        Classify a project into an archetype.

        Strategy:
        1. Try LLM classification (library-aware prompt)
        2. Fallback to physics heuristic rules (also library-aware)
        """
        # Try LLM first
        llm_result = await self._try_llm_classify(snapshot, library)
        if llm_result:
            return llm_result

        # Fallback to heuristic classification
        return self._heuristic_classify(snapshot, library)

    async def _try_llm_classify(
        self,
        snapshot: ProjectSnapshot,
        library: TemplateLibrary,
    ) -> ClassificationResult | None:
        """Attempt LLM-based classification."""
        system_prompt = self._build_system_prompt(library)
        user_prompt = self._build_user_prompt(snapshot)

        try:
            response = await self.llm_client.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=None,
                stream=False,
                temperature=0.3,
                max_tokens=500,
            )

            if response.content:
                return self._parse_llm_response(response.content, library)
        except Exception as e:
            # LLM failed — will fall back to heuristics
            pass

        return None

    def _build_system_prompt(self, library: TemplateLibrary) -> str:
        """Build a library-aware system prompt for the LLM classifier."""
        family_section = self._build_families_section(library.families)

        return f"""# Game Project Physics Classifier

You analyze COMPLETED game project source code to determine its physics and interaction regime.
You do NOT rely on genre names — you observe the actual physics, perspective, and movement system in the code.

{family_section}
## Your Task

1. Analyze the source code for three physical properties:
   - **hasGravity**: Does the code apply Y-axis gravity? (setGravityY, jumpPower, fall logic)
   - **perspective**: Is the camera side-view, top-down, or not applicable?
   - **movementType**: Is movement continuous, grid-discrete, path-following, or UI-only?

2. Decide classification:
   - If the physics profile MATCHES an existing family, use that family's archetype name.
   - If the physics profile is CLEARLY DIFFERENT from all existing families, invent a
     short, descriptive snake_case label (e.g., "side_gravity", "free_top_down",
     "discrete_grid", "path_wave", "ui_state_machine"). The label should describe the
     PHYSICS, not the genre.

## Output Format

Respond with ONLY a JSON object:
{{
  "archetype": "<snake_case label>",
  "reasoning": "Brief explanation citing specific code evidence",
  "physicsProfile": {{
    "hasGravity": true | false,
    "perspective": "side" | "top_down" | "none",
    "movementType": "continuous" | "grid" | "path" | "ui_only"
  }},
  "confidence": 0.0 to 1.0,
  "isNewFamily": true | false
}}"""

    def _build_families_section(self, families: list[TemplateFamily]) -> str:
        """Build the existing families section for the prompt."""
        if not families:
            return "## Existing Families\nNone yet. You are naming the FIRST physics regime ever observed.\n"

        lines = ["## Existing Families in the Library\n"]
        for f in families:
            pp = f.physics_profile
            lines.append(f'### "{f.archetype}" (stability: {pp.has_gravity}, projects: {len(f.contributing_projects)})')
            lines.append(f"- gravity: {pp.has_gravity}, perspective: {pp.perspective}, movement: {pp.movement_type}")
            lines.append(f"- summary: {f.summary}")
            lines.append("")
        lines.append("If the new project clearly fits one of these, reuse its archetype name.")
        lines.append("Only create a new archetype if the physics regime is fundamentally different.\n")
        return "\n".join(lines)

    def _build_user_prompt(self, snapshot: ProjectSnapshot) -> str:
        """Build the user prompt with project context."""
        truncated_summary = snapshot.code_summary[:12000]
        return f"""Classify this completed game project based on its source code.

## File Tree
{"\n".join(snapshot.file_tree)}

## Code Analysis
{truncated_summary}

Analyze the PHYSICS, PERSPECTIVE, and MOVEMENT in the actual code. Output JSON only."""

    def _parse_llm_response(self, raw: str, library: TemplateLibrary) -> ClassificationResult | None:
        """Parse LLM response into ClassificationResult."""
        import json
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"```json?\n?", "", text).replace("```", "").strip()

        try:
            parsed = json.loads(text)
            return ClassificationResult(
                archetype=parsed.get("archetype", "unknown"),
                reasoning=parsed.get("reasoning", ""),
                physics_profile=PhysicsProfile(
                    has_gravity=parsed.get("physicsProfile", {}).get("hasGravity", False),
                    perspective=parsed.get("physicsProfile", {}).get("perspective", "none"),
                    movement_type=parsed.get("physicsProfile", {}).get("movementType", "continuous"),
                ),
                confidence=parsed.get("confidence", 0.5),
                is_new_family=parsed.get("isNewFamily", False),
            )
        except (json.JSONDecodeError, KeyError):
            return None

    def _heuristic_classify(
        self,
        snapshot: ProjectSnapshot,
        library: TemplateLibrary,
    ) -> ClassificationResult:
        """
        Rule-based fallback classification using physics signals.

        Detects physics signals in code, produces a profile, then matches against
        existing families or mints a new label from the signal name.
        """
        # Concatenate all TypeScript source code
        all_code = "\n".join(
            f.content for f in snapshot.files
            if f.extension == ".ts"
        )

        # Score each signal group
        signal_scores = []
        for signal in PHYSICS_SIGNALS:
            score = sum(1 for pat in signal["patterns"] if pat.search(all_code))
            signal_scores.append({"signal": signal, "score": score})

        # Sort by score descending
        signal_scores.sort(key=lambda x: x["score"], reverse=True)
        best = signal_scores[0]
        total_matches = sum(s["score"] for s in signal_scores)

        if total_matches == 0:
            return ClassificationResult(
                archetype="unknown",
                reasoning="No recognizable physics signals found in code",
                physics_profile=PhysicsProfile(
                    has_gravity=False,
                    perspective="none",
                    movement_type="continuous",
                ),
                confidence=0.1,
            )

        detected_profile = PhysicsProfile(
            has_gravity=best["signal"]["profile"]["has_gravity"],
            perspective=best["signal"]["profile"]["perspective"],
            movement_type=best["signal"]["profile"]["movement_type"],
        )

        # Try to match against an existing family
        for family in library.families:
            fp = family.physics_profile
            if (
                fp.has_gravity == detected_profile.has_gravity
                and fp.perspective == detected_profile.perspective
                and fp.movement_type == detected_profile.movement_type
            ):
                return ClassificationResult(
                    archetype=family.archetype,
                    reasoning=f'Heuristic match to existing family "{family.archetype}" '
                              f'(signal: {best["signal"]["name"]}, score: {best["score"]}/{total_matches})',
                    physics_profile=detected_profile,
                    confidence=best["score"] / total_matches if total_matches > 0 else 0.2,
                )

        # No existing family — mint a new label from the signal name
        return ClassificationResult(
            archetype=best["signal"]["name"],
            reasoning=f'New regime detected via heuristic signal "{best["signal"]["name"]}" '
                      f'(score: {best["score"]}/{total_matches})',
            physics_profile=detected_profile,
            confidence=best["score"] / total_matches if total_matches > 0 else 0.2,
            is_new_family=True,
        )
```

## 5.5 Extractor

```python
# skills/template_skill/extractor.py
import re
from pathlib import Path


class PatternExtractor:
    """
    Extract structural patterns from a completed project's source code.

    Outputs: classes, hooks, config extensions, imports, file structure.
    """

    def extract(self, snapshot: ProjectSnapshot, classification: ClassificationResult) -> ExtractedPatterns:
        """Extract all patterns from a project snapshot."""
        return ExtractedPatterns(
            archetype=classification.archetype,
            physics_profile=classification.physics_profile,
            project_path=snapshot.project_path,
            file_structure=self._extract_file_structure(snapshot),
            classes=self._extract_classes(snapshot),
            hooks=self._extract_hooks(snapshot),
            config_extensions=self._extract_config(snapshot),
            imports=self._extract_imports(snapshot),
            code_snippets=self._extract_snippets(snapshot),
        )

    def _extract_file_structure(self, snapshot: ProjectSnapshot) -> DirectoryPattern:
        """Extract directory structure from file tree."""
        dirs = set()
        files_by_dir = {}
        for path in snapshot.file_tree:
            parts = path.split("/")
            if len(parts) > 1:
                top_dir = parts[0]
                dirs.add(top_dir)
                files_by_dir.setdefault(top_dir, []).append(parts[-1])
        return DirectoryPattern(
            directories=sorted(dirs),
            files_by_directory=files_by_dir,
        )

    def _extract_classes(self, snapshot: ProjectSnapshot) -> list[ClassDef]:
        """Extract class definitions from TypeScript files."""
        classes = []
        class_pattern = re.compile(
            r"(export\s+)?(abstract\s+)?class\s+(\w+)"
            r"(?:\s+extends\s+(\w+))?\s*\{([^}]*)\}",
            re.DOTALL,
        )
        method_pattern = re.compile(
            r"(public|protected|private)?\s*(abstract|override)?\s*"
            r"(\w+)\s*\([^)]*\)\s*:\s*(\w+)",
        )

        for f in snapshot.files:
            if f.extension != ".ts":
                continue
            for match in class_pattern.finditer(f.content):
                name = match.group(3)
                parent = match.group(4)
                body = match.group(5)
                is_abstract = match.group(2) is not None

                methods = []
                for m in method_pattern.finditer(body):
                    methods.append(MethodDef(
                        name=m.group(3),
                        visibility=m.group(1) or "public",
                        is_abstract=m.group(2) == "abstract",
                        is_override=m.group(2) == "override",
                        signature=f"{m.group(3)}(): {m.group(4)}",
                    ))

                classes.append(ClassDef(
                    name=name,
                    parent_class=parent,
                    file_path=f.relative_path,
                    is_abstract=is_abstract,
                    methods=methods,
                ))

        return classes

    def _extract_hooks(self, snapshot: ProjectSnapshot) -> list[HookDef]:
        """Extract hook methods from base classes."""
        hooks = []
        hook_pattern = re.compile(
            r"protected\s+(?:override\s+)?(\w+)\s*\([^)]*\)",
        )

        for f in snapshot.files:
            if f.extension != ".ts":
                continue
            for match in hook_pattern.finditer(f.content):
                hooks.append(HookDef(
                    name=match.group(1),
                    declaring_class="BaseClass",  # Simplified — would need AST parsing
                    signature=match.group(0),
                    is_abstract=False,
                    occurrence_count=1,
                ))

        return hooks

    def _extract_config(self, snapshot: ProjectSnapshot) -> list[ConfigField]:
        """Extract config fields beyond the M0 baseline."""
        config = []
        # Look for gameConfig.json
        for f in snapshot.files:
            if f.relative_path.endswith("gameConfig.json"):
                import json
                try:
                    data = json.loads(f.content)
                    # Extract non-baseline fields
                    self._flatten_config(data, "", config)
                except json.JSONDecodeError:
                    pass
        return config

    def _flatten_config(self, data: dict, prefix: str, out: list[ConfigField]) -> None:
        """Recursively flatten nested config into flat ConfigField list."""
        baseline = {"screenSize", "debugConfig", "renderConfig"}
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            if key in baseline:
                continue
            if isinstance(value, dict):
                self._flatten_config(value, path, out)
            else:
                out.append(ConfigField(
                    path=path,
                    value=value,
                    type=type(value).__name__,
                ))

    def _extract_imports(self, snapshot: ProjectSnapshot) -> list[ImportEdge]:
        """Extract import dependencies."""
        imports = []
        import_pattern = re.compile(
            r"import\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]"
        )
        for f in snapshot.files:
            if f.extension != ".ts":
                continue
            for match in import_pattern.finditer(f.content):
                names = [n.strip() for n in match.group(1).split(",")]
                imports.append(ImportEdge(
                    from_file=f.relative_path,
                    to_file=match.group(2),
                    imported_names=names,
                ))
        return imports

    def _extract_snippets(self, snapshot: ProjectSnapshot) -> dict[str, str]:
        """Extract key code snippets for abstraction."""
        snippets = {}
        for f in snapshot.files:
            if f.extension != ".ts":
                continue
            # Prioritize base classes and template files
            if re.search(r"Base\w+|_Template\w+|utils\.ts$", f.relative_path):
                snippets[f.relative_path] = f.content[:5000]  # Truncate large files
        return snippets
```

## 5.6 Abstractor

```python
# skills/template_skill/abstractor.py


class Abstractor:
    """
    LLM-driven template generalization.

    Takes extracted patterns from a concrete project and produces generalized,
    reusable template code where game-specific content is replaced with placeholders.
    """

    def __init__(self, llm_client: BaseLlmClient):
        self.llm_client = llm_client

    async def abstract(self, patterns: ExtractedPatterns) -> AbstractedTemplates:
        """
        Generalize extracted patterns into reusable templates.

        Strategy:
        1. Try LLM-driven abstraction
        2. Fallback to rule-based extraction
        """
        # Try LLM first
        llm_result = await self._try_llm_abstract(patterns)
        if llm_result:
            return llm_result

        # Fallback to rules
        return self._rule_based_abstract(patterns)

    async def _try_llm_abstract(self, patterns: ExtractedPatterns) -> AbstractedTemplates | None:
        """Attempt LLM-driven abstraction."""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(patterns)

        try:
            response = await self.llm_client.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=None,
                stream=False,
                temperature=0.2,
                max_tokens=8000,
            )

            if response.content:
                return self._parse_llm_response(response.content, patterns)
        except Exception:
            pass

        return None

    def _build_system_prompt(self) -> str:
        return """# Template Abstractor

You are a code analysis expert. Your task is to take CONCRETE game code extracted from a completed project and generalize it into REUSABLE template code.

## Your Goals

1. **Identify stable patterns**: Code that would appear in ANY game of this type
   (e.g., gravity setup for platformers, grid initialization for grid logic)
2. **Replace game-specific content** with generic placeholders:
   - Specific character names -> "Player", "Enemy", "Entity"
   - Hardcoded values -> config references (gameConfig.xxx.value)
   - Specific texture keys -> placeholder_texture comments
   - Specific dialogue -> TODO comments
3. **Preserve the architecture**: Keep class hierarchies, hook patterns, and lifecycle methods intact
4. **Mark extension points**: Add TODO/override comments where game-specific customization should happen

## Output Format

Return a JSON object with this structure:
{
  "templateFiles": [
    {
      "relativePath": "src/scenes/BaseLevelScene.ts",
      "content": "// ... generalized TypeScript code ...",
      "role": "base_class" | "copy_template" | "system" | "behavior" | "utility"
    }
  ],
  "summary": "Brief description of what this template family provides"
}

## Rules
- Output VALID JSON only (no markdown fences around the top-level JSON)
- Template file contents should be valid TypeScript
- Keep imports but generalize paths where needed
- base_class: Engine code that should NOT be modified (KEEP files)
- copy_template: Files meant to be copied and customized (_Template* pattern)
- system: Reusable system managers (BoardManager, WaveManager, etc.)
- behavior: Reusable behavior components (PatrolAI, MeleeAttack, etc.)
- utility: Shared utility functions"""

    def _build_user_prompt(self, patterns: ExtractedPatterns) -> str:
        """Build prompt with extracted patterns."""
        parts = [
            f"## Archetype: {patterns.archetype}",
            f"## Physics: gravity={patterns.physics_profile.has_gravity}, "
            f"perspective={patterns.physics_profile.perspective}, "
            f"movement={patterns.physics_profile.movement_type}",
            "",
            "## Directory Structure",
        ]
        for dir_name in patterns.file_structure.directories:
            files = patterns.file_structure.files_by_directory.get(dir_name, [])
            parts.append(f"{dir_name}/: {', '.join(files)}")

        parts.extend(["", "## Class Hierarchy"])
        for cls in patterns.classes:
            ext = f" extends {cls.parent_class}" if cls.parent_class else ""
            abs_flag = "abstract " if cls.is_abstract else ""
            parts.append(f"- {abs_flag}{cls.name}{ext} ({cls.file_path})")
            for m in [m for m in cls.methods if m.is_abstract or m.is_override]:
                parts.append(f"    {m.signature}")

        parts.extend(["", "## Hooks"])
        for hook in patterns.hooks:
            abs_flag = " [ABSTRACT]" if hook.is_abstract else ""
            parts.append(f"- {hook.declaring_class}::{hook.name}{abs_flag}")

        if patterns.config_extensions:
            parts.extend(["", "## Config Extensions (beyond M0 baseline)"])
            for cf in patterns.config_extensions:
                parts.append(f"- {cf.path}: {cf.value} ({cf.type})")

        parts.extend(["", "## Key Source Code"])
        for file_path, code in list(patterns.code_snippets.items())[:8]:
            truncated = code[:3000]
            parts.append(f"\n### {file_path}\n```typescript\n{truncated}\n```")

        parts.append("\n\nGeneralize this into a reusable template family. "
                     "Replace game-specific content with placeholders. "
                     "Focus on the BASE CLASSES and SYSTEMS that would be reusable "
                     "across different games of this archetype. Output JSON only.")

        return "\n".join(parts)

    def _parse_llm_response(self, raw: str, patterns: ExtractedPatterns) -> AbstractedTemplates | None:
        """Parse LLM abstraction response."""
        import json
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"```json?\n?", "", text).replace("```", "").strip()

        try:
            parsed = json.loads(text)
            template_files = [
                TemplateFileDef(
                    relative_path=tf["relativePath"],
                    content=tf["content"],
                    role=tf["role"],
                )
                for tf in parsed["templateFiles"]
            ]
            return AbstractedTemplates(
                archetype=patterns.archetype,
                template_files=template_files,
                hooks=patterns.hooks,
                config_schema=patterns.config_extensions,
                summary=parsed.get("summary", ""),
            )
        except (json.JSONDecodeError, KeyError):
            return None

    def _rule_based_abstract(self, patterns: ExtractedPatterns) -> AbstractedTemplates:
        """Fallback: extract base classes and templates by naming convention."""
        template_files = []
        for file_path, code in patterns.code_snippets.items():
            if re.search(r"Base\w+", file_path):
                template_files.append(TemplateFileDef(
                    relative_path=file_path,
                    content=code,
                    role="base_class",
                ))
            elif re.search(r"_Template\w+", file_path):
                template_files.append(TemplateFileDef(
                    relative_path=file_path,
                    content=code,
                    role="copy_template",
                ))
            elif file_path.endswith("utils.ts"):
                template_files.append(TemplateFileDef(
                    relative_path=file_path,
                    content=code,
                    role="utility",
                ))

        return AbstractedTemplates(
            archetype=patterns.archetype,
            template_files=template_files,
            hooks=patterns.hooks,
            config_schema=patterns.config_extensions,
            summary=f'Rule-based abstraction for {patterns.archetype}: '
                    f'{len(template_files)} template files, {len(patterns.hooks)} hooks',
        )
```

## 5.7 Merger

```python
# skills/template_skill/merger.py
import uuid
from datetime import datetime


class FamilyMerger:
    """
    Merge new abstracted templates into the template library.

    Either creates a new family or merges patterns into an existing one.
    """

    STABILITY_INCREMENT = 0.1
    MAX_STABILITY = 1.0

    def merge(
        self,
        abstracted: AbstractedTemplates,
        library: TemplateLibrary,
        project_path: str,
        task_id: str,
    ) -> tuple[TemplateLibrary, str]:
        """
        Merge abstracted templates into the library.

        Returns:
            (updated_library, family_id)
        """
        # Find existing family with matching archetype
        existing = next(
            (f for f in library.families if f.archetype == abstracted.archetype),
            None,
        )

        if existing:
            # Merge into existing family
            updated_family = self._merge_into_family(existing, abstracted, project_path)
            library.families = [updated_family if f.id == existing.id else f for f in library.families]
            action = "merged_to_family"
        else:
            # Create new family
            family = self._create_family(abstracted, project_path, task_id, len(library.families))
            library.families.append(family)
            updated_family = family
            action = "created_family"

        # Add evolution log entry
        library.evolution_log.append(EvolutionEntry(
            task_id=task_id,
            timestamp=datetime.utcnow().isoformat(),
            project_path=project_path,
            archetype=abstracted.archetype,
            action=action,
            family_id=updated_family.id,
            patterns_extracted=len(abstracted.template_files),
            patterns_merged=len(updated_family.template_files),
        ))

        library.version += 1
        library.updated_at = datetime.utcnow().isoformat()

        return library, updated_family.id

    def _create_family(
        self,
        abstracted: AbstractedTemplates,
        project_path: str,
        task_id: str,
        family_count: int,
    ) -> TemplateFamily:
        """Create a new template family from abstracted templates."""
        return TemplateFamily(
            id=f"fam-{abstracted.archetype}-{family_count:03d}",
            archetype=abstracted.archetype,
            physics_profile=PhysicsProfile(
                has_gravity=False,  # Would be populated from classification
                perspective="none",
                movement_type="continuous",
            ),
            discovered_at_task=int(task_id.split("-")[-1]) if "-" in task_id else 0,
            contributing_projects=[project_path],
            stability=0.1,
            file_structure=DirectoryPattern(directories=[], files_by_directory={}),
            base_classes=[],
            hooks=abstracted.hooks,
            config_extensions=abstracted.config_schema,
            template_files=abstracted.template_files,
            summary=abstracted.summary,
        )

    def _merge_into_family(
        self,
        family: TemplateFamily,
        abstracted: AbstractedTemplates,
        project_path: str,
    ) -> TemplateFamily:
        """Merge new patterns into an existing family."""
        # Add contributing project
        if project_path not in family.contributing_projects:
            family.contributing_projects.append(project_path)

        # Increase stability (capped at 1.0)
        family.stability = min(
            family.stability + self.STABILITY_INCREMENT,
            self.MAX_STABILITY,
        )

        # Merge hooks (deduplicate by name)
        existing_hook_names = {h.name for h in family.hooks}
        for hook in abstracted.hooks:
            if hook.name not in existing_hook_names:
                family.hooks.append(hook)

        # Merge config extensions (deduplicate by path)
        existing_paths = {c.path for c in family.config_extensions}
        for cfg in abstracted.config_schema:
            if cfg.path not in existing_paths:
                family.config_extensions.append(cfg)

        # Merge template files (deduplicate by relative_path)
        existing_paths = {tf.relative_path for tf in family.template_files}
        for tf in abstracted.template_files:
            if tf.relative_path not in existing_paths:
                family.template_files.append(tf)

        family.summary = abstracted.summary  # Update summary to latest

        return family
```

## 5.8 Library Manager

```python
# skills/template_skill/library_manager.py
import json
from pathlib import Path


class LibraryManager:
    """
    CRUD operations for the Template Library.

    Persists library manifest to library.json and individual family files
    to families/{archetype}/.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.library_path = output_dir / "library.json"
        self.families_dir = output_dir / "families"

    async def initialize(self) -> TemplateLibrary:
        """Create a fresh, empty template library."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.families_dir.mkdir(parents=True, exist_ok=True)

        library = TemplateLibrary(
            version=0,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            meta_template_path="agent-test/template-skill/meta-template",
            families=[],
            evolution_log=[],
        )
        await self.save(library)
        return library

    async def load(self) -> TemplateLibrary | None:
        """Load library from disk. Returns None if not found."""
        if not self.library_path.exists():
            return None

        async with aiofiles.open(self.library_path, "r") as f:
            raw = await f.read()

        data = json.loads(raw)
        return TemplateLibrary(**data)

    async def load_or_init(self) -> TemplateLibrary:
        """Load existing library or initialize a new one."""
        existing = await self.load()
        if existing:
            return existing
        return await self.initialize()

    async def save(self, library: TemplateLibrary) -> None:
        """Save library to disk."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Save manifest (without full template content)
        manifest = library.model_dump()
        manifest["families"] = [
            {
                **f.model_dump(),
                "template_files": [
                    {"relative_path": tf["relative_path"], "role": tf["role"], "content_length": len(tf["content"])}
                    for tf in f.model_dump()["template_files"]
                ],
            }
            for f in library.families
        ]

        async with aiofiles.open(self.library_path, "w") as f:
            await f.write(json.dumps(manifest, indent=2))

        # Save each family's template files
        for family in library.families:
            await self._save_family_files(family)

    async def _save_family_files(self, family: TemplateFamily) -> None:
        """Persist a family's template files to disk."""
        family_dir = self.families_dir / family.archetype
        family_dir.mkdir(parents=True, exist_ok=True)

        # Save metadata
        metadata = {
            "id": family.id,
            "archetype": family.archetype,
            "physics_profile": family.physics_profile.model_dump(),
            "discovered_at_task": family.discovered_at_task,
            "contributing_projects": family.contributing_projects,
            "stability": family.stability,
            "file_structure": family.file_structure.model_dump(),
            "hooks": [h.model_dump() for h in family.hooks],
            "config_extensions": [c.model_dump() for c in family.config_extensions],
            "summary": family.summary,
            "template_file_count": len(family.template_files),
        }

        async with aiofiles.open(family_dir / "family.json", "w") as f:
            await f.write(json.dumps(metadata, indent=2))

        # Save each template file
        for tf in family.template_files:
            file_path = family_dir / tf.relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(file_path, "w") as f:
                await f.write(tf.content)

    def get_summary(self, library: TemplateLibrary) -> str:
        """Get a human-readable summary of the library state."""
        lines = [
            f"Template Library v{library.version}",
            f"Created: {library.created_at}",
            f"Updated: {library.updated_at}",
            f"Meta Template: {library.meta_template_path}",
            f"Families: {len(library.families)}",
            f"Total Evolution Steps: {len(library.evolution_log)}",
            "",
        ]

        if not library.families:
            lines.append("  (no families yet — run evolve to start accumulating experience)")

        for family in library.families:
            lines.extend([
                f"  [{family.archetype}] {family.id}",
                f"    Stability: {family.stability * 100:.0f}%",
                f"    Contributing projects: {len(family.contributing_projects)}",
                f"    Template files: {len(family.template_files)}",
                f"    Hooks: {len(family.hooks)}",
                f"    Config extensions: {len(family.config_extensions)}",
                f"    Discovered at task: #{family.discovered_at_task}",
                f"    Summary: {family.summary}",
                "",
            ])

        if library.evolution_log:
            lines.append("Recent Evolution Log:")
            for entry in library.evolution_log[-5:]:
                lines.append(
                    f"  [{entry.timestamp}] {entry.action} -> {entry.family_id} "
                    f"({entry.archetype}, extracted: {entry.patterns_extracted}, "
                    f"merged: {entry.patterns_merged})"
                )

        return "\n".join(lines)

    def find_family(self, library: TemplateLibrary, archetype: str) -> TemplateFamily | None:
        """Find a family by archetype name."""
        return next((f for f in library.families if f.archetype == archetype), None)
```

## 5.9 Template Skill Orchestrator

```python
# skills/template_skill/__init__.py

class TemplateSkill:
    """
    Main Template Skill orchestrator.

    Combines all components into a single pipeline:
    collect -> classify -> extract -> abstract -> merge -> save
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        library_manager: LibraryManager,
    ):
        self.collector = ProjectCollector()
        self.classifier = Classifier(llm_client)
        self.extractor = PatternExtractor()
        self.abstractor = Abstractor(llm_client)
        self.merger = FamilyMerger()
        self.library_manager = library_manager

    async def evolve(self, project_dir: Path, task_id: str) -> TemplateLibrary:
        """
        Evolve the template library from a completed project.

        Pipeline:
        1. Collect project snapshot
        2. Classify archetype (library-aware)
        3. Extract patterns
        4. Abstract into templates
        5. Merge into library
        6. Persist
        """
        # Load existing library
        library = await self.library_manager.load_or_init()

        # Step 1: Collect
        print(f"[TemplateSkill] Collecting project: {project_dir}")
        snapshot = await self.collector.collect(project_dir)

        # Step 2: Classify
        print(f"[TemplateSkill] Classifying project...")
        classification = await self.classifier.classify(snapshot, library)
        print(f"[TemplateSkill] Classified as: {classification.archetype} "
              f"(confidence: {classification.confidence})")

        # Step 3: Extract
        print(f"[TemplateSkill] Extracting patterns...")
        patterns = self.extractor.extract(snapshot, classification)
        print(f"[TemplateSkill] Extracted: {len(patterns.classes)} classes, "
              f"{len(patterns.hooks)} hooks, {len(patterns.config_extensions)} config fields")

        # Step 4: Abstract
        print(f"[TemplateSkill] Abstracting templates...")
        abstracted = await self.abstractor.abstract(patterns)
        print(f"[TemplateSkill] Abstracted: {len(abstracted.template_files)} template files")

        # Step 5: Merge
        print(f"[TemplateSkill] Merging into library...")
        library, family_id = self.merger.merge(
            abstracted, library, str(project_dir), task_id,
        )
        print(f"[TemplateSkill] Merged into family: {family_id}")

        # Step 6: Save
        await self.library_manager.save(library)
        print(f"[TemplateSkill] Library saved. {len(library.families)} families total.")

        return library

    async def get_library_summary(self) -> str:
        """Get a human-readable summary of the template library."""
        library = await self.library_manager.load_or_init()
        return self.library_manager.get_summary(library)
```
