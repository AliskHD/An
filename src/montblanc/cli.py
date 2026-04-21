"""CLI fuer den Tagesplan-Workflow."""
from __future__ import annotations

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
    """Kompletter Ablauf: Teams lesen, Claude verstehen, Plan fuer morgen, Excel + Teams-Post."""
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


if __name__ == "__main__":
    main()
