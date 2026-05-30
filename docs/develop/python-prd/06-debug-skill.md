# 06 — Debug Skill

The Debug Skill maintains a living protocol of verified fixes. It runs a loop of verification, diagnosis, and repair until the project is buildable and runnable.

## 6.1 Core Principle

**Algorithm 1** (from the paper):

```
REPEAT
    Run verification and execution (build, test, run) guided by P
    IF failure observed
        Diagnose the failure using P and repair y
        Append a verified (signature, cause, fix) entry to P if new
UNTIL y is buildable and runnable
```

Where **P** is the living debugging protocol containing:
- **Entries**: Structured (signature, cause, fix) tuples
- **Rules**: Generalized reusable rules derived from repeated entries

## 6.2 Debug Loop

```python
# skills/debug_skill/debug_loop.py
import asyncio
from datetime import datetime
from pathlib import Path

MAX_DEBUG_ITERATIONS = 20


class DebugSkill:
    """
    Main Debug Skill orchestrator implementing Algorithm 1.
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        protocol_manager: ProtocolManager,
        max_iterations: int = MAX_DEBUG_ITERATIONS,
    ):
        self.llm_client = llm_client
        self.protocol_manager = protocol_manager
        self.validator = ProjectValidator()
        self.runner = StageRunner()
        self.diagnoser = ErrorDiagnoser(llm_client)
        self.repairer = ErrorRepairer(llm_client)
        self.recorder = OutcomeRecorder()
        self.generalizer = RuleGeneralizer(llm_client)
        self.max_iterations = max_iterations

    async def debug(
        self,
        project_dir: Path,
        run_dev: bool = False,
        evolve_after: bool = True,
    ) -> DebugLoopResult:
        """
        Run the complete debug loop on a project.

        This is the main entry point implementing Algorithm 1.

        Args:
            project_dir: Absolute path to the game project
            run_dev: Whether to run the dev stage after build + test pass
            evolve_after: Whether to evolve the protocol after the session

        Returns:
            DebugLoopResult with success flag, trace, and updated protocol
        """
        started_at = datetime.utcnow().isoformat()
        protocol = await self.protocol_manager.load_or_init()

        trace = DebugTrace(
            project_path=str(project_dir),
            started_at=started_at,
            completed_at="",
            success=False,
            total_iterations=0,
            max_iterations=self.max_iterations,
            validation_results=[],
            iterations=[],
            new_entries=[],
            matched_entries=[],
            total_duration_ms=0,
        )

        print(f"\n{'=' * 60}")
        print(f"Debug Loop: {project_dir}")
        print(f"Protocol v{protocol.version} | {len(protocol.entries)} entries | {len(protocol.rules)} rules")
        print(f"{'=' * 60}\n")

        # ── Step 0: Pre-execution validations ──────────────────────────────
        print("=== Pre-execution validation ===")
        validation_results = await self.validator.validate(project_dir, protocol)
        trace.validation_results = validation_results

        violations = [r for r in validation_results if not r.passed]
        if violations:
            print(f"  ! {len(violations)} validation(s) flagged:")
            for v in violations:
                for msg in v.violations:
                    print(f"    - {msg}")
        else:
            print("  OK All pre-execution validations passed")

        # ── REPEAT...UNTIL loop ────────────────────────────────────────────
        iteration = 0
        all_passed = False

        while iteration < self.max_iterations and not all_passed:
            iteration += 1
            iter_start = asyncio.get_event_loop().time()
            print(f"\n--- Iteration {iteration}/{self.max_iterations} ---")

            # Run build
            build_result = await self.runner.run(project_dir, "build")
            build_status = "PASS" if build_result.success else f"FAIL ({len(build_result.errors)} error(s))"
            print(f"  Build: {build_status}")

            if not build_result.success:
                protocol, iter_trace = await self._handle_failure(
                    build_result, protocol, project_dir, iteration, trace,
                )
                trace.iterations.append(iter_trace)
                continue

            # Run test
            test_result = await self.runner.run(project_dir, "test")
            test_status = "PASS" if test_result.success else f"FAIL ({len(test_result.errors)} error(s))"
            print(f"  Test: {test_status}")

            if not test_result.success:
                protocol, iter_trace = await self._handle_failure(
                    test_result, protocol, project_dir, iteration, trace,
                )
                trace.iterations.append(iter_trace)
                continue

            # Both passed
            all_passed = True
            trace.iterations.append(DebugIteration(
                iteration=iteration,
                timestamp=datetime.utcnow().isoformat(),
                stage="test",
                passed=True,
                duration_ms=int((asyncio.get_event_loop().time() - iter_start) * 1000),
            ))
            print("  OK Build and test both pass")

        # ── Optional: dev server probe ─────────────────────────────────────
        if all_passed and run_dev:
            print("\n=== Dev server probe ===")
            dev_result = await self.runner.run(project_dir, "dev")
            dev_status = "Server started" if dev_result.success else "Server failed"
            print(f"  Dev: {dev_status}")

        # ── Finalize trace ─────────────────────────────────────────────────
        trace.total_iterations = iteration
        trace.success = all_passed
        trace.completed_at = datetime.utcnow().isoformat()
        trace.total_duration_ms = int(
            (datetime.utcnow() - datetime.fromisoformat(started_at)).total_seconds() * 1000
        )

        # ── Evolve protocol (Algorithm 1 step 11) ──────────────────────────
        if evolve_after:
            print("\n=== Evolving protocol ===")
            new_rules = await self.generalizer.generalize(trace, protocol)
            if new_rules > 0:
                print(f"  Generated {new_rules} new rule(s)")
        else:
            await self.protocol_manager.bump_version(protocol)

        # ── Summary ────────────────────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print(f"Debug Loop {'SUCCEEDED' if all_passed else 'FAILED'}")
        print(f"  Iterations: {iteration}/{self.max_iterations} | "
              f"New entries: {len(trace.new_entries)} | "
              f"Matched: {len(trace.matched_entries)}")
        print(f"  Protocol v{protocol.version} | "
              f"{len(protocol.entries)} entries | {len(protocol.rules)} rules")
        print(f"  Duration: {trace.total_duration_ms / 1000:.1f}s")
        print(f"{'=' * 60}\n")

        # Save updated protocol
        await self.protocol_manager.save(protocol)

        return DebugLoopResult(success=all_passed, trace=trace, protocol=protocol)

    async def _handle_failure(
        self,
        run_result: RunResult,
        protocol: DebugProtocol,
        project_dir: Path,
        iteration_num: int,
        trace: DebugTrace,
    ) -> tuple[DebugProtocol, DebugIteration]:
        """
        Handle a failure: diagnose -> repair -> verify -> record.
        """
        iter_start = asyncio.get_event_loop().time()

        # Diagnose all errors
        diagnoses = await self.diagnoser.diagnose(
            run_result.errors, protocol, project_dir,
        )

        repair_action = ""
        matched_entry_id: str | None = None
        new_entry_id: str | None = None

        # Process the first diagnosable error (prioritize matched entries)
        primary_diag = next(
            (d for d in diagnoses if d.matched),
            next((d for d in diagnoses if d.candidate_entry), diagnoses[0] if diagnoses else None),
        )

        if primary_diag:
            primary_error = run_result.errors[diagnoses.index(primary_diag)]

            # Repair
            print(f"  Diagnosing: {primary_error.code} — {primary_error.message[:80]}")
            if primary_diag.matched:
                print(f"  -> Matched protocol entry: {primary_diag.matched_entry_id}")
            else:
                print("  -> Novel error, using LLM diagnosis")

            repair = await self.repairer.repair(primary_diag, primary_error, project_dir)
            repair_action = repair.description
            status = "Applied" if repair.applied else "Not applied"
            print(f"  Repair: {status} — {repair.description[:80]}")

            # Verify fix: re-run the same stage
            verify_result = await self.runner.run(project_dir, run_result.stage)
            verified = verify_result.success or len(verify_result.errors) < len(run_result.errors)

            # Record outcome to P
            log_entry = self.recorder.record(
                protocol, primary_diag, repair, project_dir, verified,
            )

            if primary_diag.matched and primary_diag.matched_entry_id:
                matched_entry_id = primary_diag.matched_entry_id
                if matched_entry_id not in trace.matched_entries:
                    trace.matched_entries.append(matched_entry_id)
            elif log_entry and log_entry.entry_id:
                new_entry_id = log_entry.entry_id
                trace.new_entries.append(new_entry_id)

        iteration = DebugIteration(
            iteration=iteration_num,
            timestamp=datetime.utcnow().isoformat(),
            stage="runtime" if run_result.stage == "dev" else run_result.stage,
            passed=False,
            raw_error="\n".join(f"{e.code}: {e.message}" for e in run_result.errors)[:2000],
            matched_entry_id=matched_entry_id,
            new_entry_id=new_entry_id,
            repair_action=repair_action,
            duration_ms=int((asyncio.get_event_loop().time() - iter_start) * 1000),
        )

        return protocol, iteration
```

## 6.3 Validator

```python
# skills/debug_skill/validator.py

class ProjectValidator:
    """
    Pre-execution validation — proactive checks using protocol rules.

    Runs before the debug loop to catch known issues before they become failures.
    """

    async def validate(
        self,
        project_dir: Path,
        protocol: DebugProtocol,
    ) -> list[ValidationResult]:
        """
        Run all applicable validation rules against the project.

        Checks each ProtocolRule's preconditions; if met, runs its checks.
        """
        results = []

        for rule in protocol.rules:
            # Check preconditions
            if not self._check_preconditions(rule, project_dir):
                continue

            # Run all checks in the rule
            violations = []
            for check in rule.checks:
                violation = await self._run_check(check, project_dir)
                if violation:
                    violations.append(violation)

            results.append(ValidationResult(
                rule_id=rule.id,
                passed=len(violations) == 0,
                violations=violations,
            ))

        return results

    def _check_preconditions(self, rule: ProtocolRule, project_dir: Path) -> bool:
        """Check if a rule's preconditions are met."""
        for precondition in rule.preconditions:
            if precondition == "has asset-pack.json":
                if not (project_dir / "public" / "assets" / "asset-pack.json").exists():
                    return False
            elif precondition == "has gameConfig.json":
                if not (project_dir / "src" / "gameConfig.json").exists():
                    return False
            # Add more precondition checks as needed
        return True

    async def _run_check(self, check: ValidationCheck, project_dir: Path) -> str | None:
        """Run a single validation check. Returns violation message or None."""
        if check.target == "file":
            return await self._check_file(check, project_dir)
        elif check.target == "config":
            return await self._check_config(check, project_dir)
        elif check.target == "imports":
            return await self._check_imports(check, project_dir)
        elif check.target == "scene_registration":
            return await self._check_scene_registration(check, project_dir)
        elif check.target == "assets":
            return await self._check_assets(check, project_dir)
        return None

    async def _check_file(self, check: ValidationCheck, project_dir: Path) -> str | None:
        """Check a file against a regex query."""
        import glob
        import re

        pattern = check.file_pattern or "**/*"
        query = re.compile(check.query)

        for file_path in project_dir.rglob(pattern):
            if file_path.is_file():
                try:
                    async with aiofiles.open(file_path, "r") as f:
                        content = await f.read()
                    if query.search(content):
                        return check.violation_message
                except Exception:
                    pass
        return None

    async def _check_config(self, check: ValidationCheck, project_dir: Path) -> str | None:
        """Check config file structure."""
        config_path = project_dir / "src" / "gameConfig.json"
        if not config_path.exists():
            return "gameConfig.json not found"

        try:
            async with aiofiles.open(config_path, "r") as f:
                import json
                config = json.loads(await f.read())

            # Check query against config
            import re
            if re.search(check.query, json.dumps(config)):
                return check.violation_message
        except Exception:
            pass

        return None

    async def _check_imports(self, check: ValidationCheck, project_dir: Path) -> str | None:
        """Check import consistency."""
        # Implementation: scan for broken imports
        return None

    async def _check_scene_registration(self, check: ValidationCheck, project_dir: Path) -> str | None:
        """Check that scenes are properly registered."""
        # Implementation: verify main.ts scene imports match scene files
        return None

    async def _check_assets(self, check: ValidationCheck, project_dir: Path) -> str | None:
        """Check asset consistency."""
        # Implementation: verify asset-pack.json references exist on disk
        return None
```

## 6.4 Runner

```python
# skills/debug_skill/runner.py
import asyncio
from pathlib import Path


class StageRunner:
    """
    Execute build, test, and dev stages.

    Parses errors from stdout/stderr into structured ParsedError objects.
    """

    STAGE_COMMANDS = {
        "build": ["npm", "run", "build"],
        "test": ["npm", "run", "test"],
        "dev": ["npm", "run", "dev"],
    }

    async def run(self, project_dir: Path, stage: str) -> RunResult:
        """Run a verification stage and parse results."""
        cmd = self.STAGE_COMMANDS.get(stage, ["npm", "run", stage])
        start = asyncio.get_event_loop().time()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=project_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=120,
            )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            errors = self._parse_errors(stdout_str, stderr_str, stage)

            return RunResult(
                stage=stage,
                success=proc.returncode == 0 and len(errors) == 0,
                exit_code=proc.returncode,
                stdout=stdout_str,
                stderr=stderr_str,
                errors=errors,
                duration_ms=int((asyncio.get_event_loop().time() - start) * 1000),
            )

        except asyncio.TimeoutError:
            return RunResult(
                stage=stage,
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Stage timed out after 120s",
                errors=[ParsedError(code="TIMEOUT", message="Stage timed out")],
                duration_ms=120000,
            )

    def _parse_errors(self, stdout: str, stderr: str, stage: str) -> list[ParsedError]:
        """Parse structured errors from stage output."""
        errors = []
        output = stdout + "\n" + stderr

        # TypeScript compilation errors
        ts_pattern = re.compile(
            r"([^\(]+)\((\d+),(\d+)\):\s*error\s+(TS\d+):\s*(.+)$",
            re.MULTILINE,
        )
        for match in ts_pattern.finditer(output):
            errors.append(ParsedError(
                code=match.group(4),
                message=match.group(5).strip(),
                file=match.group(1).strip(),
                line=int(match.group(2)),
                column=int(match.group(3)),
            ))

        # Module not found
        mod_pattern = re.compile(
            r"Cannot find module ['\"]([^'\"]+)['\"]",
            re.MULTILINE,
        )
        for match in mod_pattern.finditer(output):
            errors.append(ParsedError(
                code="MODULE_NOT_FOUND",
                message=f"Cannot find module: {match.group(1)}",
            ))

        # Reference errors (runtime)
        ref_pattern = re.compile(
            r"ReferenceError:\s*(.+)$",
            re.MULTILINE,
        )
        for match in ref_pattern.finditer(output):
            errors.append(ParsedError(
                code="ReferenceError",
                message=match.group(1).strip(),
            ))

        return errors
```

## 6.5 Diagnoser

```python
# skills/debug_skill/diagnoser.py
import re
from dataclasses import dataclass


@dataclass
class Diagnosis:
    """Result of diagnosing a single error."""
    error: ParsedError
    matched: bool = False
    matched_entry_id: str | None = None
    candidate_entry: DebugEntry | None = None
    root_cause: str = ""
    suggested_fix: str = ""


class ErrorDiagnoser:
    """
    Diagnose errors by matching against protocol entries.

    Strategy:
    1. Try to match error against existing protocol entries (fast)
    2. If no match, use LLM to diagnose (novel error)
    """

    def __init__(self, llm_client: BaseLlmClient):
        self.llm_client = llm_client

    async def diagnose(
        self,
        errors: list[ParsedError],
        protocol: DebugProtocol,
        project_dir: Path,
    ) -> list[Diagnosis]:
        """Diagnose all errors, returning a diagnosis for each."""
        return [await self._diagnose_one(e, protocol, project_dir) for e in errors]

    async def _diagnose_one(
        self,
        error: ParsedError,
        protocol: DebugProtocol,
        project_dir: Path,
    ) -> Diagnosis:
        """Diagnose a single error."""
        # Step 1: Try to match against existing entries
        matched_entry = self._match_error(error, protocol)
        if matched_entry:
            return Diagnosis(
                error=error,
                matched=True,
                matched_entry_id=matched_entry.id,
                root_cause=matched_entry.root_cause,
                suggested_fix=matched_entry.fix.get("patch", ""),
            )

        # Step 2: Try to match against protocol rules
        matched_rule = self._match_rule(error, protocol)
        if matched_rule:
            return Diagnosis(
                error=error,
                matched=False,
                root_cause=matched_rule.description,
                suggested_fix="See rule: " + matched_rule.id,
            )

        # Step 3: Novel error — use LLM to diagnose
        return await self._llm_diagnose(error, project_dir)

    def _match_error(self, error: ParsedError, protocol: DebugProtocol) -> DebugEntry | None:
        """
        Match an error against existing protocol entries.

        Matching criteria (in order of priority):
        1. Exact error code match
        2. Message pattern regex match
        3. File context match
        """
        candidates = []

        for entry in protocol.entries:
            sig = entry.signature
            score = 0

            # Error code match (strong signal)
            if sig.error_code == error.code:
                score += 10

            # Message pattern match
            try:
                pattern = re.compile(sig.message_pattern)
                if pattern.search(error.message):
                    score += 5
            except re.error:
                pass

            # File context match
            if sig.file_context and error.file:
                try:
                    ctx_pattern = re.compile(sig.file_context.replace("*", ".*"))
                    if ctx_pattern.search(error.file):
                        score += 3
                except re.error:
                    pass

            # Stage match
            if sig.stage in ("build", "test", "runtime"):
                score += 1

            if score >= 10:
                candidates.append((entry, score))

        # Return highest-scoring match
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]

        return None

    def _match_rule(self, error: ParsedError, protocol: DebugProtocol) -> ProtocolRule | None:
        """Match an error against protocol rules."""
        # Rules are more general — match by error code prefix or tags
        for rule in protocol.rules:
            for check in rule.checks:
                try:
                    if re.search(check.query, error.message):
                        return rule
                except re.error:
                    pass
        return None

    async def _llm_diagnose(self, error: ParsedError, project_dir: Path) -> Diagnosis:
        """Use LLM to diagnose a novel error."""
        prompt = f"""You are a debugging assistant. Analyze this error and suggest a fix.

## Error
- Code: {error.code}
- Message: {error.message}
- File: {error.file or "N/A"}
- Line: {error.line or "N/A"}

## Context
Project at: {project_dir}

Please provide:
1. Root cause (1-2 sentences)
2. Suggested fix (specific code change or command)
3. Type of fix: edit | shell | config | delete | create

Output as JSON:
{{
  "root_cause": "...",
  "suggested_fix": "...",
  "fix_type": "edit"
}}"""

        try:
            response = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                tools=None,
                stream=False,
                temperature=0.2,
                max_tokens=1000,
            )

            if response.content:
                import json
                text = response.content.strip()
                if text.startswith("```"):
                    text = re.sub(r"```json?\n?", "", text).replace("```", "").strip()
                parsed = json.loads(text)

                return Diagnosis(
                    error=error,
                    matched=False,
                    root_cause=parsed.get("root_cause", "Unknown"),
                    suggested_fix=parsed.get("suggested_fix", ""),
                )
        except Exception:
            pass

        return Diagnosis(
            error=error,
            matched=False,
            root_cause="Unable to diagnose — novel error pattern",
            suggested_fix="",
        )
```

## 6.6 Repairer

```python
# skills/debug_skill/repairer.py

class ErrorRepairer:
    """
    Apply fixes to projects.

    Supports five fix types:
    - edit: Search-and-replace or unified diff
    - shell: Execute a shell command
    - config: Modify a JSON config file
    - delete: Delete a file
    - create: Create a new file
    """

    def __init__(self, llm_client: BaseLlmClient):
        self.llm_client = llm_client

    async def repair(
        self,
        diagnosis: Diagnosis,
        error: ParsedError,
        project_dir: Path,
    ) -> RepairResult:
        """Apply a repair based on the diagnosis."""
        if diagnosis.matched and diagnosis.matched_entry_id:
            # Use the matched entry's fix
            return await self._apply_entry_fix(diagnosis, project_dir)
        else:
            # Generate a fix using LLM
            return await self._generate_and_apply_fix(diagnosis, error, project_dir)

    async def _apply_entry_fix(
        self,
        diagnosis: Diagnosis,
        project_dir: Path,
    ) -> RepairResult:
        """Apply a fix from a matched protocol entry."""
        fix = diagnosis.suggested_fix
        # Parse and apply the fix based on type
        # (Implementation depends on fix format)
        return RepairResult(
            applied=True,
            description=f"Applied fix from entry {diagnosis.matched_entry_id}",
            patch=fix,
            verify_stage="build",
        )

    async def _generate_and_apply_fix(
        self,
        diagnosis: Diagnosis,
        error: ParsedError,
        project_dir: Path,
    ) -> RepairResult:
        """Generate and apply a fix for a novel error."""
        prompt = f"""Fix this error in the project at {project_dir}.

## Error
- Code: {error.code}
- Message: {error.message}
- File: {error.file or "N/A"}
- Line: {error.line or "N/A"}

## Diagnosis
- Root cause: {diagnosis.root_cause}

## Your Task
Generate a specific fix. Output as:
{{
  "fix_type": "edit" | "shell" | "config" | "delete" | "create",
  "description": "What the fix does",
  "file_path": "path relative to project root (for edit/create/delete)",
  "patch": "The actual fix content"
}}

For 'edit': patch should be a search/replace pair:
OLD:
...
NEW:
...

For 'shell': patch is the command to run.
For 'config': patch is the JSON key path and new value.
For 'delete': patch is the file path.
For 'create': patch is the full file content."""

        try:
            response = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                tools=None,
                stream=False,
                temperature=0.2,
                max_tokens=2000,
            )

            if response.content:
                import json
                text = response.content.strip()
                if text.startswith("```"):
                    text = re.sub(r"```json?\n?", "", text).replace("```", "").strip()
                parsed = json.loads(text)

                fix_type = parsed.get("fix_type", "edit")
                file_path = parsed.get("file_path", "")
                patch = parsed.get("patch", "")

                applied = await self._apply_fix(
                    fix_type, project_dir / file_path, patch,
                )

                return RepairResult(
                    applied=applied,
                    description=parsed.get("description", "No description"),
                    patch=patch,
                    verify_stage="build",
                )
        except Exception as e:
            return RepairResult(
                applied=False,
                description=f"Failed to generate fix: {e}",
                patch="",
                verify_stage="build",
            )

        return RepairResult(
            applied=False,
            description="No fix generated",
            patch="",
            verify_stage="build",
        )

    async def _apply_fix(
        self,
        fix_type: str,
        file_path: Path,
        patch: str,
    ) -> bool:
        """Apply a fix of the given type."""
        if fix_type == "edit":
            return await self._apply_edit(file_path, patch)
        elif fix_type == "shell":
            return await self._apply_shell(patch)
        elif fix_type == "config":
            return await self._apply_config(file_path, patch)
        elif fix_type == "delete":
            return await self._apply_delete(file_path)
        elif fix_type == "create":
            return await self._apply_create(file_path, patch)
        return False

    async def _apply_edit(self, file_path: Path, patch: str) -> bool:
        """Apply a search/replace edit."""
        if not file_path.exists():
            return False

        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()

        # Parse search/replace
        if "OLD:" in patch and "NEW:" in patch:
            parts = patch.split("NEW:")
            old = parts[0].replace("OLD:", "").strip()
            new = parts[1].strip() if len(parts) > 1 else ""

            if old in content:
                content = content.replace(old, new, 1)
                async with aiofiles.open(file_path, "w") as f:
                    await f.write(content)
                return True

        return False

    async def _apply_shell(self, command: str) -> bool:
        """Execute a shell command."""
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0

    async def _apply_config(self, file_path: Path, patch: str) -> bool:
        """Apply a config modification."""
        # Implementation: parse JSON patch and apply
        return False

    async def _apply_delete(self, file_path: Path) -> bool:
        """Delete a file."""
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    async def _apply_create(self, file_path: Path, content: str) -> bool:
        """Create a new file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, "w") as f:
            await f.write(content)
        return True
```

## 6.7 Recorder

```python
# skills/debug_skill/recorder.py
import uuid
from datetime import datetime


class OutcomeRecorder:
    """
    Record the outcome of a diagnosis + repair into the protocol.

    Creates new entries for novel failures, increments counters for matched entries.
    """

    def record(
        self,
        protocol: DebugProtocol,
        diagnosis: Diagnosis,
        repair: RepairResult,
        project_dir: Path,
        verified: bool,
    ) -> dict:
        """
        Record the outcome of a repair attempt.

        Returns:
            dict with 'entry_id' (new or matched) and 'action' taken
        """
        if diagnosis.matched and diagnosis.matched_entry_id:
            # Matched existing entry — increment occurrence
            for entry in protocol.entries:
                if entry.id == diagnosis.matched_entry_id:
                    entry.occurrences += 1
                    entry.last_matched_at = datetime.utcnow().isoformat()
                    if str(project_dir) not in entry.contributing_projects:
                        entry.contributing_projects.append(str(project_dir))
                    return {"entry_id": entry.id, "action": "matched"}

        elif verified:
            # Novel, verified fix — create new entry
            entry_id = f"entry-{diagnosis.error.code}-{uuid.uuid4().hex[:8]}"
            new_entry = DebugEntry(
                id=entry_id,
                kind="reactive",
                signature=FailureSignature(
                    stage="build",  # Would be determined from context
                    error_code=diagnosis.error.code,
                    message_pattern=self._generalize_message(diagnosis.error.message),
                ),
                root_cause=diagnosis.root_cause,
                tags=[diagnosis.error.code.split("0")[0] if diagnosis.error.code.startswith("TS") else "runtime"],
                fix={
                    "type": "edit",  # Simplified
                    "description": repair.description,
                    "patch": repair.patch,
                },
                occurrences=1,
                contributing_projects=[str(project_dir)],
                created_at=datetime.utcnow().isoformat(),
                last_matched_at=datetime.utcnow().isoformat(),
            )
            protocol.entries.append(new_entry)
            return {"entry_id": entry_id, "action": "created"}

        return {"entry_id": None, "action": "none"}

    def _generalize_message(self, message: str) -> str:
        """
        Generalize an error message into a regex pattern.

        Replaces concrete names with capture groups:
        "Property 'foo' does not exist on type 'Bar'"
        -> "Property '(.+)' does not exist on type '(.+)'"
        """
        # Replace quoted strings with capture groups
        result = re.sub(r"'([^']+)'", r"'(.+)'", message)
        result = re.sub(r'"([^"]+)"', r'"(.+)"', result)
        # Replace specific identifiers
        result = re.sub(r"\b[A-Z][a-zA-Z0-9_]*\b", r"\\w+", result)
        return result
```

## 6.8 Protocol Manager

```python
# skills/debug_skill/protocol_manager.py
import json
from pathlib import Path


class ProtocolManager:
    """
    Load, save, initialize, and version the debug protocol.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.protocol_path = output_dir / "protocol.json"
        self.seed_protocol_path = output_dir / "seed-protocol" / "protocol.json"

    async def initialize(self) -> DebugProtocol:
        """Create a fresh protocol, optionally seeded from P0."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Try to load seed protocol
        entries = []
        rules = []
        if self.seed_protocol_path.exists():
            try:
                async with aiofiles.open(self.seed_protocol_path, "r") as f:
                    seed = json.loads(await f.read())
                    entries = [DebugEntry(**e) for e in seed.get("entries", [])]
                    rules = [ProtocolRule(**r) for r in seed.get("rules", [])]
            except Exception:
                pass

        protocol = DebugProtocol(
            version=0,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            seed_protocol_path=str(self.seed_protocol_path),
            entries=entries,
            rules=rules,
            evolution_log=[],
        )
        await self.save(protocol)
        return protocol

    async def load(self) -> DebugProtocol | None:
        """Load protocol from disk."""
        if not self.protocol_path.exists():
            return None

        async with aiofiles.open(self.protocol_path, "r") as f:
            raw = await f.read()

        data = json.loads(raw)
        return DebugProtocol(**data)

    async def load_or_init(self) -> DebugProtocol:
        """Load existing or initialize new protocol."""
        existing = await self.load()
        if existing:
            return existing
        return await self.initialize()

    async def save(self, protocol: DebugProtocol) -> None:
        """Save protocol to disk."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self.protocol_path, "w") as f:
            await f.write(json.dumps(protocol.model_dump(), indent=2))

    async def bump_version(self, protocol: DebugProtocol) -> None:
        """Bump protocol version without other changes."""
        protocol.version += 1
        protocol.updated_at = datetime.utcnow().isoformat()
        await self.save(protocol)
```

## 6.9 Generalizer

```python
# skills/debug_skill/generalizer.py

class RuleGeneralizer:
    """
    Generalize repeated debug entries into reusable protocol rules.

    When the same error pattern is seen multiple times, derive a general rule
    that can be applied proactively (pre-execution validation).
    """

    MIN_OCCURRENCES = 3  # Minimum occurrences to generalize

    def __init__(self, llm_client: BaseLlmClient):
        self.llm_client = llm_client

    async def generalize(
        self,
        trace: DebugTrace,
        protocol: DebugProtocol,
    ) -> int:
        """
        Generalize repeated entries into rules.

        Returns:
            Number of new rules generated
        """
        new_rules = 0

        # Find entries with sufficient occurrences
        candidates = [
            e for e in protocol.entries
            if e.occurrences >= self.MIN_OCCURRENCES
            and not e.generalized_from
        ]

        # Group by error code
        by_code: dict[str, list[DebugEntry]] = {}
        for entry in candidates:
            by_code.setdefault(entry.signature.error_code, []).append(entry)

        for code, entries in by_code.items():
            if len(entries) < self.MIN_OCCURRENCES:
                continue

            # Check if a rule already exists for this code
            existing = next((r for r in protocol.rules if code in r.name), None)
            if existing:
                continue

            # Generate a rule
            rule = await self._generate_rule(entries, code)
            if rule:
                protocol.rules.append(rule)
                new_rules += 1

                # Mark entries as generalized
                entry_ids = [e.id for e in entries]
                for e in entries:
                    e.generalized_from = entry_ids

        if new_rules > 0:
            protocol.version += 1
            protocol.updated_at = datetime.utcnow().isoformat()

        return new_rules

    async def _generate_rule(
        self,
        entries: list[DebugEntry],
        error_code: str,
    ) -> ProtocolRule | None:
        """Generate a protocol rule from repeated entries."""
        prompt = f"""You are analyzing repeated error patterns to create a reusable validation rule.

## Error Code
{error_code}

## Entries ({len(entries)} occurrences)
"""
        for e in entries[:5]:
            prompt += f"""
- Entry: {e.id}
- Root cause: {e.root_cause}
- Fix: {e.fix.get("description", "N/A")}
- Tags: {', '.join(e.tags)}
"""

        prompt += """
## Your Task
Generate a proactive validation rule that would CATCH this error before build.

Output as JSON:
{
  "name": "Human-readable rule name",
  "description": "What this rule checks",
  "preconditions": ["Condition for applying this rule"],
  "action": "flag" | "fix" | "block",
  "checks": [
    {
      "target": "file" | "config" | "imports" | "scene_registration" | "assets",
      "filePattern": "optional glob pattern",
      "query": "regex or structured query",
      "violationMessage": "What violation looks like"
    }
  ]
}
"""

        try:
            response = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                tools=None,
                stream=False,
                temperature=0.2,
                max_tokens=2000,
            )

            if response.content:
                import json
                text = response.content.strip()
                if text.startswith("```"):
                    text = re.sub(r"```json?\n?", "", text).replace("```", "").strip()
                parsed = json.loads(text)

                return ProtocolRule(
                    id=f"rule-{error_code}-{uuid.uuid4().hex[:8]}",
                    name=parsed["name"],
                    description=parsed["description"],
                    preconditions=parsed.get("preconditions", []),
                    action=parsed.get("action", "flag"),
                    checks=[ValidationCheck(**c) for c in parsed.get("checks", [])],
                    derived_from=[e.id for e in entries],
                    created_at=datetime.utcnow().isoformat(),
                    updated_at=datetime.utcnow().isoformat(),
                )
        except Exception:
            pass

        return None
```
