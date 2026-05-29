"""Generate command — create a game from a natural language prompt.

This is a placeholder stub. The full 6-phase pipeline will be
implemented in Phase 5.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Generate a game from a natural language prompt")
console = Console()


@app.command()
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
    approval_mode: str = typer.Option(
        "auto-edit",
        "--approval",
        help="Approval mode: ask, auto-edit, or yolo",
    ),
    model: str = typer.Option(
        "gpt-4o",
        "--model",
        "-m",
        help="LLM model to use",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose output",
    ),
) -> None:
    """Generate a complete web game from a natural language prompt.

    Example:
        opengame generate -p "Build a Snake clone with WASD controls and a dark theme"
    """
    console.print(f"[bold]Game Generation[/bold]")
    console.print(f"  Prompt: [cyan]{prompt}[/cyan]")
    console.print(f"  Output: {output_dir}")
    console.print(f"  Model: [cyan]{model}[/cyan]")
    console.print(f"  Approval: [yellow]{approval_mode}[/yellow]")
    console.print()
    console.print(
        "[yellow]Game generation is not yet implemented. Coming in Phase 5.[/yellow]"
    )
