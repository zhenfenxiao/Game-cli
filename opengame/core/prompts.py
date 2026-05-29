"""Prompt assembler — loads system prompts and injects context.

Loads base prompt files from the prompts/ directory and provides
context injection for dynamic prompt assembly.
"""

from __future__ import annotations

from pathlib import Path


class PromptAssembler:
    """Loads and assembles system prompts for the agent.

    Supports loading prompts from the package's prompts/ directory
    and injecting dynamic context (project info, game state, etc.).

    Usage:
        assembler = PromptAssembler()
        system_prompt = assembler.assemble_game_prompt(
            archetype="platformer",
            extra_context={"game_name": "My Game"},
        )
    """

    # Default prompt directory relative to the package
    PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self.prompts_dir = prompts_dir or self.PROMPTS_DIR

    def assemble_game_prompt(
        self,
        prompt_type: str = "default",
        extra_context: dict[str, str] | None = None,
    ) -> str:
        """Assemble a system prompt with optional context injection.

        Args:
            prompt_type: Which prompt to load ('default' or 'custom').
            extra_context: Key-value pairs to inject into the prompt template.

        Returns:
            The assembled system prompt string.
        """
        prompt = self._load_prompt(prompt_type)
        if extra_context:
            prompt = self._inject_context(prompt, extra_context)
        return prompt

    def _load_prompt(self, name: str) -> str:
        """Load a prompt file from the prompts directory.

        Args:
            name: Prompt name without extension (e.g., 'default', 'custom').

        Returns:
            Prompt content as a string. Returns built-in fallback if file not found.
        """
        prompt_path = self.prompts_dir / f"{name}.md"

        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        # Fallback built-in prompts
        return self._get_builtin_prompt(name)

    @staticmethod
    def _inject_context(prompt: str, context: dict[str, str]) -> str:
        """Inject context variables into a prompt template.

        Replaces {{key}} placeholders with values from the context dict.

        Args:
            prompt: Prompt template with {{key}} placeholders.
            context: Key-value pairs to inject.

        Returns:
            Prompt with placeholders replaced.
        """
        result = prompt
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, value)
        return result

    @staticmethod
    def _get_builtin_prompt(name: str) -> str:
        """Get a built-in fallback prompt when files are not available.

        These are minimal prompts; the full prompts are defined in the
        PRD appendix and will be packaged with the distribution.
        """
        if name == "custom":
            return (
                "You are an expert game developer. Your task is to create a complete, "
                "playable web game using Phaser 3, TypeScript, and Vite. Follow the "
                "6-phase game development workflow: classify, scaffold, generate GDD, "
                "create assets, configure, and implement. Always think step by step "
                "and use the available tools to build the game iteratively."
            )
        # default
        return (
            "You are an AI agent capable of using tools to accomplish tasks. "
            "Your goal is to help the user build and debug software projects. "
            "Use the available tools to read files, write code, execute commands, "
            "and search for information. Always think step by step."
        )
