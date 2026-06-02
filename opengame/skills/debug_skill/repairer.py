"""ErrorRepairer — applies fixes to diagnosed errors.

5 fix types: edit (search/replace), shell (run command),
create (new file), delete (remove file), config (JSON patch stub).

Uses fs_service and shell_service from Phase 1 for execution.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import aiofiles

from opengame.core.llm_client import BaseLlmClient
from opengame.services import shell_service as shell_svc
from opengame.skills.debug_skill.types import ParsedError, RepairResult


class ErrorRepairer:
    """Apply fixes to diagnosed errors.

    5 fix types:
    - edit: Search/replace in source files
    - shell: Run shell commands (npm install, etc.)
    - create: Create new files
    - delete: Remove files
    - config: JSON patch (stub — returns False)
    """

    def __init__(self, llm_client: BaseLlmClient) -> None:
        self.llm_client = llm_client

    async def repair(
        self,
        diagnosis,  # Diagnosis from diagnoser
        error: ParsedError,
        project_dir: str | Path,
    ) -> RepairResult:
        """Apply a fix for a diagnosed error.

        Args:
            diagnosis: The Diagnosis from ErrorDiagnoser.
            error: The parsed error to fix.
            project_dir: Path to the game project.

        Returns:
            RepairResult describing what was done.
        """
        root = Path(project_dir).resolve()

        # If we have a known fix from protocol entry, apply it
        if diagnosis.matched and diagnosis.candidate_entry:
            return await self._apply_entry_fix(diagnosis.candidate_entry.fix, error, root)

        # Otherwise, generate and apply a fix via LLM
        return await self._generate_and_apply_fix(diagnosis, error, root)

    # --- Entry-based fix ---

    async def _apply_entry_fix(
        self, fix: dict, error: ParsedError, root: Path,
    ) -> RepairResult:
        """Apply a fix from a known protocol entry."""
        fix_type = fix.get("fix_type", "edit")
        description = fix.get("description", "Apply known fix")
        patch = fix.get("patch", "")
        file_path = fix.get("file_path", "")

        if fix_type == "edit":
            return await self._apply_edit(root, file_path, patch, description)
        elif fix_type == "shell":
            return await self._apply_shell(root, patch, description)
        elif fix_type == "create":
            return await self._apply_create(root, file_path, patch, description)
        elif fix_type == "delete":
            return await self._apply_delete(root, file_path, description)
        elif fix_type == "config":
            return await self._apply_config(root, patch, description)

        return RepairResult(applied=False, description=f"Unknown fix type: {fix_type}")

    # --- LLM-generated fix ---

    async def _generate_and_apply_fix(
        self, diagnosis, error: ParsedError, root: Path,
    ) -> RepairResult:
        """Generate a fix via LLM and apply it."""
        # Parse suggested_fix from diagnosis
        try:
            fix_data = json.loads(diagnosis.suggested_fix) if diagnosis.suggested_fix else {}
        except json.JSONDecodeError:
            fix_data = {}

        fix_type = fix_data.get("fix_type", "edit")

        if fix_type == "edit":
            # Need more specific edit instructions — ask LLM
            prompt = f"""You are a TypeScript code fixer. Generate an exact edit to fix this error.

Error: {error.code}: {error.message}
File: {error.file or 'unknown'}
Root cause: {diagnosis.root_cause}

Output format:
--- FILE ---
<relative file path>
--- OLD ---
<exact string to find>
--- NEW ---
<replacement string>"""

            try:
                response = await self.llm_client.generate(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=2000,
                )
                content = response.content or ""
            except Exception as e:
                return RepairResult(
                    applied=False,
                    description=f"LLM call failed for repair of {error.code}: {e}",
                )

            # Parse the response
            file_match = re.search(r"--- FILE ---\s*\n(.*?)\n", content, re.DOTALL)
            old_match = re.search(r"--- OLD ---\s*\n(.*?)\n--- NEW ---", content, re.DOTALL)
            new_match = re.search(r"--- NEW ---\s*\n(.*?)$", content, re.DOTALL)

            if old_match and new_match:
                file_path = file_match.group(1).strip() if file_match else (error.file or "")
                old_str = old_match.group(1).strip()
                new_str = new_match.group(1).strip()
                return await self._apply_edit(root, file_path, f"--- OLD ---\n{old_str}\n--- NEW ---\n{new_str}", str(fix_data.get("description", "LLM-generated fix")))

            return RepairResult(applied=False, description="Could not parse LLM fix response")

        elif fix_type == "shell":
            command = fix_data.get("patch", "npm install")
            return await self._apply_shell(root, command, str(fix_data.get("description", "Run shell command")))

        elif fix_type == "create":
            file_path = fix_data.get("file_path", "")
            content = fix_data.get("patch", "")
            return await self._apply_create(root, file_path, content, str(fix_data.get("description", "Create file")))

        elif fix_type == "delete":
            file_path = fix_data.get("file_path", "")
            return await self._apply_delete(root, file_path, str(fix_data.get("description", "Delete file")))

        return RepairResult(applied=False, description=f"Unknown fix type: {fix_type}")

    # --- Fix applicators ---

    @staticmethod
    async def _apply_edit(root: Path, file_path: str, patch: str, description: str) -> RepairResult:
        """Apply a search/replace edit."""
        target = root / file_path if file_path else None
        if not target or not target.exists():
            return RepairResult(applied=False, description=f"File not found: {file_path}")

        # Parse OLD/NEW from patch
        old_match = re.search(r"--- OLD ---\s*\n(.*?)\n--- NEW ---", patch, re.DOTALL)
        new_match = re.search(r"--- NEW ---\s*\n(.*?)$", patch, re.DOTALL)

        if not old_match:
            return RepairResult(applied=False, description="Could not parse OLD block from patch")

        old_str = old_match.group(1)
        new_str = new_match.group(1) if new_match else ""

        try:
            async with aiofiles.open(target, "r", encoding="utf-8") as f:
                content = await f.read()

            if old_str not in content:
                return RepairResult(applied=False, description=f"OLD string not found in {file_path}")

            new_content = content.replace(old_str, new_str, 1)
            async with aiofiles.open(target, "w", encoding="utf-8") as f:
                await f.write(new_content)

            return RepairResult(applied=True, description=description, patch=patch)
        except Exception as e:
            return RepairResult(applied=False, description=str(e))

    @staticmethod
    async def _apply_shell(root: Path, command: str, description: str) -> RepairResult:
        """Run a shell command as a fix."""
        try:
            result = await shell_svc.run_command(command, work_dir=root)
            return RepairResult(
                applied=result["exit_code"] == 0,
                description=description,
                patch=command,
            )
        except Exception as e:
            return RepairResult(applied=False, description=str(e))

    @staticmethod
    async def _apply_create(root: Path, file_path: str, content: str, description: str) -> RepairResult:
        """Create a new file."""
        target = root / file_path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(target, "w", encoding="utf-8") as f:
                await f.write(content)
            return RepairResult(applied=True, description=description, patch=content[:200])
        except Exception as e:
            return RepairResult(applied=False, description=str(e))

    @staticmethod
    async def _apply_delete(root: Path, file_path: str, description: str) -> RepairResult:
        """Delete a file."""
        target = root / file_path
        try:
            if target.exists():
                target.unlink()
                return RepairResult(applied=True, description=description)
            return RepairResult(applied=False, description=f"File not found: {file_path}")
        except Exception as e:
            return RepairResult(applied=False, description=str(e))

    @staticmethod
    async def _apply_config(root: Path, patch: str, description: str) -> RepairResult:
        """Apply a JSON config patch (stub)."""
        return RepairResult(applied=False, description="Config patches not yet implemented")
