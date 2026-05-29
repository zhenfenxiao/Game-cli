"""Typer CLI root application for OpenGame."""

from __future__ import annotations

from pathlib import Path

import typer

from opengame import __version__

app = typer.Typer(
    name="opengame",
    help="Open-source agentic framework for end-to-end web game creation.",
    rich_markup_mode="rich",
)

# Register subcommands
from opengame.cli.commands import config as config_commands  # noqa: E402
from opengame.cli.commands import debug as debug_commands  # noqa: E402
from opengame.cli.commands import evolve as evolve_commands  # noqa: E402
from opengame.cli.commands import generate as generate_commands  # noqa: E402

app.add_typer(config_commands.app, name="config", help="Manage configuration")
app.add_typer(generate_commands.app, name="generate", help="Generate a game from a prompt")
app.add_typer(debug_commands.app, name="debug", help="Debug a game project")
app.add_typer(evolve_commands.app, name="evolve", help="Evolve template library")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"opengame v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
    model: str = typer.Option(
        "gpt-4o",
        "--model",
        "-m",
        help="LLM model to use",
    ),
    approval_mode: str = typer.Option(
        "auto-edit",
        "--approval-mode",
        help="Approval mode: ask, auto-edit, or yolo",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose output",
    ),
    output_dir: Path = typer.Option(
        Path.cwd(),
        "--output-dir",
        "-o",
        help="Output directory for generated projects",
    ),
) -> None:
    """OpenGame CLI — generate web games from natural language prompts."""
    if verbose:
        typer.echo(f"OpenGame v{__version__}")
