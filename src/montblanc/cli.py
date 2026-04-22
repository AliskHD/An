"""CLI fuer den Tagesplan-Workflow."""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from pathlib import Path

import click

from . import config as cfg_module
from .excel_export import export_tagesplan
from .orchestrator import run
from .parsers import parse_losstaende, parse_qualifikationsmatrix, parse_stammdaten
from .planer import erstelle_tagesplan


@click.group()
def main() -> None:
    """Mont Blanc Tagesplanung."""


@main.command()
@click.option("--tag", type=str, default=None, help="Meldungstag YYYY-MM-DD (Default: heute)")
def tagesablauf(tag: str | None) -> None:
    """Tagesablauf: Meldungen aus Store -> Plan -> Excel -> Teams-Post via Bot."""
    cfg = cfg_module.load()
    tag_date = datetime.strptime(tag, "%Y-%m-%d").date() if tag else date.today()
    pfad = run(cfg, tag_meldungen=tag_date)
    click.echo(f"Tagesplan erstellt: {pfad}")


@main.command()
@click.option("--datum", type=str, default=None, help="Plan-Datum YYYY-MM-DD (Default: heute)")
def nur_plan(datum: str | None) -> None:
    """Nur Tagesplan aus den .md-Dateien generieren (ohne Teams/Claude)."""
    cfg = cfg_module.load()
    plan_tag = datetime.strptime(datum, "%Y-%m-%d").date() if datum else date.today()

    lose = parse_losstaende(cfg.data_dir / "losstaende.md")
    mitarbeiter = parse_qualifikationsmatrix(cfg.data_dir / "qualifikationsmatrix.md")
    stammdaten = parse_stammdaten(cfg.data_dir / "stammdaten.yaml")

    plan = erstelle_tagesplan(plan_tag, lose, mitarbeiter, stammdaten)
    pfad = cfg.output_dir / f"tagesplan_{plan_tag.isoformat()}.xlsx"
    export_tagesplan(plan, pfad)
    click.echo(f"{len(plan.zuweisungen)} Zuweisungen, "
               f"{len(plan.nicht_eingeplante_lose)} Hinweise -> {pfad}")


@main.group()
def bot() -> None:
    """Teams-Bot-Befehle."""


@bot.command("serve")
def bot_serve() -> None:
    """Startet den Messaging-Endpoint (aiohttp, /api/messages)."""
    from .bot.app import run_app
    cfg = cfg_module.load()
    click.echo(f"Bot laeuft auf http://0.0.0.0:{cfg.bot_port}/api/messages")
    run_app(cfg)


@bot.command("prompt-tagesmeldung")
def bot_prompt() -> None:
    """Fordert alle gespeicherten Mitarbeiter proaktiv zur Tagesmeldung auf."""
    from .bot.app import build_adapter
    from .bot.cards import prompt_tagesmeldung_card
    from .bot.proactive import broadcast_card
    from .bot.refs import ConversationReferenceStore

    cfg = cfg_module.load()
    if not cfg.bot_app_id:
        raise click.ClickException("MICROSOFT_APP_ID nicht gesetzt.")
    adapter = build_adapter(cfg)
    refs = ConversationReferenceStore(cfg.state_dir / "conversation_refs.json")
    karte = prompt_tagesmeldung_card()
    asyncio.run(broadcast_card(adapter, cfg.bot_app_id, refs, karte))
    click.echo(f"Aufforderung an {len(refs.all())} Mitarbeiter gesendet.")


if __name__ == "__main__":
    main()
