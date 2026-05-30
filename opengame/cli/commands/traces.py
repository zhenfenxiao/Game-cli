"""Traces command — browse and inspect agent trace sessions."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from opengame.tracing.store import TraceStore

app = typer.Typer(help="Browse agent trace history")
console = Console()


@app.command()
def list(limit: int = typer.Option(20, "--limit", "-n", help="Number of sessions to show")) -> None:
    """List recent trace sessions."""
    store = TraceStore()
    store.open()

    sessions = store.list_sessions(limit)
    store.close()

    if not sessions:
        console.print("[dim]No trace sessions found.[/dim]")
        return

    table = Table(title=f"Trace Sessions (last {len(sessions)})")
    table.add_column("ID", style="cyan")
    table.add_column("Prompt", style="white")
    table.add_column("Model", style="yellow")
    table.add_column("Status")
    table.add_column("Start")

    for s in sessions:
        status = "[green]✓[/green]" if s["success"] else "[red]✗[/red]"
        start = s["start"][:19] if s["start"] else "-"
        table.add_row(str(s["id"]), s["prompt"], s["model"], status, start)

    console.print(table)


@app.command()
def show(session_id: int = typer.Argument(..., help="Session ID to inspect")) -> None:
    """Show detailed trace for a session."""
    store = TraceStore()
    store.open()

    session = store.get_session(session_id)
    if session is None:
        console.print(f"[red]Session {session_id} not found.[/red]")
        store.close()
        return

    events = store.get_events(session_id)
    store.close()

    # Session header
    console.print(f"[bold]Session #{session['id']}[/bold]")
    console.print(f"  Prompt: [cyan]{session['prompt']}[/cyan]")
    console.print(f"  Model: {session['model']}")
    console.print(f"  Success: {'[green]✓[/green]' if session['success'] else '[red]✗[/red]'}")
    if session["error"]:
        console.print(f"  Error: [red]{session['error'][:200]}[/red]")

    # Phase summary
    phases: dict[str, list[dict]] = {}
    for e in events:
        phases.setdefault(e["phase"], []).append(e)

    console.print(f"\n[bold]Phases ({len(phases)}):[/bold]")
    for phase, phase_events in phases.items():
        start_ev = next((e for e in phase_events if e["event_type"] == "phase_start"), None)
        end_ev = next((e for e in phase_events if e["event_type"] == "phase_end"), None)
        errors = [e for e in phase_events if e["event_type"] == "error"]

        duration = ""
        if end_ev and "elapsed_ms" in (json.loads(end_ev["data_json"]) if isinstance(end_ev["data_json"], str) else end_ev.get("data_json", {})):
            data = json.loads(end_ev["data_json"])
            duration = f" ({data.get('elapsed_ms', 0)/1000:.1f}s)"

        result = ""
        if end_ev:
            data = json.loads(end_ev["data_json"])
            result = data.get("result", "")

        status = "[red]✗[/red]" if errors else "[green]✓[/green]"
        console.print(f"  {status} [bold]{phase}[/bold]{duration} {result}")

    # Event timeline
    console.print(f"\n[bold]Timeline ({len(events)} events):[/bold]")
    for e in events[:50]:  # limit display
        icon = {
            "phase_start": "▶", "phase_end": "◀", "llm_call": "🤖", "llm_response": "💬",
            "tool_call": "🔧", "tool_result": "✅", "error": "❌", "debug_iteration": "🪲",
        }.get(e["event_type"], "•")

        data = json.loads(e["data_json"]) if isinstance(e["data_json"], str) else e.get("data_json", {})
        detail = ""
        if e["event_type"] == "llm_call":
            detail = f" [{data.get('model', '')}]"
        elif e["event_type"] == "tool_call":
            detail = f" [{data.get('tool_name', '')}]"
        elif e["event_type"] == "tool_result":
            detail = f" [{data.get('tool_name', '')} {'✓' if data.get('success') else '✗'}]"
        elif e["event_type"] == "error":
            detail = f" [red]{data.get('message', '')[:80]}[/red]"

        console.print(f"  {icon} #{e['seq']} {e['event_type']}{detail}")
