"""Debug command — diagnose and repair a game project.

Wires the DebugSkill to the CLI for standalone project debugging.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from opengame.cli.config_loader import ConfigLoader
from opengame.core.openai_client import OpenAiClient
from opengame.skills.debug_skill import DebugSkill, ProtocolManager

app = typer.Typer(help="Debug a game project")
console = Console()


@app.callback(invoke_without_command=True)
def debug(
    project_path: Path = typer.Argument(
        ...,
        help="Path to the game project to debug",
    ),
    max_iterations: int = typer.Option(
        20,
        "--max-iterations",
        "-n",
        help="Maximum debug iterations",
    ),
    auto_fix: bool = typer.Option(
        False,
        "--auto-fix",
        "-y",
        help="Automatically apply fixes without asking",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose output",
    ),
) -> None:
    """Debug a game project, diagnosing and repairing build/test errors."""
    # Load config
    loader = ConfigLoader()
    config = loader.load(load_dotenv=True)

    # Initialize LLM client
    llm_client = OpenAiClient(
        model=config.llm.model,
        base_url=config.llm.base_url,
        api_key=config.llm.api_key,
        timeout=config.llm.timeout,
    )

    # Initialize debug skill
    protocol_dir = project_path / ".opengame" / "debug-protocol"
    protocol_manager = ProtocolManager(protocol_dir)
    debug_skill = DebugSkill(llm_client, protocol_manager, max_iterations=max_iterations)

    console.print(Panel.fit(
        f"Project: {project_path}\n"
        f"Max Iterations: {max_iterations}\n"
        f"Auto Fix: {auto_fix}",
        title="Debug Mode",
    ))

    # Run debug loop
    import asyncio
    result = asyncio.run(debug_skill.debug(
        project_dir=project_path,
        run_dev=False,
        evolve_after=True,
    ))

    # Display results
    if result.success:
        console.print(f"\n[green]✓ Debug completed successfully![/green]")
        console.print(f"  Iterations: {result.trace.total_iterations}")
        console.print(f"  Duration: {result.trace.total_duration_ms / 1000:.1f}s")

        # Show matched/new entries
        if result.trace.matched_entries:
            console.print(f"  Matched entries: {len(result.trace.matched_entries)}")
        if result.trace.new_entries:
            console.print(f"  New entries: {len(result.trace.new_entries)}")
    else:
        console.print(f"\n[yellow]⚠ Debug incomplete[/yellow]")
        console.print(f"  Iterations: {result.trace.total_iterations}/{max_iterations}")

        # Show iteration details
        if verbose and result.trace.iterations:
            table = Table(title="Debug Iterations")
            table.add_column("Iter", style="cyan")
            table.add_column("Stage", style="yellow")
            table.add_column("Passed")
            table.add_column("Action")

            for it in result.trace.iterations:
                table.add_row(
                    str(it.iteration),
                    it.stage,
                    "✓" if it.passed else "✗",
                    it.repair_action[:50] if it.repair_action else "",
                )
            console.print(table)
