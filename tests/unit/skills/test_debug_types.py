"""Tests for Debug Skill data models."""

import json

from opengame.skills.debug_skill.types import (
    DebugIteration,
    DebugLoopResult,
    DebugProtocol,
    DebugTrace,
    FailureSignature,
    ParsedError,
    RunResult,
)


class TestParsedError:
    def test_construction(self) -> None:
        err = ParsedError(code="TS2322", message="Type string is not assignable to number")
        assert err.code == "TS2322"


class TestRunResult:
    def test_successful_build(self) -> None:
        result = RunResult(stage="build", success=True, exit_code=0)
        assert result.success is True


class TestDebugProtocol:
    def test_default(self) -> None:
        proto = DebugProtocol(version=0)
        assert proto.version == 0
        assert proto.entries == []

    def test_json_roundtrip(self) -> None:
        proto = DebugProtocol(version=1)
        data = json.loads(proto.model_dump_json())
        proto2 = DebugProtocol.model_validate(data)
        assert proto2.version == 1


class TestDebugLoopResult:
    def test_construction(self) -> None:
        trace = DebugTrace(project_path="/test", success=True)
        result = DebugLoopResult(success=True, trace=trace)
        assert result.success is True
