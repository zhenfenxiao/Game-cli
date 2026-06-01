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
from opengame.cli.commands.debug import debug  # noqa: E402
from opengame.cli.commands.evolve import evolve  # noqa: E402
from opengame.cli.commands.generate import generate  # noqa: E402
from opengame.cli.commands.shell import shell  # noqa: E402
from opengame.cli.commands import traces as traces_commands  # noqa: E402

# Sub-typers (have their own subcommands: config show/init/validate, traces list/show/export)
app.add_typer(config_commands.app, name="config", help="Manage configuration")
app.add_typer(traces_commands.app, name="traces", help="Browse agent trace history")

# Direct commands (no subcommands — register as top-level commands)
app.command(name="generate", help="Generate a game from a prompt")(generate)
app.command(name="debug", help="Debug a game project")(debug)
app.command(name="evolve", help="Evolve template library")(evolve)
app.command(name="shell", help="Interactive game development REPL")(shell)


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
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model to use (default: from config or env)",
    ),
    approval_mode: str | None = typer.Option(
        None,
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
