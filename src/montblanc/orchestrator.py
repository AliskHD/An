"""Tagesablauf-Orchestrator.

Ablauf:
1. Stammdaten einlesen.
2. Tagesmeldungen aus dem TagesmeldungStore lesen (hat der Bot im Lauf des Tages
   gefuellt – primaer ueber Adaptive-Cards, Claude nur als Freitext-Fallback).
3. Losstaende gemaess Meldungen fortschreiben.
4. Tagesplan fuer morgen erstellen.
5. Excel exportieren.
6. Proaktiv ueber den Bot als Adaptive-Card in Teams posten.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path

from .bot.app import build_adapter, build_bot
from .bot.cards import tagesplan_card
from .bot.proactive import broadcast_card
from .bot.refs import ConversationReferenceStore
from .bot.store import TagesmeldungStore
from .config import Config
from .excel_export import export_tagesplan
from .models import Mitarbeiter, Tagesmeldung
from .parsers import parse_losstaende, parse_qualifikationsmatrix, parse_stammdaten
from .planer import erstelle_tagesplan, wende_tagesmeldungen_an


def _anwesende(
    alle: list[Mitarbeiter], meldungen: list[Tagesmeldung]
) -> list[Mitarbeiter]:
    gemeldete = {m.mitarbeiter for m in meldungen}
    return [m for m in alle if m.name in gemeldete]


async def _post_plan_in_teams(cfg: Config, karte: dict) -> None:
    if not cfg.bot_app_id:
        print("Info: MICROSOFT_APP_ID nicht gesetzt – Teams-Post uebersprungen.")
        return
    adapter = build_adapter(cfg)
    refs = ConversationReferenceStore(cfg.state_dir / "conversation_refs.json")
    if not refs.all():
        print("Info: keine ConversationReferences gespeichert – niemand hat mit "
              "dem Bot geschrieben. Teams-Post uebersprungen.")
        return
    await broadcast_card(adapter, cfg.bot_app_id, refs, karte)


def run(cfg: Config, tag_meldungen: date | None = None) -> Path:
    tag_meldungen = tag_meldungen or date.today()
    plan_tag = tag_meldungen + timedelta(days=1)

    # 1) Stammdaten
    lose = parse_losstaende(cfg.data_dir / "losstaende.md")
    mitarbeiter = parse_qualifikationsmatrix(cfg.data_dir / "qualifikationsmatrix.md")
    stammdaten = parse_stammdaten(cfg.data_dir / "stammdaten.yaml")

    # 2) Tagesmeldungen aus dem Store
    meldungen_store = TagesmeldungStore(cfg.state_dir / "meldungen")
    meldungen = meldungen_store.list_for(tag_meldungen)

    # 3) Losstaende fortschreiben
    lose_verbleibend = wende_tagesmeldungen_an(lose, meldungen)

    # 4) Tagesplan fuer morgen
    anwesende = _anwesende(mitarbeiter, meldungen) or mitarbeiter
    plan = erstelle_tagesplan(
        datum=plan_tag,
        lose=lose_verbleibend,
        mitarbeiter=anwesende,
        stammdaten=stammdaten,
    )

    # 5) Excel als Archiv
    excel_pfad = cfg.output_dir / f"tagesplan_{plan_tag.isoformat()}.xlsx"
    export_tagesplan(plan, excel_pfad)

    # 6) Teams-Post als Adaptive-Card
    karte = tagesplan_card(plan)
    asyncio.run(_post_plan_in_teams(cfg, karte))

    return excel_pfad
