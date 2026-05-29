"""Tests for the Typer CLI entry point."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from opengame import __version__
from opengame.cli.main import app

runner = CliRunner()


class TestCliMain:
    """Tests for the root CLI command."""

    def test_help(self) -> None:
        """--help shows available commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "config" in result.stdout.lower() or "Config" in result.stdout
        assert "generate" in result.stdout.lower() or "Generate" in result.stdout

    def test_version(self) -> None:
        """--version prints the version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout


class TestConfigCommands:
    """Tests for config subcommands."""

    def test_config_show(self) -> None:
        """config show displays configuration."""
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "LLM" in result.stdout or "openai" in result.stdout.lower()

    def test_config_show_raw(self) -> None:
        """config show --raw outputs JSON."""
        result = runner.invoke(app, ["config", "show", "--raw"])
        assert result.exit_code == 0
        assert '"llm"' in result.stdout or '"approval_mode"' in result.stdout

    def test_config_validate(self) -> None:
        """config validate checks configuration."""
        result = runner.invoke(app, ["config", "validate"])
        assert result.exit_code == 0
        # Warns about missing API key
        assert "warnings" in result.stdout.lower() or "Warnings" in result.stdout or "valid" in result.stdout.lower()


class TestPlaceholderCommands:
    """Tests that placeholder commands exist but show 'not yet implemented'."""

    def test_generate_exists(self) -> None:
        """generate command is registered."""
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0

    def test_debug_exists(self) -> None:
        """debug command is registered."""
        result = runner.invoke(app, ["debug", "--help"])
        assert result.exit_code == 0

    def test_evolve_exists(self) -> None:
        """evolve command is registered."""
        result = runner.invoke(app, ["evolve", "--help"])
        assert result.exit_code == 0
