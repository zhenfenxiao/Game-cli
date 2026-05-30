"""Tests for ErrorDiagnoser."""

from unittest.mock import AsyncMock

import pytest

from opengame.skills.debug_skill.diagnoser import ErrorDiagnoser
from opengame.skills.debug_skill.types import (
    DebugEntry,
    DebugProtocol,
    FailureSignature,
    ParsedError,
)


class TestErrorDiagnoser:
    @pytest.fixture
    def mock_llm(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def diagnoser(self, mock_llm: AsyncMock) -> ErrorDiagnoser:
        return ErrorDiagnoser(mock_llm)

    def test_match_error_by_code(self, diagnoser: ErrorDiagnoser) -> None:
        protocol = DebugProtocol(entries=[
            DebugEntry(
                id="entry-1",
                kind="reactive",
                signature=FailureSignature(
                    error_code="TS2322",
                    message_pattern="not assignable",
                    stage="build",
                ),
                root_cause="Type mismatch",
                fix={"fix_type": "edit", "description": "Fix type"},
            ),
        ])

        error = ParsedError(
            code="TS2322",
            message="Type 'string' is not assignable to type 'number'",
            file="src/Game.ts",
            line=10,
            column=5,
        )

        diagnosis = diagnoser._match_error(error, protocol)
        assert diagnosis.matched is True
        assert diagnosis.matched_entry_id == "entry-1"

    def test_no_match_below_threshold(self, diagnoser: ErrorDiagnoser) -> None:
        protocol = DebugProtocol(entries=[
            DebugEntry(
                id="entry-1",
                kind="reactive",
                signature=FailureSignature(error_code="TS9999", message_pattern="something"),
            ),
        ])

        error = ParsedError(code="TS2322", message="Different error")

        diagnosis = diagnoser._match_error(error, protocol)
        assert diagnosis.matched is False

    @pytest.mark.asyncio
    async def test_diagnose_empty_errors(self, diagnoser: ErrorDiagnoser) -> None:
        protocol = DebugProtocol()
        diagnoses = await diagnoser.diagnose([], protocol, "/test")
        assert len(diagnoses) == 0

    @pytest.mark.asyncio
    async def test_diagnose_with_llm_fallback(self, diagnoser: ErrorDiagnoser, mock_llm: AsyncMock) -> None:
        mock_llm.generate.return_value.content = '{"root_cause": "test", "suggested_fix": "fix it", "fix_type": "edit"}'

        protocol = DebugProtocol()
        errors = [ParsedError(code="UNKNOWN", message="Something went wrong")]

        diagnoses = await diagnoser.diagnose(errors, protocol, "/test")
        assert len(diagnoses) == 1
