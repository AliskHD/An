"""Tests fuer TagesmeldungStore und Adaptive-Card-Templates."""
from datetime import date
from pathlib import Path

from montblanc.bot.cards import (
    prompt_tagesmeldung_card,
    rueckfrage_card,
    tagesmeldung_card,
    tagesplan_card,
)
from montblanc.bot.store import TagesmeldungStore
from montblanc.models import Mitarbeiter, Tagesmeldung
from montblanc.parsers import (
    parse_losstaende,
    parse_qualifikationsmatrix,
    parse_stammdaten,
)
from montblanc.planer import erstelle_tagesplan


DATA = Path(__file__).parent.parent / "data"


def test_tagesmeldung_store_roundtrip(tmp_path):
    store = TagesmeldungStore(tmp_path)
    tag = date(2026, 4, 22)
    m = Tagesmeldung(
        mitarbeiter="Anna Becker",
        los_nummer="L-24001",
        schritt="Polieren",
        menge_geschafft=120,
        verstanden=True,
    )
    store.add(tag, m)
    store.add(tag, m)
    gelesen = store.list_for(tag)
    assert len(gelesen) == 2
    assert gelesen[0].mitarbeiter == "Anna Becker"
    assert gelesen[0].los_nummer == "L-24001"


def test_tagesmeldung_card_filtert_schritte_nach_quali():
    mitarbeiter = parse_qualifikationsmatrix(DATA / "qualifikationsmatrix.md")
    lose = parse_losstaende(DATA / "losstaende.md")
    david = next(m for m in mitarbeiter if m.name.startswith("David"))
    card = tagesmeldung_card(david, lose)
    schritt_input = next(
        b for b in card["content"]["body"] if b.get("id") == "schritt"
    )
    schritt_values = {c["value"] for c in schritt_input["choices"]}
    # David hat nur Drehen, Pruefung, Lackieren, Trocknen, Laserbeschriftung >= 2
    assert "Galvanik" not in schritt_values
    assert "Drehen" in schritt_values


def test_tagesplan_card_rendert_alle_zuweisungen():
    lose = parse_losstaende(DATA / "losstaende.md")
    ma = parse_qualifikationsmatrix(DATA / "qualifikationsmatrix.md")
    st = parse_stammdaten(DATA / "stammdaten.yaml")
    plan = erstelle_tagesplan(date(2026, 4, 22), lose, ma, st)
    card = tagesplan_card(plan)
    columnsets = [
        b for b in card["content"]["body"] if b["type"] == "ColumnSet"
    ]
    # Header + pro Zuweisung eine Zeile
    assert len(columnsets) == 1 + len(plan.zuweisungen)


def test_rueckfrage_card_belegt_vor():
    mitarbeiter = parse_qualifikationsmatrix(DATA / "qualifikationsmatrix.md")
    lose = parse_losstaende(DATA / "losstaende.md")
    anna = next(m for m in mitarbeiter if m.name.startswith("Anna"))
    vorbelegung = Tagesmeldung(
        mitarbeiter="Anna Becker",
        los_nummer="L-24001",
        schritt=None,
        menge_geschafft=50,
        verstanden=False,
        rueckfrage="Welchen Schritt?",
    )
    card = rueckfrage_card(
        mitarbeiter=anna, lose=lose,
        rohtext="L-24001 50 Stueck",
        rueckfrage="Welchen Schritt?",
        vorbelegung=vorbelegung,
    )
    los_input = next(b for b in card["content"]["body"] if b.get("id") == "los_nummer")
    assert los_input["value"] == "L-24001"
    menge_input = next(b for b in card["content"]["body"] if b.get("id") == "menge_geschafft")
    assert menge_input["value"] == 50


def test_prompt_card_hat_submit_action():
    card = prompt_tagesmeldung_card()
    assert card["content"]["actions"][0]["type"] == "Action.Submit"
