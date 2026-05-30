"""Abstractor — generalizes concrete game code into reusable templates.

Uses LLM-driven code generalization with rule-based fallback.
Replaces game-specific content (names, values, asset paths) with
placeholder tokens suitable for template reuse.
"""

from __future__ import annotations

import json
import re
from typing import Any

from opengame.core.llm_client import BaseLlmClient
from opengame.skills.template_skill.types import (
    AbstractedTemplates,
    ExtractedPatterns,
    HookDef,
    TemplateFileDef,
)

ABSTRACTOR_SYSTEM_PROMPT: str = """\
You are a code template abstractor. Your task is to convert concrete game code into generalized, reusable templates.

## Rules
1. Replace game-specific names (player character names, specific level names) with `{{PLACEHOLDER}}` tokens
2. Replace hardcoded values (sizes, speeds, colors) that vary per-game with `{{CONFIG_VALUE}}`
3. Replace asset paths (image URLs, audio files) with `{{ASSET_PATH}}`
4. Keep the code structure, class hierarchy, and logic intact
5. Classify each file into one of these roles:
   - **base_class**: Abstract base classes that all games extend (e.g., BaseScene, BasePlayer)
   - **copy_template**: Files that are copied as-is with placeholder replacements (e.g., _Template scenes)
   - **system**: Framework-level utilities (e.g., LevelManager, asset loaders)
   - **behavior**: Game-specific behavior implementations (e.g., Enemy, PowerUp)
   - **utility**: Utility functions and helpers

## Output Format
Output ONLY a JSON array of template files:
```json
[
  {
    "relative_path": "src/scenes/PlayScene_Template.ts",
    "content": "// Abstracted code...",
    "role": "copy_template"
  }
]
```"""


class Abstractor:
    """Abstract concrete game code into reusable templates.

    Strategy: LLM-first with rule-based fallback for files matching
    standard naming conventions.
    """

    def __init__(self, llm_client: BaseLlmClient) -> None:
        self.llm_client = llm_client

    async def abstract(self, patterns: ExtractedPatterns) -> AbstractedTemplates:
        """Abstract extracted patterns into template files.

        Args:
            patterns: Extracted patterns from a project.

        Returns:
            AbstractedTemplates with generalized template files.
        """
        # Try LLM-based abstraction
        try:
            return await self._try_llm_abstract(patterns)
        except Exception:
            pass

        # Fallback to rule-based
        return self._rule_based_abstract(patterns)

    # --- LLM abstraction ---

    async def _try_llm_abstract(self, patterns: ExtractedPatterns) -> AbstractedTemplates:
        """Attempt LLM-driven abstraction."""
        # Build the prompt with code snippets
        snippets_text = "\n\n".join(
            f"### {path}\n```typescript\n{content}\n```"
            for path, content in list(patterns.code_snippets.items())[:10]
        )

        user_prompt = f"""## Archetype
{patterns.archetype}

## Hooks to Preserve
{json.dumps([h.model_dump() for h in patterns.hooks], indent=2)}

## Code Snippets to Abstract
{snippets_text}

Abstract these files into template format."""

        response = await self.llm_client.generate(
            messages=[
                {"role": "system", "content": ABSTRACTOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=8000,
        )

        return self._parse_llm_response(response.content or "", patterns)

    def _parse_llm_response(self, content: str, patterns: ExtractedPatterns) -> AbstractedTemplates:
        """Parse LLM JSON response into AbstractedTemplates."""
        # Strip markdown fences
        content = re.sub(r"```(?:json)?\s*", "", content)
        content = content.strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return self._rule_based_abstract(patterns)
            else:
                return self._rule_based_abstract(patterns)

        if not isinstance(data, list):
            return self._rule_based_abstract(patterns)

        template_files = [
            TemplateFileDef(
                relative_path=item.get("relative_path", ""),
                content=item.get("content", ""),
                role=item.get("role", "behavior"),
            )
            for item in data
        ]

        return AbstractedTemplates(
            archetype=patterns.archetype,
            template_files=template_files,
            hooks=patterns.hooks,
            config_schema=patterns.config_extensions,
            summary=f"Abstracted {len(template_files)} template files for archetype '{patterns.archetype}'",
        )

    # --- Rule-based fallback ---

    def _rule_based_abstract(self, patterns: ExtractedPatterns) -> AbstractedTemplates:
        """Rule-based abstraction using naming conventions."""
        template_files: list[TemplateFileDef] = []

        for path, content in patterns.code_snippets.items():
            # Determine role by naming convention
            if "Base" in path:
                role = "base_class"
            elif "_Template" in path or "template" in path.lower():
                role = "copy_template"
            elif "Manager" in path or "LevelManager" in path:
                role = "system"
            elif "util" in path.lower() or "helper" in path.lower():
                role = "utility"
            else:
                role = "behavior"

            # Simple placeholder replacement
            abstracted = content
            # Replace quoted strings that look like game-specific names
            abstracted = re.sub(r"'[^']*player[^']*'", "'{{PLAYER_NAME}}'", abstracted, flags=re.IGNORECASE)
            abstracted = re.sub(r"'[^']*enemy[^']*'", "'{{ENEMY_NAME}}'", abstracted, flags=re.IGNORECASE)
            abstracted = re.sub(r'"[^"]*assets/[^"]*"', '"{{ASSET_PATH}}"', abstracted)

            template_files.append(TemplateFileDef(
                relative_path=path,
                content=abstracted,
                role=role,  # type: ignore[arg-type]
            ))

        return AbstractedTemplates(
            archetype=patterns.archetype,
            template_files=template_files,
            hooks=patterns.hooks,
            config_schema=patterns.config_extensions,
            summary=f"Rule-based abstraction: {len(template_files)} files",
        )
