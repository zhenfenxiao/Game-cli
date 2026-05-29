"""Tests for the PromptAssembler."""

from __future__ import annotations

import tempfile
from pathlib import Path

from opengame.core.prompts import PromptAssembler


class TestPromptAssembler:
    """Tests for prompt loading and context injection."""

    def test_default_prompt(self) -> None:
        """Default prompt is loaded."""
        assembler = PromptAssembler()
        prompt = assembler.assemble_game_prompt("default")
        assert len(prompt) > 0
        assert "AI agent" in prompt or "tools" in prompt.lower()

    def test_custom_prompt(self) -> None:
        """Custom game prompt is loaded."""
        assembler = PromptAssembler()
        prompt = assembler.assemble_game_prompt("custom")
        assert len(prompt) > 0
        assert "game developer" in prompt.lower() or "Phaser" in prompt

    def test_unknown_prompt_falls_back(self) -> None:
        """Unknown prompt type returns built-in default."""
        assembler = PromptAssembler()
        prompt = assembler.assemble_game_prompt("nonexistent")
        # Should not raise, returns fallback
        assert len(prompt) > 0

    def test_context_injection(self) -> None:
        """Context variables are injected into prompts."""
        assembler = PromptAssembler()
        prompt = assembler.assemble_game_prompt(
            "custom",
            extra_context={"archetype": "platformer"},
        )
        # Default built-in doesn't have {{archetype}} placeholder,
        # but the injection should not fail
        assert len(prompt) > 0

    def test_load_from_custom_directory(self, tmp_path: Path) -> None:
        """Prompts can be loaded from a custom directory."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "custom.md").write_text("Custom prompt from file")

        assembler = PromptAssembler(prompts_dir=prompts_dir)
        prompt = assembler.assemble_game_prompt("custom")
        assert prompt == "Custom prompt from file"


class TestInjectContext:
    """Tests for the _inject_context static method."""

    def test_replaces_placeholders(self) -> None:
        """{{key}} placeholders are replaced with values."""
        template = "Hello {{name}}, welcome to {{project}}!"
        result = PromptAssembler._inject_context(
            template,
            {"name": "Alice", "project": "OpenGame"},
        )
        assert result == "Hello Alice, welcome to OpenGame!"

    def test_missing_context_left_as_is(self) -> None:
        """Placeholders with no matching context key are left unchanged."""
        template = "Hello {{name}}!"
        result = PromptAssembler._inject_context(template, {})
        assert result == "Hello {{name}}!"
