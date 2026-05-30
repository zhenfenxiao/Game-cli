"""Pydantic v2 data models for Debug Skill.

Defines all models from PRD section 3.3:
FailureSignature, DebugEntry, ValidationCheck, ProtocolRule,
DebugProtocol, ParsedError, RunResult, ValidationResult,
DebugIteration, DebugTrace, DebugLoopResult, RepairResult.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


# --- Protocol Data ---


class FailureSignature(BaseModel):
    """Signature that identifies a known failure pattern."""

    stage: Literal["build", "test", "runtime"] = "build"
    error_code: str = ""
    message_pattern: str = ""
    file_context: str | None = None


class DebugEntry(BaseModel):
    """A single debug protocol entry — either reactive (from an error) or proactive (a rule)."""

    id: str = Field(description="Unique entry ID, e.g. 'entry-TS2322-abc12345'")
    kind: Literal["reactive", "proactive"] = "reactive"
    signature: FailureSignature = Field(default_factory=FailureSignature)
    root_cause: str = ""
    tags: list[str] = Field(default_factory=list)
    fix: dict = Field(default_factory=dict)
    occurrences: int = 1
    contributing_projects: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_matched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    generalized_from: str | None = None


class ValidationCheck(BaseModel):
    """A single validation check, part of a protocol rule."""

    target: Literal["file", "config", "imports", "scene_registration", "assets"] = "file"
    file_pattern: str = ""
    query: str = ""
    violation_message: str = ""


class ProtocolRule(BaseModel):
    """A proactive rule in the debug protocol, derived from repeated entries."""

    id: str = Field(description="Unique rule ID")
    name: str = ""
    description: str = ""
    preconditions: list[str] = Field(default_factory=list)
    action: Literal["flag", "fix", "block"] = "flag"
    checks: list[ValidationCheck] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    prevention_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DebugEvolutionEntry(BaseModel):
    """An entry in the protocol's evolution log."""

    task_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    project_path: str
    action: Literal["new_entry", "matched_existing", "generalized_rule"]
    entry_id: str = ""
    rule_id: str = ""
    details: str = ""


class DebugProtocol(BaseModel):
    """Complete debug protocol with reactive entries and proactive rules."""

    version: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    seed_protocol_path: str = ""
    entries: list[DebugEntry] = Field(default_factory=list)
    rules: list[ProtocolRule] = Field(default_factory=list)
    evolution_log: list[DebugEvolutionEntry] = Field(default_factory=list)


# --- Runtime Results ---


class ParsedError(BaseModel):
    """A single error parsed from build/test/dev output."""

    code: str = ""
    message: str = ""
    file: str | None = None
    line: int | None = None
    column: int | None = None


class RunResult(BaseModel):
    """Result of running a build, test, or dev stage."""

    stage: Literal["build", "test", "dev"] = "build"
    success: bool = False
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    errors: list[ParsedError] = Field(default_factory=list)
    duration_ms: int = 0


class ValidationResult(BaseModel):
    """Result of a single pre-execution validation check."""

    rule_id: str = ""
    passed: bool = True
    violations: list[str] = Field(default_factory=list)


# --- Loop Trace ---


class DebugIteration(BaseModel):
    """A single iteration in the debug loop."""

    iteration: int
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stage: str = ""
    passed: bool = False
    raw_error: str = ""
    matched_entry_id: str = ""
    new_entry_id: str = ""
    repair_action: str = ""
    duration_ms: int = 0


class DebugTrace(BaseModel):
    """Complete trace of a debug session."""

    project_path: str
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""
    success: bool = False
    total_iterations: int = 0
    max_iterations: int = 20
    validation_results: list[ValidationResult] = Field(default_factory=list)
    iterations: list[DebugIteration] = Field(default_factory=list)
    new_entries: list[str] = Field(default_factory=list)
    matched_entries: list[str] = Field(default_factory=list)
    total_duration_ms: int = 0


class DebugLoopResult(BaseModel):
    """Final result of a debug session."""

    success: bool
    trace: DebugTrace = Field(default_factory=DebugTrace)
    protocol: DebugProtocol | None = None


class RepairResult(BaseModel):
    """Result of applying a repair."""

    applied: bool = False
    description: str = ""
    patch: str = ""
    verify_stage: Literal["build", "test", "dev"] = "build"
