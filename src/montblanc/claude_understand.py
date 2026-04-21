"""Verstehen unklarer Tagesmeldungen via Claude API.

Nutzt structured outputs (pydantic + messages.parse) um freie Teams-Texte
wie "Anna hat heute L-24001 poliert, ca. 100 Stueck geschafft" in
strukturierte Felder zu ueberfuehren und Rueckfragen zu formulieren,
wenn etwas fehlt.
"""
from __future__ import annotations

import os
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from .models import Los, Mitarbeiter, Tagesmeldung


_SYSTEM_PROMPT = """Du bist Assistent fuer die Mont Blanc Fertigungsabteilung.
Mitarbeiter melden im Teams-Chat am Tagesende, was sie geschafft haben.
Deine Aufgabe: extrahiere strukturiert:
- mitarbeiter: Name des Mitarbeiters
- los_nummer: z.B. "L-24001" (Format L-XXXXX)
- schritt: einer der bekannten Prozessschritte
- menge_geschafft: Anzahl Stueck

Wenn eine Information fehlt, nicht eindeutig ist oder der Losstand unplausibel
ist: setze "verstanden": false und formuliere in "rueckfrage" eine freundliche,
kurze Rueckfrage auf Deutsch (du, nicht Sie), die genau die fehlende Information
klaert. Keine Floskeln, direkt die Frage.
"""


class _ClaudeAntwort(BaseModel):
    mitarbeiter: str | None = Field(default=None)
    los_nummer: str | None = Field(default=None)
    schritt: str | None = Field(default=None)
    menge_geschafft: int | None = Field(default=None)
    verstanden: bool
    rueckfrage: str | None = Field(default=None)


def _kontext_block(mitarbeiter: list[Mitarbeiter], lose: list[Los]) -> str:
    namen = ", ".join(sorted(m.name for m in mitarbeiter))
    schritte = sorted({s for m in mitarbeiter for s in m.qualifikationen.keys()})
    lose_kurz = ", ".join(sorted(l.nummer for l in lose))
    return (
        f"Bekannte Mitarbeiter: {namen}\n"
        f"Bekannte Prozessschritte: {', '.join(schritte)}\n"
        f"Aktive Lose: {lose_kurz}\n"
    )


def verstehe_meldung(
    rohtext: str,
    absender: str,
    mitarbeiter: list[Mitarbeiter],
    lose: list[Los],
    client: anthropic.Anthropic | None = None,
    model: str | None = None,
) -> Tagesmeldung:
    client = client or anthropic.Anthropic()
    model = model or os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7")

    kontext = _kontext_block(mitarbeiter, lose)

    # cache_control auf den Kontextblock -> Stammdaten werden gecached,
    # nur der eigentliche Meldungstext aendert sich pro Anfrage.
    response = client.messages.parse(
        model=model,
        max_tokens=1024,
        system=[
            {"type": "text", "text": _SYSTEM_PROMPT},
            {"type": "text", "text": kontext, "cache_control": {"type": "ephemeral"}},
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Absender im Teams-Chat: {absender}\n"
                    f"Nachricht: {rohtext}"
                ),
            }
        ],
        output_format=_ClaudeAntwort,
    )

    a: _ClaudeAntwort = response.parsed_output

    return Tagesmeldung(
        mitarbeiter=a.mitarbeiter or absender,
        los_nummer=a.los_nummer,
        schritt=a.schritt,
        menge_geschafft=a.menge_geschafft,
        rohtext=rohtext,
        verstanden=a.verstanden,
        rueckfrage=a.rueckfrage,
    )
