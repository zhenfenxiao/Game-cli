"""Generate command — create a game from a natural language prompt.

Wires the full 6-phase GameSkill pipeline to the CLI.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from opengame import __version__
from opengame.cli.config_loader import ConfigLoader
from opengame.core.openai_client import OpenAiClient
from opengame.services.asset_service import AssetService
from opengame.skills.debug_skill import DebugSkill, ProtocolManager
from opengame.skills.game_skill import GameSkill
from opengame.skills.template_skill import TemplateSkill
from opengame.skills.template_skill.library_manager import LibraryManager
from opengame.tools.factory import create_tool_registry

app = typer.Typer(help="Generate a game from a natural language prompt")
console = Console()


@app.callback(invoke_without_command=True)
def generate(
    prompt: str = typer.Option(
        ...,
        "--prompt",
        "-p",
        help="Natural language game description",
    ),
    output_dir: Path = typer.Option(
        Path("./output"),
        "--output-dir",
        "-o",
        help="Output directory for the generated game",
    ),
    approval_mode: str | None = typer.Option(
        None,
        "--approval",
        help="Approval mode: ask, auto-edit, or yolo (default: from config)",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model to use (default: from config or env)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose output",
    ),
) -> None:
    """Generate a complete web game from a natural language prompt."""
    # Load config (only apply CLI overrides if user explicitly passed them)
    loader = ConfigLoader()
    if model is not None:
        loader.set_cli_override("llm.model", model)
    if approval_mode is not None:
        loader.set_cli_override("approval_mode", approval_mode)
    config = loader.load(load_dotenv=True)

    # Initialize LLM client
    llm_client = OpenAiClient(
        model=config.llm.model,
        base_url=config.llm.base_url,
        api_key=config.llm.api_key,
        timeout=config.llm.timeout,
    )

    # Initialize skills
    library_manager = LibraryManager(config.game_skill.library_output_dir)
    template_skill = TemplateSkill(llm_client, library_manager)

    protocol_manager = ProtocolManager(config.game_skill.protocol_output_dir)
    debug_skill = DebugSkill(
        llm_client,
        protocol_manager,
        max_iterations=config.game_skill.max_debug_iterations,
    )

    # Initialize TurnLoop with tools
    tool_registry = create_tool_registry(llm_client=llm_client)

    # Build the AssetService for asset generation
    asset_service = AssetService(config)

    # Build the GameSkill orchestrator
    game_skill = GameSkill(
        llm_client=llm_client,
        template_skill=template_skill,
        debug_skill=debug_skill,
        tool_registry=tool_registry,
        config=config,
    )
    game_skill.set_asset_service(asset_service)

    console.print(Panel.fit(
        f"[bold]OpenGame v{__version__}[/bold]\n"
        f"Prompt: [cyan]{prompt}[/cyan]\n"
        f"Output: {output_dir}\n"
        f"Model: [cyan]{model}[/cyan]",
        title="Game Generation",
    ))

    # Run the pipeline
    import asyncio
    result = asyncio.run(game_skill.generate_game(prompt, output_dir))

    if result.success:
        console.print(f"\n[green]✓ Game generated successfully![/green]")
        console.print(f"  Project: {result.project_dir}")
        console.print(f"  Duration: {result.duration_ms / 1000:.1f}s")
        if result.gdd:
            console.print(f"  GDD: {result.gdd.title}")
    else:
        console.print(f"\n[red]✗ Game generation failed[/red]")
        if result.error:
            console.print(f"  Error: {result.error}")
