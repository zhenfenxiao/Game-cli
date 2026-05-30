"""StageRunner — executes build/test/dev commands and parses errors.

Runs npm commands via asyncio subprocess and extracts structured
error information from the output.
"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

from opengame.skills.debug_skill.types import ParsedError, RunResult
from opengame.utils.errors import ToolError

# Default timeout for stage execution (seconds)
DEFAULT_TIMEOUT = 120

# Regex patterns for parsing TypeScript/Node errors
TS_ERROR_RE = re.compile(
    r"(?P<file>[^(]+)\((?P<line>\d+),(?P<col>\d+)\):\s*"
    r"error\s+(?P<code>TS\d+):\s*(?P<message>.+)",
    re.MULTILINE,
)
MODULE_NOT_FOUND_RE = re.compile(
    r"Cannot find module\s+['\"](?P<module>[^'\"]+)['\"]",
    re.MULTILINE,
)
REFERENCE_ERROR_RE = re.compile(
    r"(?P<type>ReferenceError|TypeError|SyntaxError):\s*(?P<message>.+)",
    re.MULTILINE,
)
GENERIC_ERROR_RE = re.compile(
    r"(?P<file>[^:\s]+):(?P<line>\d+):(?P<col>\d+):\s*"
    r"(?:error\s+)?(?P<message>.+)",
    re.MULTILINE,
)


class StageRunner:
    """Execute a build, test, or dev stage and parse the output.

    Runs npm commands asynchronously and extracts structured
    ParsedError objects from stdout/stderr.
    """

    def __init__(self) -> None:
        pass

    async def run(self, project_dir: str | Path, stage: str) -> RunResult:
        """Execute a stage in the given project directory.

        Args:
            project_dir: Path to the project.
            stage: Stage to run: "build", "test", or "dev".

        Returns:
            RunResult with success status, output, and parsed errors.
        """
        root = Path(project_dir).resolve()

        if stage == "build":
            command = "npm run build"
        elif stage == "test":
            command = "npm test"
        elif stage == "dev":
            command = "npm run dev"
        else:
            return RunResult(
                stage=stage,  # type: ignore[arg-type]
                success=False,
                stderr=f"Unknown stage: {stage}",
            )

        start_time = time.monotonic()

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=root,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=DEFAULT_TIMEOUT,
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            exit_code = process.returncode or 0

        except asyncio.TimeoutError:
            return RunResult(
                stage=stage,  # type: ignore[arg-type]
                success=False,
                exit_code=-1,
                stderr=f"Stage '{stage}' timed out after {DEFAULT_TIMEOUT}s",
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )
        except FileNotFoundError:
            return RunResult(
                stage=stage,  # type: ignore[arg-type]
                success=False,
                exit_code=-1,
                stderr=f"npm not found. Is Node.js installed?",
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        success = exit_code == 0

        # Parse errors from combined output
        combined = stdout + "\n" + stderr
        errors = self._parse_errors(combined)

        return RunResult(
            stage=stage,  # type: ignore[arg-type]
            success=success,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            errors=errors,
            duration_ms=elapsed_ms,
        )

    def _parse_errors(self, output: str) -> list[ParsedError]:
        """Parse structured error information from stage output.

        Applies multiple regex patterns to extract TypeScript
        compilation errors, module resolution failures, and
        runtime errors.

        Args:
            output: Combined stdout and stderr from stage execution.

        Returns:
            List of ParsedError objects.
        """
        errors: list[ParsedError] = []
        seen: set[str] = set()  # Deduplicate by error code + message

        # Pattern 1: TypeScript errors (TS1234: message)
        for match in TS_ERROR_RE.finditer(output):
            msg = match.group("message").strip()
            code = match.group("code")
            key = f"{code}:{msg}"
            if key not in seen:
                seen.add(key)
                errors.append(ParsedError(
                    code=code,
                    message=msg,
                    file=match.group("file").strip(),
                    line=int(match.group("line")),
                    column=int(match.group("col")),
                ))

        # Pattern 2: Module not found
        for match in MODULE_NOT_FOUND_RE.finditer(output):
            msg = f"Cannot find module '{match.group('module')}'"
            if msg not in seen:
                seen.add(msg)
                errors.append(ParsedError(
                    code="MODULE_NOT_FOUND",
                    message=msg,
                ))

        # Pattern 3: Runtime errors
        for match in REFERENCE_ERROR_RE.finditer(output):
            msg = match.group("message").strip()
            error_type = match.group("type")
            key = f"{error_type}:{msg}"
            if key not in seen:
                seen.add(key)
                errors.append(ParsedError(
                    code=error_type,
                    message=msg,
                ))

        # If no structured errors found, try generic pattern
        if not errors:
            for match in GENERIC_ERROR_RE.finditer(output):
                msg = match.group("message").strip()
                if "error" in msg.lower() and msg not in seen:
                    seen.add(msg)
                    errors.append(ParsedError(
                        code="GENERIC",
                        message=msg,
                        file=match.group("file").strip(),
                        line=int(match.group("line")),
                        column=int(match.group("col")),
                    ))

        return errors
