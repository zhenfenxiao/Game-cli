"""Shell command — interactive REPL for collaborative game development.

Similar to Claude Code, the user and agent collaborate on a game project.
The agent can read/write files, run commands, and ask the user questions.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from prompt_toolkit import PromptSession as PTKPrompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from opengame.cli.config_loader import ConfigLoader
from opengame.core.exceptions import UserQuestionRequested
from opengame.core.interactive_loop import InteractiveLoop, TurnOutcome
from opengame.core.openai_client import OpenAiClient
from opengame.tools.factory import create_interactive_tool_registry
from opengame.tracing.store import TraceStore

console = Console()


def shell(
    project_path: Path = typer.Argument(
        Path.cwd(),
        help="Path to the game project",
    ),
    model: str | None = typer.Option(
        None, "--model", "-m",
        help="LLM model to use (default: from config or env)",
    ),
    verbose: bool = typer.Option(
        False, "--verbose",
        help="Show tool call details",
    ),
    design_first: bool = typer.Option(
        False, "--design", "-d",
        help="Start in design mode: agent proposes plan before implementing",
    ),
    resume: str | None = typer.Option(
        None, "--resume", "-r",
        help="Resume a saved session (session filename or ID)",
    ),
) -> None:
    """Start an interactive game development session.

    Chat with the agent to modify your game. The agent can read files,
    write code, run build commands, and ask you questions.

    Special commands (type at the prompt):
      /exit       — End the session
      /help       — Show available commands
      /clear      — Clear the conversation history
      /design     — Toggle design-first mode
      /history    — Show recent conversation summary
      /save       — Save session to .opengame/shell-sessions/
    """
    root = project_path.resolve()

    if not root.exists():
        console.print(f"[red]Project not found: {root}[/red]")
        raise typer.Exit(1)

    # Load config
    loader = ConfigLoader()
    if model is not None:
        loader.set_cli_override("llm.model", model)
    config = loader.load(load_dotenv=True)

    # LLM client
    llm_client = OpenAiClient(
        model=config.llm.model, base_url=config.llm.base_url,
        api_key=config.llm.api_key, timeout=config.llm.timeout,
    )

    # Tool registry with interactive tools
    tool_registry = create_interactive_tool_registry(llm_client=llm_client)

    # Build system prompt with project context
    system_prompt = _build_system_prompt(root, design_first)

    # Initialize interactive loop
    loop = InteractiveLoop(llm_client, tool_registry)
    loop.set_on_compressed(lambda msg: console.print(f"[dim]📦 {msg}[/dim]"))
    loop.start(system_prompt)

    # Resume from saved session if requested
    if resume:
        _load_session(loop, root, resume)

    # Display header
    _print_header(root, config.llm.model, design_first, resumed=resume is not None)

    design_mode = design_first
    import asyncio

    # Use prompt_toolkit for proper line editing (backspace, cursor, history)
    hist_path = root / ".opengame" / ".shell_history"
    hist_path.parent.mkdir(parents=True, exist_ok=True)
    ptk_session = PTKPrompt(
        history=FileHistory(str(hist_path)),
        style=Style.from_dict({"": "#00ff00 bold"}),
    )

    async def run_interaction() -> None:
        nonlocal design_mode

        while True:
            try:
                user_input = await ptk_session.prompt_async(
                    "> ", multiline=False,
                )
                user_input = user_input.strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if not user_input:
                continue

            # Handle special commands
            if user_input.startswith("/"):
                cmd, *args = user_input[1:].split(maxsplit=1)
                if cmd == "exit":
                    console.print("[dim]Goodbye![/dim]")
                    break
                elif cmd == "help":
                    _show_help()
                    continue
                elif cmd == "clear":
                    loop.start(system_prompt)
                    console.print("[dim]Conversation cleared.[/dim]")
                    continue
                elif cmd == "design":
                    design_mode = not design_mode
                    status = "ON" if design_mode else "OFF"
                    console.print(f"[dim]Design-first mode: [bold]{status}[/bold][/dim]")
                    continue
                elif cmd == "history":
                    if loop.context:
                        msg_count = len(loop.context.messages)
                        turns = loop.context.turn_count
                        console.print(f"[dim]{msg_count} messages, {turns} turns[/dim]")
                    continue
                elif cmd == "save":
                    _save_session(loop, root)
                    continue
                elif cmd == "resume":
                    await _list_and_resume(loop, root)
                    continue
                else:
                    console.print(f"[yellow]Unknown command: /{cmd}. Type /help for help.[/yellow]")
                    continue

            # Design mode: prefix with instruction to propose first
            if design_mode:
                user_input = (
                    f"{user_input}\n\n"
                    "Before implementing, first use propose_design to present "
                    "your implementation plan for review."
                )

            # Send to agent
            with console.status("[dim]Thinking...[/dim]"):
                output = await loop.send_message(user_input)

            # Handle outcomes
            while True:
                if output.outcome == TurnOutcome.DONE:
                    if output.content:
                        console.print(Markdown(output.content))
                    break

                elif output.outcome == TurnOutcome.USER_QUESTION:
                    _display_question(output.question)
                    try:
                        answer = await ptk_session.prompt_async(
                            "Your answer > ", multiline=False,
                        )
                    except (KeyboardInterrupt, EOFError):
                        answer = "skip"
                    with console.status("[dim]Processing answer...[/dim]"):
                        output = await loop.answer_question(answer)
                    # Continue loop to handle next outcome

                elif output.outcome == TurnOutcome.TURN_LIMIT:
                    console.print("[yellow]Turn limit reached. Type /clear to start fresh.[/yellow]")
                    break

                elif output.outcome == TurnOutcome.TOKEN_LIMIT:
                    console.print("[yellow]Token limit reached. Type /clear to start fresh.[/yellow]")
                    break

                elif output.outcome == TurnOutcome.TOOL_CALLS:
                    with console.status("[dim]Executing tools...[/dim]"):
                        output = await loop._continue_turns()
                    # Continue loop

                else:
                    break

    asyncio.run(run_interaction())


def _build_system_prompt(root: Path, design_first: bool) -> str:
    """Build a system prompt with project context."""
    # Gather project info
    files = sorted(str(p.relative_to(root)) for p in root.rglob("*")
                   if p.is_file() and "node_modules" not in str(p) and ".git" not in str(p))[:30]

    pkg_info = ""
    pkg_path = root / "package.json"
    if pkg_path.exists():
        try:
            pkg = json.loads(pkg_path.read_text())
            pkg_info = f"- Name: {pkg.get('name', 'unknown')}\n"
            pkg_info += f"- Scripts: {', '.join(pkg.get('scripts', {}).keys())}\n"
        except Exception:
            pass

    gdd_info = ""
    gdd_path = root / "GAME_DESIGN.md"
    if gdd_path.exists():
        gdd_info = f"\nThe Game Design Document is at GAME_DESIGN.md ({len(gdd_path.read_text())} chars).\n"

    design_instruction = ""
    if design_first:
        design_instruction = (
            "\n## IMPORTANT: Design-First Mode\n"
            "Before making any code changes, use the propose_design tool to present "
            "your implementation plan. Wait for user approval before implementing.\n"
        )

    return f"""You are an expert Phaser 3 + TypeScript game developer. You are collaborating
with a user on their game project in an interactive shell session.

## Project Context
- Location: {root}
{pkg_info}
## Files
{chr(10).join(f"  - {f}" for f in files[:30])}
{gdd_info}
## Your Role
- Help the user improve their game
- Read existing code before making changes
- Propose designs for complex changes
- Use ask_user when you need clarification
- Execute build commands (npm run build) to verify changes
- Be concise and focused on the user's requests

## Available Tools
You have access to file operations (read_file, write_file, edit, glob, grep, ls),
shell execution, and interactive tools (ask_user, propose_design).
{design_instruction}
## Interaction Style
- Respond in plain text or markdown
- Show code snippets when relevant
- Ask clarifying questions when needed
- Keep responses focused and actionable"""


def _print_header(root: Path, model: str, design_first: bool, resumed: bool = False) -> None:
    """Print the shell header."""
    status_parts = []
    if design_first:
        status_parts.append("[yellow]design-first[/yellow]")
    if resumed:
        status_parts.append("[green]resumed[/green]")
    status = " (" + ", ".join(status_parts) + ")" if status_parts else ""
    console.print(Panel.fit(
        f"[bold]OpenGame Interactive Shell[/bold]{status}\n"
        f"Project: [cyan]{root}[/cyan]\n"
        f"Model: [cyan]{model}[/cyan]\n"
        f"\nType your requests. Special commands:\n"
        f"  /help • /exit • /clear • /design • /history • /save • /resume",
        title="Shell",
        border_style="cyan",
    ))


def _display_question(question: UserQuestionRequested | None) -> None:
    """Display an ask_user question to the user."""
    if question is None:
        return

    if question.options:
        options_text = " / ".join(
            f"[bold]{o}[/bold]" for o in question.options
        )
        body = f"{question.question}\n\nOptions: {options_text}"
    else:
        body = question.question

    console.print(Panel(
        body,
        title=f"[bold yellow]? {question.header}[/bold yellow]",
        border_style="yellow",
    ))


def _show_help() -> None:
    """Display help text."""
    table = Table(title="Shell Commands")
    table.add_column("Command", style="cyan")
    table.add_column("Description")
    table.add_row("/exit", "End the session")
    table.add_row("/help", "Show this help")
    table.add_row("/clear", "Clear conversation history")
    table.add_row("/design", "Toggle design-first mode (agent proposes before implementing)")
    table.add_row("/history", "Show conversation stats")
    table.add_row("/save", "Save session to .opengame/shell-sessions/")
    console.print(table)


def _get_trace_store() -> TraceStore:
    """Get a TraceStore instance for shell session persistence."""
    store = TraceStore()
    store.open()
    return store


def _save_session(loop: InteractiveLoop, root: Path) -> None:
    """Save the current shell session to traces DB."""
    if loop.context is None:
        console.print("[dim]No active session to save.[/dim]")
        return

    store = _get_trace_store()
    try:
        # Create a shell-type session or use an existing shell session
        # First check if we're already in a traced session
        sid = store.create_session(
            prompt=f"Shell: {root.name}",
            model="shell-session",
            session_type="shell",
        )
        store.save_shell_session(
            session_id=sid,
            messages=loop.context.messages,
            turn_count=loop.context.turn_count,
            project_path=str(root),
        )
        console.print(f"[dim]Session saved as trace #{sid} → .opengame/traces/traces.db[/dim]")
    finally:
        store.close()


def _load_session(loop: InteractiveLoop, root: Path, session_ref: str) -> None:
    """Load a shell session from traces DB by ID."""
    store = _get_trace_store()
    try:
        # Try as numeric ID first, then search
        try:
            sid = int(session_ref)
        except ValueError:
            # Search shell sessions by prompt match
            shells = store.list_shell_sessions(limit=50)
            sid = None
            for s in shells:
                if session_ref.lower() in s["prompt"].lower():
                    sid = s["id"]
                    break
            if sid is None and shells:
                sid = shells[0]["id"]  # Default to most recent

        if sid is None:
            console.print(f"[yellow]No shell sessions found.[/yellow]")
            return

        data = store.load_shell_session(sid)
        if data is None:
            console.print(f"[yellow]Session #{sid} has no saved snapshot.[/yellow]")
            return

        # Restore messages
        if loop.context is None:
            return
        system_msg = loop.context.messages[0] if loop.context.messages else None
        loop.context.messages = [system_msg] if system_msg else []
        saved_messages = data.get("messages", [])
        loop.context.messages.extend(saved_messages[1:] if saved_messages and system_msg else saved_messages)
        loop.context.turn_count = data.get("turn_count", 0)

        console.print(f"[green]Resumed session #{sid}: {len(saved_messages)} messages, "
                      f"{data.get('turn_count', 0)} turns[/green]")
    finally:
        store.close()


def _list_and_resume(loop: InteractiveLoop, root: Path) -> None:
    """List saved shell sessions and prompt user to pick one."""
    store = _get_trace_store()
    try:
        sessions = store.list_shell_sessions(limit=20)
        if not sessions:
            console.print("[dim]No saved shell sessions. Use /save first.[/dim]")
            return

        from rich.table import Table
        table = Table(title="Saved Shell Sessions (in traces)")
        table.add_column("#", style="cyan")
        table.add_column("ID")
        table.add_column("Project")
        table.add_column("Start")

        for i, s in enumerate(sessions[:10], 1):
            start = s["start"][:19] if s["start"] else "-"
            table.add_row(str(i), str(s["id"]), s["prompt"][:40], start)

        console.print(table)
        console.print("[dim]Type the number or session ID to resume, or press Enter to cancel.[/dim]")
        console.print("[dim]Use 'opengame traces list' for full history.[/dim]")

        try:
            choice = PTKPrompt().prompt("Resume session > ", multiline=False)
        except (KeyboardInterrupt, EOFError):
            return

        if not choice:
            return

        # Resolve choice
        if choice.isdigit() and 1 <= int(choice) <= len(sessions):
            sid = sessions[int(choice) - 1]["id"]
        else:
            sid = int(choice) if choice.isdigit() else None

        if sid:
            _load_session(loop, root, str(sid))
        else:
            console.print(f"[yellow]Invalid session: {choice}[/yellow]")
    finally:
        store.close()
