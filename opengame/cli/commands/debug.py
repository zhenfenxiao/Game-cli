"""Debug command — diagnose and repair a game project.

This is a placeholder stub. The full debug loop will be
implemented in Phase 3 (Debug Skill).
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Debug a game project")
console = Console()


@app.command()
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
    """Debug a game project, diagnosing and repairing build/test errors.

    Example:
        opengame debug ./my-game
        opengame debug ./my-game --auto-fix --max-iterations 10
    """
    console.print(f"[bold]Debug Mode[/bold]")
    console.print(f"  Project: {project_path}")
    console.print(f"  Max Iterations: {max_iterations}")
    console.print(f"  Auto Fix: {auto_fix}")
    console.print()
    console.print("[yellow]Debug command is not yet implemented. Coming in Phase 3.[/yellow]")
