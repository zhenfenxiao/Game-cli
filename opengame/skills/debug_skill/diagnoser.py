"""ErrorDiagnoser — matches errors against protocol entries.

Three-tier diagnosis:
1. Score-based matching against protocol entries
2. Rule-based matching via protocol rules
3. LLM fallback for novel errors
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from opengame.core.llm_client import BaseLlmClient
from opengame.skills.debug_skill.types import (
    DebugEntry,
    DebugProtocol,
    FailureSignature,
    ParsedError,
)


@dataclass
class Diagnosis:
    """Internal diagnosis result (not a Pydantic model)."""

    error: ParsedError
    matched: bool = False
    matched_entry_id: str = ""
    candidate_entry: DebugEntry | None = None
    root_cause: str = ""
    suggested_fix: str = ""


class ErrorDiagnoser:
    """Diagnose errors using protocol matching and LLM fallback.

    Three-tier approach per error:
    1. Score-based match against protocol entries (threshold >= 10 points)
    2. Rule-based match via protocol rules
    3. LLM diagnosis for novel errors
    """

    def __init__(self, llm_client: BaseLlmClient) -> None:
        self.llm_client = llm_client

    async def diagnose(
        self,
        errors: list[ParsedError],
        protocol: DebugProtocol,
        project_dir: str | Path,
    ) -> list[Diagnosis]:
        """Diagnose all parsed errors.

        Args:
            errors: Parsed errors from stage output.
            protocol: Current debug protocol.
            project_dir: Path to the game project.

        Returns:
            List of Diagnosis objects, one per error.
        """
        diagnoses: list[Diagnosis] = []

        for error in errors:
            # Tier 1: Score-based protocol entry match
            diagnosis = self._match_error(error, protocol)

            # Tier 2: Rule-based match (if no entry matched)
            if not diagnosis.matched:
                diagnosis = self._match_rule(error, protocol)

            # Tier 3: LLM diagnosis (novel error)
            if not diagnosis.matched:
                diagnosis = await self._llm_diagnose(error, project_dir)

            diagnoses.append(diagnosis)

        return diagnoses

    # --- Tier 1: Protocol entry matching ---

    def _match_error(self, error: ParsedError, protocol: DebugProtocol) -> Diagnosis:
        """Score-based matching against protocol entries."""
        best_score = 0
        best_entry: DebugEntry | None = None

        for entry in protocol.entries:
            score = 0

            # Error code match: 10 points
            if entry.signature.error_code and entry.signature.error_code == error.code:
                score += 10

            # Message pattern match: 5 points
            if entry.signature.message_pattern:
                try:
                    if re.search(entry.signature.message_pattern, error.message, re.IGNORECASE):
                        score += 5
                except re.error:
                    pass

            # File context match: 3 points
            if entry.signature.file_context and error.file:
                if entry.signature.file_context in error.file:
                    score += 3

            # Stage match: 1 point (bonus, not always available)
            if entry.signature.stage:
                score += 1

            if score > best_score and score >= 10:
                best_score = score
                best_entry = entry

        if best_entry:
            return Diagnosis(
                error=error,
                matched=True,
                matched_entry_id=best_entry.id,
                candidate_entry=best_entry,
                root_cause=best_entry.root_cause,
                suggested_fix=json.dumps(best_entry.fix) if best_entry.fix else "",
            )

        return Diagnosis(error=error, matched=False)

    # --- Tier 2: Rule-based matching ---

    @staticmethod
    def _match_rule(error: ParsedError, protocol: DebugProtocol) -> Diagnosis:
        """Match error against protocol rules' queries."""
        for rule in protocol.rules:
            for check in rule.checks:
                if check.query:
                    try:
                        if re.search(check.query, error.message, re.IGNORECASE):
                            return Diagnosis(
                                error=error,
                                matched=True,
                                matched_entry_id=rule.id,
                                root_cause=check.violation_message or rule.description,
                                suggested_fix="",
                            )
                    except re.error:
                        pass

        return Diagnosis(error=error, matched=False)

    # --- Tier 3: LLM diagnosis ---

    async def _llm_diagnose(self, error: ParsedError, project_dir: str | Path) -> Diagnosis:
        """Use LLM to diagnose a novel error."""
        prompt = f"""You are a TypeScript/Phaser 3 debugging expert. Diagnose this build error.

## Error
- Code: {error.code}
- Message: {error.message}
- File: {error.file or 'unknown'}
- Line: {error.line or 'unknown'}
- Column: {error.column or 'unknown'}

## Project
{project_dir}

## Output Format
```json
{{
  "root_cause": "Brief explanation of what caused this error",
  "suggested_fix": "Specific steps to fix the error",
  "fix_type": "edit|shell|create|delete|config"
}}
```"""

        try:
            response = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1000,
            )

            content = response.content or "{}"

            # Parse JSON from response
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                return Diagnosis(
                    error=error,
                    matched=False,
                    root_cause=data.get("root_cause", "Unknown"),
                    suggested_fix=json.dumps(data),
                )

        except Exception:
            pass

        return Diagnosis(
            error=error,
            matched=False,
            root_cause=f"Unable to diagnose: {error.message[:100]}",
            suggested_fix="",
        )
