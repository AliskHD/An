"""Markdown-Parser fuer Losstaende und Qualifikationsmatrix."""
from __future__ import annotations

import re
from datetime import date, datetime, time
from pathlib import Path

import yaml

from .models import (
    Los,
    Mitarbeiter,
    Prioritaet,
    Prozessschritt,
    Stammdaten,
)

_TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")


def _table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        m = _TABLE_ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        # Trennerzeile (---) ueberspringen
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    return rows


def parse_losstaende(pfad: Path) -> list[Los]:
    rows = _table_rows(pfad.read_text(encoding="utf-8"))
    if not rows:
        return []
    header = [h.lower() for h in rows[0]]
    idx = {
        "nummer": header.index("los-nr."),
        "artikel": header.index("artikel"),
        "menge": header.index("menge"),
        "aktuell": header.index("aktueller schritt"),
        "naechster": header.index("nächster schritt"),
        "prio": header.index("priorität"),
        "deadline": header.index("deadline"),
    }
    lose: list[Los] = []
    for row in rows[1:]:
        lose.append(
            Los(
                nummer=row[idx["nummer"]],
                artikel=row[idx["artikel"]],
                menge=int(row[idx["menge"]]),
                aktueller_schritt=row[idx["aktuell"]],
                naechster_schritt=row[idx["naechster"]],
                prioritaet=Prioritaet(row[idx["prio"]].lower()),
                deadline=date.fromisoformat(row[idx["deadline"]]),
            )
        )
    return lose


def parse_qualifikationsmatrix(pfad: Path) -> list[Mitarbeiter]:
    rows = _table_rows(pfad.read_text(encoding="utf-8"))
    if not rows:
        return []
    header = rows[0]
    schritte = header[1:]
    mitarbeiter: list[Mitarbeiter] = []
    for row in rows[1:]:
        name = row[0]
        qual = {schritte[i]: int(row[i + 1]) for i in range(len(schritte))}
        mitarbeiter.append(Mitarbeiter(name=name, qualifikationen=qual))
    return mitarbeiter


def parse_stammdaten(pfad: Path) -> Stammdaten:
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    schritte = {
        name: Prozessschritt(name=name, **cfg)
        for name, cfg in daten["prozessschritte"].items()
    }
    return Stammdaten(
        prozessschritte=schritte,
        prozessfolgen=daten.get("prozessfolgen", {}),
        schicht_beginn=_parse_time(daten["schicht"]["beginn"]),
        schicht_ende=_parse_time(daten["schicht"]["ende"]),
        pause_min=int(daten["schicht"]["pause_min"]),
    )


def _parse_time(wert: str) -> time:
    return datetime.strptime(wert, "%H:%M").time()
