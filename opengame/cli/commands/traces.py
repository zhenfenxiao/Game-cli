"""Traces command — browse, inspect, and export agent trace sessions."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from opengame.tracing.store import TraceStore

app = typer.Typer(help="Browse and export agent trace history")
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
    table.add_column("Type")
    table.add_column("Prompt", style="white")
    table.add_column("Model", style="yellow")
    table.add_column("Status")
    table.add_column("Start")

    for s in sessions:
        stype = s.get("type", "generate")
        type_label = "🤖" if stype == "generate" else "💬" if stype == "shell" else stype
        status = "[green]✓[/green]" if s["success"] else "[red]✗[/red]" if not stype == "shell" else ""
        if stype == "shell":
            status = "[dim]saved[/dim]"
        start = s["start"][:19] if s["start"] else "-"
        table.add_row(str(s["id"]), type_label, s["prompt"], s["model"], status, start)

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
    stype = session.get("session_type", "generate")
    type_label = "Shell Session" if stype == "shell" else "Game Generation"
    console.print(f"[bold]Session #{session['id']}[/bold] [dim]({type_label})[/dim]")
    console.print(f"  Prompt: [cyan]{session['prompt']}[/cyan]")
    console.print(f"  Model: {session['model']}")
    if stype != "shell":
        console.print(f"  Success: {'[green]✓[/green]' if session['success'] else '[red]✗[/red]'}")
    if session.get("error"):
        console.print(f"  Error: [red]{session['error'][:200]}[/red]")

    # For shell sessions, show message stats
    if stype == "shell":
        for e in events:
            data = json.loads(e["data_json"]) if isinstance(e["data_json"], str) else e.get("data_json", {})
            if e["event_type"] == "shell_snapshot":
                msgs = data.get("messages", [])
                console.print(f"  Messages: {len(msgs)}")
                console.print(f"  Turns: {data.get('turn_count', 0)}")
                console.print(f"  Project: {data.get('project', '')}")
                # Show last few messages as preview
                if msgs:
                    console.print(f"\n[bold]Last messages:[/bold]")
                    for m in msgs[-3:]:
                        role = m.get("role", "?")
                        content = str(m.get("content", ""))[:150]
                        console.print(f"  [dim]{role}:[/dim] {content}")
                break
        return

    # Phase summary
    phases: dict[str, list[dict]] = {}
    for e in events:
        phases.setdefault(e["phase"], []).append(e)

    console.print(f"\n[bold]Phases ({len(phases)}):[/bold]")
    for phase, phase_events in phases.items():
        errors = [e for e in phase_events if e["event_type"] == "error"]
        end_ev = next((e for e in phase_events if e["event_type"] == "phase_end"), None)

        result = ""
        duration = ""
        if end_ev:
            data = json.loads(end_ev["data_json"]) if isinstance(end_ev["data_json"], str) else end_ev.get("data_json", {})
            result = data.get("result", "")
            if "elapsed_ms" in data:
                duration = f" ({data['elapsed_ms'] / 1000:.1f}s)"

        status = "[red]✗[/red]" if errors else "[green]✓[/green]"
        console.print(f"  {status} [bold]{phase}[/bold]{duration} {result}")

    # Event timeline
    console.print(f"\n[bold]Timeline ({len(events)} events):[/bold]")
    icons = {
        "phase_start": "▶", "phase_end": "◀", "llm_call": "🤖", "llm_response": "💬",
        "llm_exchange": "🔄", "tool_call": "🔧", "tool_result": "✅",
        "error": "❌", "debug_iteration": "🪲", "compression": "📦",
    }
    for e in events[:100]:
        icon = icons.get(e["event_type"], "•")
        data = json.loads(e["data_json"]) if isinstance(e["data_json"], str) else e.get("data_json", {})
        detail = ""
        if e["event_type"] == "llm_exchange":
            msgs = data.get("messages_count", 0)
            resp_len = len(data.get("response", ""))
            tokens = data.get("token_usage", {}).get("total_tokens", 0)
            has_tools = "🔧" if data.get("tool_calls") else ""
            detail = f" [{data.get('model', '')}] {msgs}msg→{resp_len}chars {tokens}tk {has_tools}"
        elif e["event_type"] == "llm_call":
            detail = f" [{data.get('model', '')}]"
        elif e["event_type"] == "tool_call":
            detail = f" [{data.get('tool_name', '')}]"
        elif e["event_type"] == "tool_result":
            detail = f" [{data.get('tool_name', '')} {'✓' if data.get('success') else '✗'}]"
        elif e["event_type"] == "compression":
            detail = f" ~{data.get('tokens_before', '?')}→~{data.get('tokens_after', '?')}tk ({data.get('reduction_pct', '?')}%)"
        elif e["event_type"] == "error":
            detail = f" [red]{data.get('message', '')[:80]}[/red]"
        console.print(f"  {icon} #{e['seq']} {e['event_type']}{detail}")


@app.command()
def export(
    session_id: int = typer.Option(None, "--session", "-s", help="Export a specific session (omit for all)"),
    output_dir: Path = typer.Option(Path("./traces-export"), "--output", "-o", help="Output directory for JSON files"),
    pretty: bool = typer.Option(True, "--pretty/--compact", help="Pretty-print JSON (default: true)"),
) -> None:
    """Export trace sessions to JSON files.

    Examples:
        opengame traces export                    # Export all sessions
        opengame traces export -s 3               # Export session #3
        opengame traces export -o ./my-traces     # Custom output directory
        opengame traces export --compact          # Compact JSON (no indentation)
    """
    store = TraceStore()
    store.open()

    indent = 2 if pretty else None

    if session_id is not None:
        # Export single session
        data = store.export_session(session_id)
        if data is None:
            console.print(f"[red]Session {session_id} not found.[/red]")
            store.close()
            raise typer.Exit(1)

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"session-{session_id}.json"
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=indent), "utf-8")

        event_count = len(data["events"])
        store.close()
        console.print(f"[green]✓[/green] Exported session [bold]{session_id}[/bold] "
                      f"({event_count} events) → {output_path}")
    else:
        # Export all sessions
        all_data = store.export_all()
        store.close()

        if not all_data:
            console.print("[dim]No trace sessions to export.[/dim]")
            return

        output_dir.mkdir(parents=True, exist_ok=True)

        total_events = 0
        for data in all_data:
            sid = data["session"]["id"]
            output_path = output_dir / f"session-{sid}.json"
            output_path.write_text(json.dumps(data, ensure_ascii=False, indent=indent), "utf-8")
            total_events += len(data["events"])

        console.print(f"[green]✓[/green] Exported [bold]{len(all_data)}[/bold] sessions "
                      f"({total_events} events) → {output_dir}/")
        console.print(f"\n  Files: {output_dir}/session-*.json")
        console.print(f"  Format: {{\"session\": {{...}}, \"events\": [...]}}")
