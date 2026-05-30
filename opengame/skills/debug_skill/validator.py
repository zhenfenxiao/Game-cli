"""ProjectValidator — pre-execution validation checks.

Checks project structure, file existence, and configuration before
attempting build/test/dev. Many checks are stubbed as specified
in the PRD (returning None for unimplemented checks).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import aiofiles

from opengame.skills.debug_skill.types import DebugProtocol, ValidationResult


class ProjectValidator:
    """Validate a project before execution.

    Runs protocol-derived validation checks against the project
    to catch known issues before running build/test/dev.
    """

    def __init__(self) -> None:
        pass

    async def validate(
        self,
        project_dir: str | Path,
        protocol: DebugProtocol,
    ) -> list[ValidationResult]:
        """Run all applicable validation checks.

        Args:
            project_dir: Path to the game project.
            protocol: Current debug protocol with rules.

        Returns:
            List of ValidationResult, one per applicable rule.
        """
        root = Path(project_dir).resolve()
        results: list[ValidationResult] = []

        for rule in protocol.rules:
            # Check preconditions
            if not self._preconditions_met(rule.preconditions, root):
                continue

            violations: list[str] = []

            for check in rule.checks:
                check_result = await self._run_check(check, root)
                if check_result:
                    violations.append(check_result)

            results.append(ValidationResult(
                rule_id=rule.id,
                passed=len(violations) == 0,
                violations=violations,
            ))

        return results

    @staticmethod
    def _preconditions_met(preconditions: list[str], root: Path) -> bool:
        """Check if all preconditions are met."""
        for cond in preconditions:
            if cond.startswith("has "):
                filename = cond[4:]
                if not (root / filename).exists():
                    return False
        return True

    async def _run_check(self, check, root: Path) -> str | None:
        """Run a single validation check. Returns violation message or None."""
        target = check.target
        file_pattern = check.file_pattern
        query = check.query

        if target == "file":
            return await self._check_file(root, file_pattern, query, check.violation_message)
        elif target == "config":
            return await self._check_config(root, query, check.violation_message)
        elif target == "imports":
            return None  # Stub — not yet implemented per PRD
        elif target == "scene_registration":
            return None  # Stub
        elif target == "assets":
            return None  # Stub

        return None

    @staticmethod
    async def _check_file(
        root: Path, file_pattern: str, query: str, violation_msg: str,
    ) -> str | None:
        """Check a file against a regex query."""
        if not file_pattern:
            return None

        target_file = root / file_pattern
        if not target_file.exists():
            return violation_msg or f"Required file not found: {file_pattern}"

        if query:
            try:
                async with aiofiles.open(target_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                if not re.search(query, content):
                    return violation_msg or f"Pattern not found in {file_pattern}: {query}"
            except Exception:
                return f"Could not read {file_pattern}"
        return None

    @staticmethod
    async def _check_config(
        root: Path, query: str, violation_msg: str,
    ) -> str | None:
        """Check gameConfig.json for expected fields."""
        config_path = root / "gameConfig.json"
        if not config_path.exists():
            return violation_msg or "gameConfig.json not found"

        if query:
            try:
                async with aiofiles.open(config_path, "r", encoding="utf-8") as f:
                    data = json.loads(await f.read())
                # query is a dot-notation path like "physics.gravity"
                parts = query.split(".")
                current = data
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return violation_msg or f"Config key not found: {query}"
            except (json.JSONDecodeError, KeyError, TypeError):
                return violation_msg or f"Invalid config structure for query: {query}"

        return None
