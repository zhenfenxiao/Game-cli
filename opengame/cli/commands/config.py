"""Config subcommands: show, init, validate."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from opengame.cli.config_loader import ConfigLoader

app = typer.Typer(help="Manage OpenGame configuration")
console = Console()


@app.command()
def show(
    raw: bool = typer.Option(False, "--raw", help="Show raw config values as JSON"),
) -> None:
    """Show the effective configuration (merged from all sources)."""
    loader = ConfigLoader()
    config = loader.load(load_dotenv=True)

    if raw:
        console.print_json(config.model_dump_json(indent=2))
        return

    # Styled output
    console.print("[bold]OpenGame Configuration[/bold]\n")

    # LLM section
    console.print(f"  LLM Provider: [cyan]{config.llm.provider}[/cyan]")
    console.print(f"  LLM Model: [cyan]{config.llm.model}[/cyan]")
    console.print(f"  LLM Base URL: [cyan]{config.llm.base_url}[/cyan]")
    console.print(f"  Approval Mode: [yellow]{config.approval_mode}[/yellow]")
    console.print()

    # Asset providers
    table = Table(title="Asset Providers")
    table.add_column("Modality", style="bold")
    table.add_column("Provider")
    table.add_column("Model")

    for name, provider in [
        ("Image", config.image),
        ("Audio", config.audio),
        ("Video", config.video),
        ("Reasoning", config.reasoning),
    ]:
        if provider:
            table.add_row(name, provider.provider, provider.model or "default")
        else:
            table.add_row(name, "[dim]not configured[/dim]", "")

    console.print(table)
    console.print()

    # Game Skill
    console.print("[bold]Game Skill:[/bold]")
    console.print(f"  Templates: {config.game_skill.templates_dir}")
    console.print(f"  Docs: {config.game_skill.docs_dir}")
    console.print(f"  Max Debug Iterations: {config.game_skill.max_debug_iterations}")


@app.command()
def init() -> None:
    """Create a user settings file with template content."""
    loader = ConfigLoader()
    loader.ensure_directories()
    path = loader.create_user_settings_template()
    console.print(f"[green]Created settings template at:[/green] {path}")
    console.print("Edit this file to add your API keys.")


@app.command()
def validate() -> None:
    """Validate the current configuration."""
    loader = ConfigLoader()
    config = loader.load(load_dotenv=True)

    errors: list[str] = []
    warnings: list[str] = []

    # Validate LLM config
    if not config.llm.api_key:
        warnings.append(
            "LLM API key is not configured — set OPENAI_API_KEY or add to settings.json"
        )

    console.print("[bold]Configuration Validation[/bold]\n")

    if errors:
        console.print("[red]Errors:[/red]")
        for e in errors:
            console.print(f"  [red][X][/red] {e}")

    if warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for w in warnings:
            console.print(f"  [yellow][!][/yellow] {w}")

    if not errors and not warnings:
        console.print("[green]Configuration is valid.[/green]")
