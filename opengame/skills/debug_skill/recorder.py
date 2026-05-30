"""OutcomeRecorder — records diagnosis and repair results into the protocol.

Handles entry creation, occurrence tracking, and message pattern generalization.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from opengame.skills.debug_skill.types import (
    DebugEntry,
    DebugProtocol,
    FailureSignature,
)


class OutcomeRecorder:
    """Record debug outcomes to the protocol.

    Creates new entries for novel errors, increments occurrences
    for matched entries, and generalizes error message patterns.
    """

    def __init__(self) -> None:
        pass

    def record(
        self,
        protocol: DebugProtocol,
        diagnosis,  # Diagnosis from diagnoser
        repair,  # RepairResult from repairer
        project_dir: str | Path,
        verified: bool = False,
    ) -> dict:
        """Record a diagnosis + repair outcome.

        Args:
            protocol: Current debug protocol.
            diagnosis: The Diagnosis result.
            repair: The RepairResult from applying the fix.
            project_dir: Path to the game project.
            verified: Whether the fix was verified (re-built/tested successfully).

        Returns:
            Dict with entry_id and action ("matched"/"created"/"none").
        """
        project_path = str(project_dir)

        # Case 1: Matched existing entry — increment
        if diagnosis.matched and diagnosis.matched_entry_id:
            return self._record_match(protocol, diagnosis, project_path)

        # Case 2: Novel error, fix verified — create new entry
        if verified and not diagnosis.matched:
            return self._create_entry(protocol, diagnosis, repair, project_path)

        return {"entry_id": "", "action": "none"}

    @staticmethod
    def _record_match(
        protocol: DebugProtocol,
        diagnosis,
        project_path: str,
    ) -> dict:
        """Update an existing debug entry."""
        for entry in protocol.entries:
            if entry.id == diagnosis.matched_entry_id:
                entry.occurrences += 1
                entry.last_matched_at = datetime.now(timezone.utc).isoformat()
                if project_path not in entry.contributing_projects:
                    entry.contributing_projects.append(project_path)
                return {"entry_id": entry.id, "action": "matched"}

        return {"entry_id": "", "action": "none"}

    def _create_entry(
        self,
        protocol: DebugProtocol,
        diagnosis,
        repair,
        project_path: str,
    ) -> dict:
        """Create a new debug protocol entry."""
        entry_id = self._generate_entry_id(diagnosis.error.code)

        # Generalize the error message into a regex pattern
        message_pattern = self._generalize_message(diagnosis.error.message)

        entry = DebugEntry(
            id=entry_id,
            kind="reactive",
            signature=FailureSignature(
                stage="build",
                error_code=diagnosis.error.code,
                message_pattern=message_pattern,
                file_context=diagnosis.error.file,
            ),
            root_cause=diagnosis.root_cause,
            tags=self._extract_tags(diagnosis.error.message),
            fix={
                "description": repair.description,
                "patch": repair.patch,
                "fix_type": "edit",
            },
            occurrences=1,
            contributing_projects=[project_path],
        )

        protocol.entries.append(entry)
        return {"entry_id": entry_id, "action": "created"}

    @staticmethod
    def _generate_entry_id(error_code: str) -> str:
        """Generate a unique entry ID."""
        short_uuid = str(uuid.uuid4())[:8]
        code = error_code.lower().replace(" ", "-") if error_code else "unknown"
        return f"entry-{code}-{short_uuid}"

    @staticmethod
    def _generalize_message(message: str) -> str:
        """Generalize an error message into a regex pattern.

        Replaces quoted strings with capture groups and identifiers
        with generic patterns so similar errors can be matched.
        """
        pattern = re.escape(message)

        # Replace quoted strings with capture groups
        pattern = re.sub(
            r"(\\'[^'\\]*\\')|(\\\"[^\"\\]*\\\")",
            r"(['\"]).*?\2",
            pattern,
        )

        # Replace numbers with wildcards
        pattern = re.sub(r"\\d+", r"\\d+", pattern)

        return pattern

    @staticmethod
    def _extract_tags(message: str) -> list[str]:
        """Extract relevant tags from an error message."""
        tags: list[str] = []

        tag_patterns = {
            "typescript": r"TS\d{4}",
            "import": r"import|module|resolve",
            "type": r"type\s|Type\s|assignable",
            "syntax": r"syntax|unexpected|expected",
            "property": r"property|does not exist",
            "argument": r"argument|parameter",
            "phaser": r"phaser|Phaser|scene|sprite",
        }

        for tag, pattern_str in tag_patterns.items():
            if re.search(pattern_str, message, re.IGNORECASE):
                tags.append(tag)

        return tags if tags else ["unclassified"]
