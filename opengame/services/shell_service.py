"""Async shell execution service.

Provides secure subprocess execution with timeouts and a read-only command checker.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opengame.utils.errors import ToolError


@dataclass
class ShellResult:
    """Result of a shell command execution."""

    exit_code: int
    stdout: str
    stderr: str


class ShellReadOnlyChecker:
    """Checks whether a shell command is read-only (safe to auto-run)."""

    # Commands that are always safe (read-only)
    READ_ONLY_COMMANDS: set[str] = {
        "ls", "cat", "head", "tail", "grep", "find", "wc",
        "sort", "uniq", "cut", "tr", "awk", "sed", "file",
        "stat", "du", "df", "echo", "pwd", "which", "type",
        "env", "printenv", "uname", "hostname", "whoami",
        "date", "man", "info", "less", "more", "od", "xxd",
        "pgrep", "pidof", "lsof", "ps", "top", "free",
        "uptime", "git", "npm", "node", "npx", "python",
        "python3", "pip", "pip3", "poetry", "hatch",
        "tree", "realpath", "readlink", "basename", "dirname",
        "tar", "gzip", "bzip2", "zipinfo", "unzip",
        "test", "[", "expr", "true", "false",
    }

    # Patterns that indicate destructive operations
    DANGEROUS_PATTERNS: list[re.Pattern] = [
        re.compile(r"\brm\b"),           # remove
        re.compile(r"\bmv\b"),            # move/rename
        re.compile(r"\bcp\b"),            # copy (can overwrite)
        re.compile(r"\bdd\b"),            # disk destroyer
        re.compile(r"\bmkfs\b"),          # make filesystem
        re.compile(r"\bfdisk\b"),         # partition tool
        re.compile(r"\bchmod\b"),         # change permissions
        re.compile(r"\bchown\b"),         # change owner
        re.compile(r"\bkill\b"),          # kill processes
        re.compile(r"\bpkill\b"),         # kill processes
        re.compile(r"\breboot\b"),        # reboot
        re.compile(r"\bshutdown\b"),      # shutdown
        re.compile(r"\bformat\b"),        # format disk
        re.compile(r"\bparted\b"),        # partition editor
        re.compile(r">\s*/dev/"),         # write to device
        re.compile(r"\bsudo\b"),          # superuser
        re.compile(r"\bsu\b"),            # switch user
        re.compile(r"\bpasswd\b"),        # change password
        re.compile(r"\bwget\b.*-O"),      # wget output to file
        re.compile(r"\bcurl\b.*-o"),      # curl output to file
        re.compile(r">\s*\S"),            # redirect to file
        re.compile(r">>\s*\S"),           # append to file
        re.compile(r"\btee\b"),           # tee writes to files
        re.compile(r"\bgit\s+push\b"),    # git push
        re.compile(r"\bgit\s+reset\b"),   # git reset
        re.compile(r"\bgit\s+clean\b"),   # git clean
        re.compile(r"\bnpm\s+publish\b"), # npm publish
        re.compile(r"\bpip\s+install\b"), # pip install
    ]

    def is_read_only(self, command: str) -> bool:
        """Check if a command is read-only (safe to auto-execute).

        Args:
            command: The shell command string.

        Returns:
            True if the command appears to be read-only.
        """
        if self.is_dangerous(command):
            return False

        # Extract the base command (first word before any flag or pipe)
        base = command.strip().split()[0] if command.strip() else ""
        base = os.path.basename(base)  # Handle /usr/bin/ls → ls

        return base in self.READ_ONLY_COMMANDS

    def is_dangerous(self, command: str) -> bool:
        """Check if a command appears destructive.

        Args:
            command: The shell command string.

        Returns:
            True if the command matches dangerous patterns.
        """
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.search(command):
                return True
        return False


async def run_command(
    command: str,
    timeout: int = 120,
    work_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run a shell command asynchronously with a timeout.

    Args:
        command: Shell command to execute.
        timeout: Maximum execution time in seconds (default 120s).
        work_dir: Working directory for the command.

    Returns:
        Dict with exit_code, stdout, and stderr.

    Raises:
        ToolError: If the command times out or fails to execute.
    """
    cwd = Path(work_dir) if work_dir else None

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise ToolError(
                f"Command timed out after {timeout}s",
                context={"command": command, "timeout": timeout},
                recoverable=True,
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        return {
            "exit_code": process.returncode or 0,
            "stdout": stdout,
            "stderr": stderr,
        }

    except ToolError:
        raise
    except FileNotFoundError:
        raise ToolError(
            f"Command not found: {command.split()[0]}",
            context={"command": command},
            recoverable=True,
        )
    except Exception as e:
        raise ToolError(
            f"Failed to execute command: {e}",
            context={"command": command, "error": str(e)},
            recoverable=True,
        )
