"""Evolve command — evolve the template library from existing projects.

This is a placeholder stub. The full evolve pipeline will be
implemented in Phase 3 (Template Skill).
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Evolve the template library")
console = Console()


@app.command()
def evolve(
    project_path: Path = typer.Argument(
        ...,
        help="Path to the game project to learn from",
    ),
    library_path: Path = typer.Option(
        Path(".opengame/template-library"),
        "--library",
        "-l",
        help="Path to the template library",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview changes without writing to the library",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose output",
    ),
) -> None:
    """Evolve the template library by analyzing a completed game project.

    Example:
        opengame evolve ./my-game
        opengame evolve ./my-game --dry-run
    """
    console.print(f"[bold]Template Evolution[/bold]")
    console.print(f"  Project: {project_path}")
    console.print(f"  Library: {library_path}")
    console.print(f"  Dry Run: {dry_run}")
    console.print()
    console.print(
        "[yellow]Evolve command is not yet implemented. Coming in Phase 3.[/yellow]"
    )
