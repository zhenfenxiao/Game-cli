"""DebugSkill — Algorithm 1 REPEAT...UNTIL loop for game debugging.

Orchestrates the complete debug pipeline:
  REPEAT
    build → test
    IF failure: diagnose → repair → verify
  UNTIL all pass OR max_iterations reached
  Optionally: dev server probe, protocol evolution
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from opengame.core.llm_client import BaseLlmClient
from opengame.skills.debug_skill.diagnoser import ErrorDiagnoser
from opengame.skills.debug_skill.generalizer import RuleGeneralizer
from opengame.skills.debug_skill.protocol_manager import ProtocolManager
from opengame.skills.debug_skill.recorder import OutcomeRecorder
from opengame.skills.debug_skill.repairer import ErrorRepairer
from opengame.skills.debug_skill.runner import StageRunner
from opengame.skills.debug_skill.types import (
    DebugIteration,
    DebugLoopResult,
    DebugTrace,
)
from opengame.skills.debug_skill.validator import ProjectValidator


class DebugSkill:
    """Algorithm 1 debug loop: validate, build, test, diagnose, repair, repeat.

    Usage:
        skill = DebugSkill(llm_client, protocol_manager)
        result = await skill.debug(Path("./my-game"))
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        protocol_manager: ProtocolManager,
        max_iterations: int = 20,
    ) -> None:
        self.llm_client = llm_client
        self.protocol_manager = protocol_manager
        self.max_iterations = max_iterations
        self._auto_fix = False  # If True, apply fixes without verify step
        self._on_progress = None  # callback(iteration, stage, action, detail)

        # Initialize sub-components
        self.validator = ProjectValidator()
        self.runner = StageRunner()
        self.diagnoser = ErrorDiagnoser(llm_client)
        self.repairer = ErrorRepairer(llm_client)
        self.recorder = OutcomeRecorder()
        self.generalizer = RuleGeneralizer(llm_client)

    def set_on_progress(self, callback) -> None:
        """Set callback for debug progress: callback(iteration, stage, action, detail)."""
        self._on_progress = callback

    async def get_protocol_context(self) -> str:
        """Get protocol knowledge formatted for inclusion in system prompts.

        Returns formatted text listing known errors and prevention rules
        that the LLM agent can use to avoid repeating mistakes.
        """
        protocol = await self.protocol_manager.load_or_init()
        if not protocol.entries and not protocol.rules:
            return ""

        lines = ["\n## Known Issues & Best Practices (from debug protocol)\n"]

        # Top entries (most frequent errors)
        if protocol.entries:
            top = sorted(protocol.entries, key=lambda e: e.occurrences, reverse=True)[:8]
            if top:
                lines.append("### Frequent Errors")
                for entry in top:
                    if entry.occurrences >= 1:
                        lines.append(
                            f"- **{entry.signature.error_code or 'Error'}**: "
                            f"{entry.root_cause or entry.signature.message_pattern[:100]}\n"
                            f"  Fix: {entry.fix.get('description', 'see protocol')} "
                            f"(occurrences: {entry.occurrences})"
                        )

        # Active prevention rules
        if protocol.rules:
            lines.append("\n### Prevention Rules")
            for rule in protocol.rules[:5]:
                lines.append(f"- **{rule.name}**: {rule.description}")
                for check in rule.checks[:2]:
                    if check.violation_message:
                        lines.append(f"  - Check: {check.violation_message}")

        return "\n".join(lines) if len(lines) > 1 else ""

    async def debug(
        self,
        project_dir: str | Path,
        run_dev: bool = False,
        evolve_after: bool = True,
    ) -> DebugLoopResult:
        """Run the full debug loop on a game project.

        Args:
            project_dir: Path to the game project.
            run_dev: Whether to also probe the dev server.
            evolve_after: Whether to generalize rules after debugging.

        Returns:
            DebugLoopResult with success status, trace, and updated protocol.
        """
        project_path = str(project_dir)
        started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.monotonic()

        # Load protocol
        protocol = await self.protocol_manager.load_or_init()

        # Initialize trace
        trace = DebugTrace(
            project_path=project_path,
            started_at=started_at,
            max_iterations=self.max_iterations,
        )

        # Step 1: Pre-execution validation
        validation_results = await self.validator.validate(project_path, protocol)
        trace.validation_results = validation_results
        critical_violations = [v for v in validation_results if not v.passed]

        # Algorithm 1: REPEAT...UNTIL loop
        for iteration_num in range(1, self.max_iterations + 1):
            iter_start = time.monotonic()

            iter_entry = DebugIteration(
                iteration=iteration_num,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            # Stage 1: Build
            build_result = await self.runner.run(project_path, "build")
            iter_entry.stage = "build"
            iter_entry.passed = build_result.success
            iter_entry.raw_error = build_result.stderr if not build_result.success else ""
            iter_entry.duration_ms = int((time.monotonic() - iter_start) * 1000)

            if not build_result.success:
                if self._on_progress:
                    errs = build_result.errors
                    detail = "; ".join(e.message[:60] for e in errs[:2]) if errs else (build_result.stderr or build_result.stdout)[:120]
                    self._on_progress(iteration_num, "build", "fail", detail)
                iter_entry.raw_error = build_result.stderr or build_result.stdout
                # Diagnose and repair
                iter_entry = await self._handle_failure(
                    iter_entry, build_result.errors, protocol, project_path,
                )

                if not iter_entry.passed:
                    trace.iterations.append(iter_entry)
                    continue

            # Stage 2: Test
            test_result = await self.runner.run(project_path, "test")
            iter_entry.stage = "test"
            iter_entry.passed = test_result.success
            iter_entry.raw_error = test_result.stderr if not test_result.success else ""

            if not test_result.success:
                iter_entry = await self._handle_failure(
                    iter_entry, test_result.errors, protocol, project_path,
                )

                if not iter_entry.passed:
                    trace.iterations.append(iter_entry)
                    continue

            # Both build and test passed!
            trace.iterations.append(iter_entry)
            trace.success = True
            break

        # Post-loop
        trace.total_iterations = len(trace.iterations)

        # Optional: Dev server probe
        if run_dev and trace.success:
            dev_result = await self.runner.run(project_path, "dev")
            # Dev is just a probe — we don't repair dev failures (stub)

        # Optional: Evolve protocol
        if evolve_after and trace.success:
            await self.generalizer.generalize(trace, protocol)

        # Save protocol
        await self.protocol_manager.bump_version(protocol)

        # Finalize trace
        trace.completed_at = datetime.now(timezone.utc).isoformat()
        trace.total_duration_ms = int((time.monotonic() - start_time) * 1000)

        return DebugLoopResult(
            success=trace.success,
            trace=trace,
            protocol=protocol,
        )

    async def _handle_failure(
        self,
        iteration: DebugIteration,
        errors,
        protocol,
        project_path: str,
    ) -> DebugIteration:
        """Handle a stage failure: diagnose, repair, verify.

        Args:
            iteration: Current debug iteration (mutated in place).
            errors: ParsedError list from the failed stage.
            protocol: Current debug protocol.
            project_path: Path to the game project.

        Returns:
            Updated debug iteration.
        """
        if not errors:
            # No structured errors parsed — use raw output as a generic error
            raw = (iteration.raw_error or "")[:500]
            if not raw.strip():
                iteration.passed = False
                return iteration
            # Create a synthetic ParsedError so LLM can still attempt diagnosis
            from opengame.skills.debug_skill.types import ParsedError
            errors = [ParsedError(code="BUILD_FAILED", message=raw)]

        # Diagnose all errors
        diagnoses = await self.diagnoser.diagnose(errors, protocol, project_path)

        # Repair the first diagnosed error
        repaired = False
        for i, (error, diagnosis) in enumerate(zip(errors, diagnoses)):
            if i >= 3:  # Max 3 repair attempts per iteration
                break

            repair = await self.repairer.repair(diagnosis, error, project_path)

            if diagnosis.matched:
                iteration.matched_entry_id = diagnosis.matched_entry_id
                trace_entry = {"entry_id": diagnosis.matched_entry_id, "action": "matched"}
                if diagnosis.matched_entry_id not in trace.new_entries:
                    trace_entry["action"] = "matched"
            else:
                trace_entry = self.recorder.record(
                    protocol, diagnosis, repair, project_path, verified=False,
                )
                if trace_entry.get("entry_id"):
                    iteration.new_entry_id = trace_entry["entry_id"]

            iteration.repair_action = repair.description

            if self._on_progress:
                self._on_progress(iteration.iteration, iteration.stage,
                    "repair",
                    f"{repair.description[:60]} (applied={repair.applied})")

            if repair.applied:
                if self._auto_fix:
                    # Auto-fix mode: trust the repair without verifying
                    iteration.passed = True
                    self.recorder.record(
                        protocol, diagnosis, repair, project_path, verified=True,
                    )
                    repaired = True
                    break
                else:
                    # Verify the fix: re-run the same stage
                    verify_result = await self.runner.run(
                        project_path,
                        iteration.stage if iteration.stage else "build",
                    )
                    iteration.passed = verify_result.success

                    if verify_result.success:
                        self.recorder.record(
                            protocol, diagnosis, repair, project_path, verified=True,
                        )
                        repaired = True
                        break

        if not repaired:
            iteration.passed = False

        return iteration
