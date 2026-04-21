"""Tagesplan-Generator.

Strategie:
- Lose werden nach Prioritaet + Deadline sortiert.
- Fuer jeden Los wird der naechste auszufuehrende Schritt bestimmt.
- Qualifizierte, noch nicht voll ausgelastete Mitarbeiter werden zugewiesen.
- Die zugeteilte Menge wird durch die verfuegbare Restzeit des Mitarbeiters begrenzt.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from .models import (
    Los,
    Mitarbeiter,
    Prioritaet,
    Stammdaten,
    Tagesplan,
    Zuweisung,
)

_PRIO_RANK = {Prioritaet.hoch: 0, Prioritaet.mittel: 1, Prioritaet.niedrig: 2}


def _los_rank(los: Los) -> tuple[int, date]:
    return (_PRIO_RANK[los.prioritaet], los.deadline)


def erstelle_tagesplan(
    datum: date,
    lose: Iterable[Los],
    mitarbeiter: Iterable[Mitarbeiter],
    stammdaten: Stammdaten,
) -> Tagesplan:
    lose_sortiert = sorted(lose, key=_los_rank)
    mitarbeiter_liste = list(mitarbeiter)

    netto_min = stammdaten.netto_minuten()
    rest_min: dict[str, float] = {m.name: float(netto_min) for m in mitarbeiter_liste}
    naechste_start: dict[str, datetime] = {
        m.name: datetime.combine(datum, stammdaten.schicht_beginn)
        for m in mitarbeiter_liste
    }

    zuweisungen: list[Zuweisung] = []
    offene_mengen: dict[str, int] = {los.nummer: los.menge for los in lose_sortiert}
    nicht_eingeplant: list[str] = []

    for los in lose_sortiert:
        schritt_name = los.naechster_schritt
        schritt = stammdaten.prozessschritte.get(schritt_name)
        if schritt is None:
            nicht_eingeplant.append(
                f"{los.nummer}: Schritt '{schritt_name}' nicht in Stammdaten"
            )
            continue

        # Mitarbeiter nach Qualifikation absteigend sortieren, dann nach Restzeit
        kandidaten = sorted(
            (m for m in mitarbeiter_liste
             if m.kann(schritt_name, schritt.min_qualifikation)),
            key=lambda m: (-m.qualifikationen.get(schritt_name, 0), -rest_min[m.name]),
        )
        if not kandidaten:
            nicht_eingeplant.append(
                f"{los.nummer}: kein qualifizierter Mitarbeiter fuer '{schritt_name}'"
            )
            continue

        for kandidat in kandidaten:
            if offene_mengen[los.nummer] <= 0:
                break
            verfuegbar = rest_min[kandidat.name]
            if verfuegbar <= 0:
                continue
            max_stueck = int(verfuegbar // schritt.dauer_min_pro_stueck)
            if max_stueck <= 0:
                continue
            menge = min(max_stueck, offene_mengen[los.nummer])
            dauer = menge * schritt.dauer_min_pro_stueck
            start_dt = naechste_start[kandidat.name]
            end_dt = start_dt + timedelta(minutes=dauer)

            zuweisungen.append(
                Zuweisung(
                    mitarbeiter=kandidat.name,
                    los_nummer=los.nummer,
                    artikel=los.artikel,
                    schritt=schritt_name,
                    menge=menge,
                    dauer_min=round(dauer, 1),
                    startzeit=start_dt.time(),
                    endzeit=end_dt.time(),
                )
            )
            rest_min[kandidat.name] -= dauer
            naechste_start[kandidat.name] = end_dt
            offene_mengen[los.nummer] -= menge

        if offene_mengen[los.nummer] > 0:
            nicht_eingeplant.append(
                f"{los.nummer}: {offene_mengen[los.nummer]} Stueck ohne Kapazitaet"
            )

    freie = [m.name for m in mitarbeiter_liste if rest_min[m.name] >= netto_min]

    return Tagesplan(
        datum=datum,
        zuweisungen=zuweisungen,
        nicht_eingeplante_lose=nicht_eingeplant,
        freie_mitarbeiter=freie,
    )


def wende_tagesmeldungen_an(lose: list[Los], meldungen: list) -> list[Los]:
    """Reduziert Losmengen basierend auf gemeldeten Tagesleistungen."""
    lose_map = {los.nummer: los for los in lose}
    for m in meldungen:
        if not m.verstanden or not m.los_nummer or not m.menge_geschafft:
            continue
        los = lose_map.get(m.los_nummer)
        if los is None:
            continue
        los.menge = max(0, los.menge - m.menge_geschafft)
    return [los for los in lose if los.menge > 0]
