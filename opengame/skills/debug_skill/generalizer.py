"""RuleGeneralizer — derives proactive rules from repeated error entries.

When the same error appears >= 3 times across projects, generates
a ProtocolRule to prevent it proactively.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from datetime import datetime, timezone

from opengame.core.llm_client import BaseLlmClient
from opengame.skills.debug_skill.types import (
    DebugEntry,
    DebugProtocol,
    DebugTrace,
    ProtocolRule,
    ValidationCheck,
)

MIN_OCCURRENCES = 3


class RuleGeneralizer:
    """Generalize repeated error entries into proactive protocol rules.

    Identifies entries with >= MIN_OCCURRENCES that haven't been
    generalized yet, and creates ProtocolRules to prevent them.
    """

    def __init__(self, llm_client: BaseLlmClient) -> None:
        self.llm_client = llm_client

    async def generalize(self, trace: DebugTrace, protocol: DebugProtocol) -> int:
        """Generalize repeated entries into rules.

        Args:
            trace: The current debug session trace.
            protocol: The current debug protocol.

        Returns:
            Number of new rules created.
        """
        # Find entries that qualify for generalization
        candidates: list[DebugEntry] = []
        for entry in protocol.entries:
            if entry.occurrences >= MIN_OCCURRENCES and not entry.generalized_from:
                # Check if already has a rule
                has_rule = any(
                    rule.derived_from and entry.id in rule.derived_from
                    for rule in protocol.rules
                )
                if not has_rule:
                    candidates.append(entry)

        if not candidates:
            return 0

        # Group by error code
        groups: dict[str, list[DebugEntry]] = {}
        for entry in candidates:
            code = entry.signature.error_code or "generic"
            groups.setdefault(code, []).append(entry)

        new_rules = 0

        for code, entries in groups.items():
            if len(entries) >= 1:
                try:
                    rule = await self._generate_rule(entries)
                    if rule:
                        protocol.rules.append(rule)

                        # Mark entries as generalized
                        for entry in entries:
                            entry.generalized_from = rule.id

                        new_rules += 1
                except Exception:
                    pass

        return new_rules

    async def _generate_rule(self, entries: list[DebugEntry]) -> ProtocolRule | None:
        """Generate a proactive rule from a group of similar entries.

        Uses LLM to analyze the error pattern and create a preventive rule.
        """
        if not entries:
            return None

        # Build prompt with entry details
        entries_text = "\n\n".join(
            f"### Entry {e.id}\n"
            f"- Error: {e.signature.error_code}\n"
            f"- Pattern: {e.signature.message_pattern}\n"
            f"- Root cause: {e.root_cause}\n"
            f"- Occurrences: {e.occurrences}\n"
            f"- Fix: {json.dumps(e.fix)}"
            for e in entries[:5]
        )

        prompt = f"""You are a code quality expert. Create a preventive validation rule based on these recurring errors.

## Recurring Errors
{entries_text}

## Output Format
```json
{{
  "name": "Short rule name",
  "description": "What this rule prevents",
  "preconditions": ["has package.json", "has gameConfig.json"],
  "action": "flag",
  "checks": [
    {{
      "target": "file",
      "file_pattern": "path/to/file.ts",
      "query": "regex to check for",
      "violation_message": "What to tell the developer"
    }}
  ]
}}
```"""

        try:
            response = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1000,
            )
            content = response.content or "{}"
        except Exception:
            return None

        # Parse JSON
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            return None

        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return None

        rule_id = f"rule-{str(uuid.uuid4())[:8]}"

        checks = [
            ValidationCheck(
                target=c.get("target", "file"),
                file_pattern=c.get("file_pattern", ""),
                query=c.get("query", ""),
                violation_message=c.get("violation_message", ""),
            )
            for c in data.get("checks", [])
        ]

        return ProtocolRule(
            id=rule_id,
            name=data.get("name", f"Auto-rule for {entries[0].signature.error_code}"),
            description=data.get("description", ""),
            preconditions=data.get("preconditions", []),
            action=data.get("action", "flag"),  # type: ignore[arg-type]
            checks=checks,
            derived_from=[e.id for e in entries],
            prevention_count=sum(e.occurrences for e in entries),
        )
