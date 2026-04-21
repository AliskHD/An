"""Tagesablauf-Orchestrator.

1. Losstaende, Qualifikationsmatrix, Stammdaten einlesen.
2. Tagesmeldungen aus Teams holen (Channel oder Chat).
3. Jede Meldung von Claude verstehen lassen; unklare -> Rueckfrage in Teams.
4. Losstaende gemaess Meldungen reduzieren.
5. Tagesplan fuer morgen erstellen.
6. Excel erzeugen und in Teams posten.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import anthropic

from . import teams
from .claude_understand import verstehe_meldung
from .config import Config
from .excel_export import export_tagesplan
from .models import Mitarbeiter, Tagesmeldung
from .parsers import parse_losstaende, parse_qualifikationsmatrix, parse_stammdaten
from .planer import erstelle_tagesplan, wende_tagesmeldungen_an


def _teams_config(cfg: Config) -> teams.TeamsConfig:
    return teams.TeamsConfig(
        tenant_id=cfg.graph_tenant_id or "",
        client_id=cfg.graph_client_id or "",
        client_secret=cfg.graph_client_secret or "",
        team_id=cfg.teams_team_id,
        channel_id=cfg.teams_channel_id,
        chat_id=cfg.teams_chat_id,
        power_automate_webhook_url=cfg.power_automate_webhook_url,
    )


def _anwesende(
    alle: list[Mitarbeiter], meldungen: list[Tagesmeldung]
) -> list[Mitarbeiter]:
    gemeldete = {m.mitarbeiter for m in meldungen}
    return [m for m in alle if m.name in gemeldete]


def run(cfg: Config, tag_meldungen: date | None = None) -> Path:
    tag_meldungen = tag_meldungen or date.today()
    plan_tag = tag_meldungen + timedelta(days=1)

    # 1) Stammdaten
    lose = parse_losstaende(cfg.data_dir / "losstaende.md")
    mitarbeiter = parse_qualifikationsmatrix(cfg.data_dir / "qualifikationsmatrix.md")
    stammdaten = parse_stammdaten(cfg.data_dir / "stammdaten.yaml")

    # 2) Teams-Meldungen einlesen
    tcfg = _teams_config(cfg)
    raw_msgs: list[dict] = []
    if tcfg.team_id and tcfg.channel_id:
        graph = teams.GraphClient(tcfg)
        raw_msgs = graph.channel_messages_today(tag_meldungen)

    # 3) Claude verstehen
    anthropic_client = anthropic.Anthropic() if cfg.anthropic_api_key else None
    meldungen: list[Tagesmeldung] = []
    for msg in raw_msgs:
        absender, text = teams.extract_report_text(msg)
        if not text.strip():
            continue
        if anthropic_client:
            m = verstehe_meldung(
                rohtext=text,
                absender=absender,
                mitarbeiter=mitarbeiter,
                lose=lose,
                client=anthropic_client,
                model=cfg.anthropic_model,
            )
        else:
            m = Tagesmeldung(mitarbeiter=absender, rohtext=text, verstanden=False,
                             rueckfrage="Ich kann gerade nicht verstehen, "
                                         "bitte nenne Los-Nr., Schritt und Menge.")
        meldungen.append(m)

        if not m.verstanden and m.rueckfrage and tcfg.power_automate_webhook_url:
            try:
                teams.post_rueckfrage(tcfg, m.mitarbeiter, m.rueckfrage)
            except Exception as e:
                print(f"Warnung: Rueckfrage an {m.mitarbeiter} fehlgeschlagen: {e}")

    # 4) Losstaende fortschreiben
    lose_verbleibend = wende_tagesmeldungen_an(lose, meldungen)

    # 5) Tagesplan fuer morgen
    anwesende = _anwesende(mitarbeiter, meldungen) or mitarbeiter
    plan = erstelle_tagesplan(
        datum=plan_tag,
        lose=lose_verbleibend,
        mitarbeiter=anwesende,
        stammdaten=stammdaten,
    )

    # 6) Excel + Teams-Post
    excel_pfad = cfg.output_dir / f"tagesplan_{plan_tag.isoformat()}.xlsx"
    export_tagesplan(plan, excel_pfad)

    if tcfg.power_automate_webhook_url:
        try:
            teams.post_tagesplan(
                tcfg,
                nachricht=(
                    f"Tagesplan Mont Blanc fuer {plan_tag.isoformat()}: "
                    f"{len(plan.zuweisungen)} Zuweisungen, "
                    f"{len(plan.nicht_eingeplante_lose)} Hinweise."
                ),
                excel_pfad=excel_pfad,
            )
        except Exception as e:
            print(f"Warnung: Teams-Post fehlgeschlagen: {e}")

    return excel_pfad
