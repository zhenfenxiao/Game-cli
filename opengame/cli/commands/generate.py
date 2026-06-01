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
from opengame.tracing.store import TraceStore
from opengame.tracing.tracer import TraceSession

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
    max_debug_iterations: int | None = typer.Option(
        None,
        "--max-debug-iterations",
        "-n",
        help="Maximum debug iterations (default: 20 from config)",
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

    # Protocol stored alongside the generated game so debug can continue later
    protocol_manager = ProtocolManager(output_dir / ".opengame" / "debug-protocol")
    debug_iterations = max_debug_iterations if max_debug_iterations is not None else config.game_skill.max_debug_iterations
    debug_skill = DebugSkill(
        llm_client,
        protocol_manager,
        max_iterations=debug_iterations,
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

    # Set up tracing
    trace_store = TraceStore()
    trace_store.open()
    trace = TraceSession(trace_store)
    game_skill.set_tracer(trace)

    console.print(Panel.fit(
        f"[bold]OpenGame v{__version__}[/bold]\n"
        f"Prompt: [cyan]{prompt}[/cyan]\n"
        f"Output: {output_dir}\n"
        f"Model: [cyan]{config.llm.model}[/cyan]\n"
        f"Image: [yellow]{config.image.provider if config.image else 'none'}[/yellow]\n"
        f"Audio: [yellow]{config.audio.provider if config.audio else 'none'}[/yellow]",
        title="Game Generation",
    ))

    # Run the pipeline (with proper event loop cleanup)
    import asyncio
    import warnings
    loop = asyncio.new_event_loop()
    try:
        trace.start(prompt, config.llm.model)
        console.print(f"[dim]Trace session #{trace.session_id} started[/dim]")
        result = loop.run_until_complete(game_skill.generate_game(prompt, output_dir))
        trace.finish(success=result.success, error=result.error)
        event_count = len(trace_store.get_events(trace.session_id)) if trace.session_id else 0
        console.print(f"[dim]Trace saved: {event_count} events → .opengame/traces/traces.db[/dim]")
        # Let pending subprocess transports finish cleanup
        loop.run_until_complete(asyncio.sleep(0.1))
    except Exception as e:
        trace.finish(success=False, error=str(e))
        raise
    finally:
        trace_store.close()
        # Suppress "Event loop is closed" noise from subprocess cleanup
        warnings.filterwarnings("ignore", category=ResourceWarning)
        loop.close()

    if result.success:
        console.print(f"\n[green]✓ Game generated successfully![/green]")
        console.print(f"  Project: {result.project_dir}")
        console.print(f"  Duration: {result.duration_ms / 1000:.1f}s")
        if result.gdd:
            console.print(f"  GDD: {result.gdd.title}")
    elif result.gdd is not None:
        # GDD was generated — game may be playable even if debug failed
        console.print(f"\n[yellow]⚠ Game generated with warnings[/yellow]")
        console.print(f"  Project: {result.project_dir}")
        console.print(f"  The game may work in browser despite debug phase issues.")
        console.print(f"  To serve: cd {result.project_dir} && npm run dev")
        console.print(f"  To continue debugging: opengame debug {result.project_dir} --auto-fix")
        if result.error:
            console.print(f"  [dim]Debug: {result.error}[/dim]")
    else:
        console.print(f"\n[red]✗ Game generation failed[/red]")
        if result.error:
            console.print(f"  [red]Error:[/red] {result.error}")
