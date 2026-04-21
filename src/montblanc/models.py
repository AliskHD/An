"""Domaenenmodelle fuer die Tagesplanung."""
from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Prioritaet(str, Enum):
    hoch = "hoch"
    mittel = "mittel"
    niedrig = "niedrig"


class Los(BaseModel):
    nummer: str
    artikel: str
    menge: int
    aktueller_schritt: str
    naechster_schritt: str
    prioritaet: Prioritaet
    deadline: date


class Mitarbeiter(BaseModel):
    name: str
    qualifikationen: dict[str, int] = Field(
        default_factory=dict,
        description="Schritt-Name -> Qualifikationsstufe 0..3",
    )

    def kann(self, schritt: str, min_stufe: int) -> bool:
        return self.qualifikationen.get(schritt, 0) >= min_stufe


class Prozessschritt(BaseModel):
    name: str
    dauer_min_pro_stueck: float
    min_qualifikation: int


class Stammdaten(BaseModel):
    prozessschritte: dict[str, Prozessschritt]
    prozessfolgen: dict[str, list[str]] = Field(default_factory=dict)
    schicht_beginn: time
    schicht_ende: time
    pause_min: int

    def netto_minuten(self) -> int:
        beginn = datetime.combine(date.today(), self.schicht_beginn)
        ende = datetime.combine(date.today(), self.schicht_ende)
        return int((ende - beginn).total_seconds() / 60) - self.pause_min


class Tagesmeldung(BaseModel):
    """Was ein Mitarbeiter am Tagesende gemeldet hat."""
    mitarbeiter: str
    los_nummer: str | None = None
    schritt: str | None = None
    menge_geschafft: int | None = None
    rohtext: str = ""
    verstanden: bool = True
    rueckfrage: str | None = None


class Zuweisung(BaseModel):
    mitarbeiter: str
    los_nummer: str
    artikel: str
    schritt: str
    menge: int
    dauer_min: float
    startzeit: time
    endzeit: time


class Tagesplan(BaseModel):
    datum: date
    zuweisungen: list[Zuweisung]
    nicht_eingeplante_lose: list[str] = Field(default_factory=list)
    freie_mitarbeiter: list[str] = Field(default_factory=list)
