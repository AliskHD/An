"""Minimal-Tests fuer Parser und Planer."""
from datetime import date
from pathlib import Path

from montblanc.parsers import (
    parse_losstaende,
    parse_qualifikationsmatrix,
    parse_stammdaten,
)
from montblanc.planer import erstelle_tagesplan, wende_tagesmeldungen_an
from montblanc.models import Tagesmeldung


DATA = Path(__file__).parent.parent / "data"


def test_parse_losstaende():
    lose = parse_losstaende(DATA / "losstaende.md")
    assert len(lose) == 6
    assert lose[0].nummer == "L-24001"
    assert lose[0].menge == 120


def test_parse_qualifikationsmatrix():
    ma = parse_qualifikationsmatrix(DATA / "qualifikationsmatrix.md")
    assert len(ma) == 6
    anna = next(m for m in ma if m.name == "Anna Becker")
    assert anna.qualifikationen["Drehen"] == 3
    assert anna.kann("Drehen", 2)
    assert not anna.kann("Galvanik", 1)


def test_parse_stammdaten_liest_umlaut_schritt():
    st = parse_stammdaten(DATA / "stammdaten.yaml")
    assert "Prüfung" in st.prozessschritte
    assert st.netto_minuten() == 480


def test_erstelle_tagesplan_weist_alle_lose_zu():
    lose = parse_losstaende(DATA / "losstaende.md")
    ma = parse_qualifikationsmatrix(DATA / "qualifikationsmatrix.md")
    st = parse_stammdaten(DATA / "stammdaten.yaml")
    plan = erstelle_tagesplan(date(2026, 4, 22), lose, ma, st)
    assert len(plan.zuweisungen) >= 6
    assert plan.nicht_eingeplante_lose == []


def test_wende_tagesmeldungen_an_reduziert_losmenge():
    lose = parse_losstaende(DATA / "losstaende.md")
    meldungen = [Tagesmeldung(
        mitarbeiter="Anna Becker",
        los_nummer="L-24001",
        schritt="Polieren",
        menge_geschafft=50,
        verstanden=True,
    )]
    verbleibend = wende_tagesmeldungen_an(lose, meldungen)
    l = next(x for x in verbleibend if x.nummer == "L-24001")
    assert l.menge == 120 - 50
