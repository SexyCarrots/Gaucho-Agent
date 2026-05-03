"""Gaucho-Agent CLI – Typer app with subcommands."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from gaucho_agent.config import settings
from gaucho_agent.utils.logging import setup_logging

setup_logging()
console = Console()

app = typer.Typer(
    name="gaucho",
    help="Gaucho-Agent: UCSB academic assistant CLI",
    add_completion=False,
)

sync_app = typer.Typer(help="Sync data from Canvas and UCSB APIs.")
app.add_typer(sync_app, name="sync")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_config(require_canvas: bool = False, require_ucsb: bool = False, require_llm: bool = False) -> bool:
    """Print warnings for missing config; return False if critical items missing."""
    ok = True
    if require_canvas and not settings.canvas_ics_url:
        console.print("[yellow]Warning:[/] CANVAS_ICS_URL is not set in .env")
        ok = False
    if require_ucsb and not settings.ucsb_api_key:
        console.print("[yellow]Warning:[/] UCSB_API_KEY is not set in .env")
        ok = False
    if require_llm:
        if settings.llm_provider == "openai" and not settings.openai_api_key:
            console.print("[red]Error:[/] OPENAI_API_KEY is not set. Run `gaucho doctor` for details.")
            ok = False
        elif settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
            console.print("[red]Error:[/] ANTHROPIC_API_KEY is not set. Run `gaucho doctor` for details.")
            ok = False
    return ok


def _get_llm_client():
    """Return the configured LLM client instance."""
    if settings.llm_provider == "anthropic":
        from gaucho_agent.clients.llm_anthropic import AnthropicClient
        return AnthropicClient(api_key=settings.anthropic_api_key, model=settings.llm_model)
    from gaucho_agent.clients.llm_openai import OpenAIClient
    return OpenAIClient(api_key=settings.openai_api_key, model=settings.llm_model)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def init():
    """Initialize the database and verify configuration."""
    from gaucho_agent.db import init_db
    console.print("[bold cyan]Initializing Gaucho-Agent...[/]")
    init_db()
    console.print("[green]Database initialized.[/]")
    _check_config()
    console.print("[bold]Done.[/] Run [cyan]gaucho doctor[/] for a full health check.")


@app.command()
def doctor():
    """Check environment variables, DB connectivity, and API reachability."""
    console.print(Panel("[bold cyan]Gaucho-Agent Health Check[/]", expand=False))

    checks = Table(show_header=True, header_style="bold magenta")
    checks.add_column("Check")
    checks.add_column("Status")
    checks.add_column("Value / Notes")

    # DB
    try:
        from gaucho_agent.db import init_db, get_session
        from sqlmodel import text
        init_db()
        with get_session() as s:
            s.exec(text("SELECT 1"))
        checks.add_row("Database", "[green]OK[/]", settings.gaucho_db_path)
    except Exception as e:
        checks.add_row("Database", "[red]FAIL[/]", str(e))

    # Config
    def chk(label: str, value: str, secret: bool = False) -> None:
        if value:
            display = (value[:8] + "...") if secret and len(value) > 8 else value
            checks.add_row(label, "[green]SET[/]", display)
        else:
            checks.add_row(label, "[yellow]MISSING[/]", "")

    chk("CANVAS_ICS_URL", settings.canvas_ics_url, secret=True)
    chk("UCSB_API_KEY", settings.ucsb_api_key, secret=True)
    chk("OPENAI_API_KEY", settings.openai_api_key, secret=True)
    chk("ANTHROPIC_API_KEY", settings.anthropic_api_key, secret=True)
    chk("LLM_PROVIDER", settings.llm_provider)
    chk("LLM_MODEL", settings.llm_model)
    chk("LOCAL_TIMEZONE", settings.local_timezone)

    console.print(checks)


@app.command()
def upcoming(days: int = typer.Option(7, "--days", "-d", help="Days ahead to look")):
    """Show upcoming assignments and events (no LLM)."""
    from gaucho_agent.db import get_session, init_db
    from gaucho_agent.tools.assignments import get_upcoming_assignments

    init_db()
    with get_session() as session:
        result = get_upcoming_assignments(days=days, session=session)

    if result["count"] == 0:
        console.print(f"[yellow]No assignments found in the next {days} days.[/]")
        console.print("Tip: run [cyan]gaucho sync canvas[/] to sync your Canvas feed.")
        return

    table = Table(title=f"Upcoming Assignments (next {days} days)", show_lines=True)
    table.add_column("Title", style="bold")
    table.add_column("Course", style="cyan")
    table.add_column("Due")
    table.add_column("URL")

    for a in result["assignments"]:
        table.add_row(
            a["title"],
            a["course_code"] or "-",
            a["due_at"] or "-",
            a["url"] or "-",
        )

    console.print(table)


@app.command()
def dining():
    """Show dining commons status."""
    from gaucho_agent.db import get_session, init_db
    from gaucho_agent.tools.dining import get_dining_commons_status

    init_db()
    with get_session() as session:
        result = get_dining_commons_status(session=session)

    if not result["commons"]:
        console.print("[yellow]No dining data found.[/]")
        console.print("Tip: run [cyan]gaucho sync dining[/] to sync dining data.")
        return

    table = Table(title=f"Dining Commons — {result['date']}", show_lines=False)
    table.add_column("Name", style="cyan")
    table.add_column("Open Today")
    table.add_column("Sack Meal")
    table.add_column("Take-Out")

    for c in result["commons"]:
        is_open = c["is_open_today"]
        if is_open is True:
            open_str = "[green]Open[/]"
        elif is_open is False:
            open_str = "[red]Closed[/]"
        else:
            open_str = "[dim]Unknown[/]"
        table.add_row(
            c["commons_name"],
            open_str,
            "[green]Yes[/]" if c["has_sack_meal"] else "[dim]No[/]",
            "[green]Yes[/]" if c["has_take_out_meal"] else "[dim]No[/]",
        )

    console.print(table)
    console.print(f"[dim]{result['open_count']} open today · sync dining to refresh[/]")


@app.command()
def plan(when: str = typer.Argument("today", help="Date as YYYY-MM-DD or 'today'")):
    """Show a deterministic daily plan (no LLM)."""
    from gaucho_agent.db import get_session, init_db
    from gaucho_agent.tools.planning import make_daily_plan
    from gaucho_agent.utils.time import today_local

    init_db()
    date_str = None if when == "today" else when

    with get_session() as session:
        result = make_daily_plan(date=date_str, session=session)

    console.print(Panel(f"[bold]Daily Plan – {result['date']}[/] ({result['available_hours']}h available)", expand=False))

    def print_block(label: str, items: list[str]) -> None:
        if items:
            console.print(f"\n[bold cyan]{label}[/]")
            for item in items:
                console.print(f"  - {item}")

    if result["urgent"]:
        console.print("\n[bold red]URGENT[/]")
        for item in result["urgent"]:
            console.print(f"  [red]! {item}[/]")

    print_block("Morning (8am–12pm)", result["morning"])
    print_block("Afternoon (12pm–5pm)", result["afternoon"])
    print_block("Evening (5pm–9pm)", result["evening"])

    if result.get("notes"):
        console.print("\n[dim]Notes:[/]")
        for n in result["notes"]:
            console.print(f"  [dim]- {n}[/]")

    if not any([result["urgent"], result["morning"], result["afternoon"], result["evening"]]):
        console.print("[yellow]No events found.[/] Run [cyan]gaucho sync all[/] first.")


@app.command()
def chat():
    """Interactive chat loop with LLM and tool calling."""
    from gaucho_agent.db import get_session, init_db
    from gaucho_agent.services.tool_executor import TOOL_SCHEMAS, execute_tool

    init_db()

    if not _check_config(require_llm=True):
        raise typer.Exit(1)

    llm = _get_llm_client()

    # Load system prompt
    prompt_path = Path(__file__).parent.parent / "prompts" / "system.txt"
    system_prompt = prompt_path.read_text() if prompt_path.exists() else "You are a UCSB academic assistant."

    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    console.print(Panel("[bold cyan]Gaucho-Agent Chat[/]\nType [bold]exit[/] or [bold]quit[/] to leave.", expand=False))

    with get_session() as session:
        while True:
            try:
                user_input = console.input("\n[bold green]You:[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye![/]")
                break

            if user_input.lower() in {"exit", "quit", "q"}:
                console.print("[dim]Goodbye![/]")
                break

            if not user_input:
                continue

            messages.append({"role": "user", "content": user_input})

            # --- Agentic tool-calling loop ---
            while True:
                response = llm.chat_with_tools(messages, TOOL_SCHEMAS)
                tool_calls = response.get("tool_calls") or []

                if not tool_calls:
                    # Final answer
                    break

                # Execute each tool call
                messages.append(response)
                for tc in tool_calls:
                    fn = tc["function"]
                    name = fn["name"]
                    try:
                        args = json.loads(fn["arguments"])
                    except (json.JSONDecodeError, KeyError):
                        args = {}

                    console.print(f"  [dim]→ calling {name}({args})[/]")
                    tool_result = execute_tool(name, args, session)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": name,
                        "content": json.dumps(tool_result),
                    })

            assistant_text = response.get("content") or ""
            if assistant_text:
                console.print(f"\n[bold blue]Gaucho:[/] {assistant_text}")
            messages.append({"role": "assistant", "content": assistant_text})


# ---------------------------------------------------------------------------
# Sync sub-commands
# ---------------------------------------------------------------------------

@sync_app.command("canvas")
def sync_canvas_cmd():
    """Sync Canvas calendar feed."""
    from gaucho_agent.db import get_session, init_db
    from gaucho_agent.services.sync_canvas import sync_canvas

    init_db()
    _check_config(require_canvas=True)

    console.print("[cyan]Syncing Canvas ICS feed...[/]")
    with get_session() as session:
        run = asyncio.run(sync_canvas(session))
        success, count, error = run.success, run.records_upserted, run.error_text

    if success:
        console.print(f"[green]Canvas sync complete.[/] {count} events upserted.")
    else:
        console.print(f"[red]Canvas sync failed:[/] {error}")


@sync_app.command("dining")
def sync_dining_cmd():
    """Sync UCSB dining data."""
    from gaucho_agent.db import get_session, init_db
    from gaucho_agent.services.sync_dining import sync_dining

    init_db()
    _check_config(require_ucsb=True)

    console.print("[cyan]Syncing UCSB dining data...[/]")
    with get_session() as session:
        run = asyncio.run(sync_dining(session))
        success, count, error = run.success, run.records_upserted, run.error_text

    if success:
        console.print(f"[green]Dining sync complete.[/] {count} records upserted.")
    else:
        console.print(f"[red]Dining sync failed:[/] {error}")


@sync_app.command("academics")
def sync_academics_cmd():
    """Sync UCSB academic calendar and events."""
    from gaucho_agent.db import get_session, init_db
    from gaucho_agent.services.sync_academics import sync_academics

    init_db()
    _check_config(require_ucsb=True)

    console.print("[cyan]Syncing UCSB academic data...[/]")
    with get_session() as session:
        run = asyncio.run(sync_academics(session))
        success, count, error = run.success, run.records_upserted, run.error_text

    if success:
        console.print(f"[green]Academics sync complete.[/] {count} records upserted.")
    else:
        console.print(f"[red]Academics sync failed:[/] {error}")


@sync_app.command("all")
def sync_all_cmd():
    """Sync all data sources."""
    sync_canvas_cmd()
    sync_dining_cmd()
    sync_academics_cmd()


if __name__ == "__main__":
    app()
