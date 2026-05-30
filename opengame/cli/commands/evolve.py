"""Evolve command — evolve the template library from existing projects.

Wires the TemplateSkill to the CLI for standalone library evolution.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from opengame.cli.config_loader import ConfigLoader
from opengame.core.openai_client import OpenAiClient
from opengame.skills.template_skill import TemplateSkill
from opengame.skills.template_skill.library_manager import LibraryManager

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
    """Evolve the template library by analyzing a completed game project."""
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

    # Initialize template skill
    library_manager = LibraryManager(library_path)
    template_skill = TemplateSkill(llm_client, library_manager)

    console.print(Panel.fit(
        f"Project: {project_path}\n"
        f"Library: {library_path}\n"
        f"Dry Run: {dry_run}",
        title="Template Evolution",
    ))

    # Run evolution
    import asyncio
    import uuid

    task_id = f"evolve-{uuid.uuid4()!s:.8}"

    if dry_run:
        # Show what would be learned without saving
        snapshot = asyncio.run(template_skill.collector.collect(project_path))
        console.print(f"\nFiles collected: {len(snapshot.files)}")
        console.print(f"Code summary:\n{snapshot.code_summary}")

        library = asyncio.run(library_manager.load_or_init())
        classification = asyncio.run(
            template_skill.classifier.classify(snapshot, library),
        )
        console.print(f"\nClassified as: [cyan]{classification.archetype}[/cyan]")
        console.print(f"Confidence: {classification.confidence}")
        console.print(f"New family: {classification.is_new_family}")
    else:
        # Run full pipeline
        result = asyncio.run(template_skill.evolve(project_path, task_id))

        console.print(f"\n[green]✓ Template library evolved![/green]")
        console.print(f"  Library version: {result.version}")
        console.print(f"  Families: {len(result.families)}")
        console.print(f"  Evolution log entries: {len(result.evolution_log)}")

        # Show library summary
        summary = asyncio.run(template_skill.get_library_summary())
        console.print(f"\n{summary}")
