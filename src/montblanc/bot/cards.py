"""Adaptive-Card-Templates fuer Tagesmeldung, Rueckfrage und Tagesplan."""
from __future__ import annotations

from datetime import date
from typing import Any

from ..models import Los, Mitarbeiter, Tagesmeldung, Tagesplan


ADAPTIVE_CARD_CONTENT_TYPE = "application/vnd.microsoft.card.adaptive"


def _attachment(body: list[dict], actions: list[dict] | None = None) -> dict:
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": body,
    }
    if actions:
        card["actions"] = actions
    return {"contentType": ADAPTIVE_CARD_CONTENT_TYPE, "content": card}


def _schritt_choices_fuer(mitarbeiter: Mitarbeiter, min_stufe: int = 2) -> list[dict]:
    return [
        {"title": name, "value": name}
        for name, stufe in sorted(mitarbeiter.qualifikationen.items())
        if stufe >= min_stufe
    ]


def _los_choices(lose: list[Los]) -> list[dict]:
    return [
        {"title": f"{l.nummer}  –  {l.artikel}  ({l.menge} offen)", "value": l.nummer}
        for l in lose
    ]


def tagesmeldung_card(
    mitarbeiter: Mitarbeiter,
    lose: list[Los],
    prefill: Tagesmeldung | None = None,
) -> dict:
    """Karte, mit der ein Mitarbeiter seine Tagesleistung strukturiert meldet."""
    body: list[dict] = [
        {
            "type": "TextBlock",
            "size": "Medium",
            "weight": "Bolder",
            "text": f"Tagesmeldung – {mitarbeiter.name}",
        },
        {
            "type": "TextBlock",
            "wrap": True,
            "isSubtle": True,
            "text": "Bitte waehle Los, Schritt und gemeldete Menge. Mehrere Meldungen einfach nacheinander abschicken.",
        },
        {
            "type": "Input.ChoiceSet",
            "id": "los_nummer",
            "label": "Los-Nr.",
            "placeholder": "Los auswaehlen",
            "isRequired": True,
            "errorMessage": "Los fehlt",
            "value": prefill.los_nummer if prefill and prefill.los_nummer else None,
            "choices": _los_choices(lose),
        },
        {
            "type": "Input.ChoiceSet",
            "id": "schritt",
            "label": "Prozessschritt",
            "placeholder": "Schritt auswaehlen",
            "isRequired": True,
            "errorMessage": "Schritt fehlt",
            "value": prefill.schritt if prefill and prefill.schritt else None,
            "choices": _schritt_choices_fuer(mitarbeiter),
        },
        {
            "type": "Input.Number",
            "id": "menge_geschafft",
            "label": "Menge (Stueck)",
            "min": 1,
            "isRequired": True,
            "errorMessage": "Menge fehlt",
            "value": prefill.menge_geschafft if prefill and prefill.menge_geschafft else None,
        },
        {
            "type": "Input.Text",
            "id": "bemerkung",
            "label": "Bemerkung (optional)",
            "isMultiline": True,
        },
    ]
    actions = [{
        "type": "Action.Submit",
        "title": "Meldung senden",
        "data": {"action": "tagesmeldung"},
    }]
    return _attachment(body, actions)


def rueckfrage_card(
    mitarbeiter: Mitarbeiter,
    lose: list[Los],
    rohtext: str,
    rueckfrage: str,
    vorbelegung: Tagesmeldung,
) -> dict:
    """Karte, wenn Claude die Freitext-Meldung nicht eindeutig verstanden hat."""
    body: list[dict] = [
        {
            "type": "TextBlock",
            "size": "Medium",
            "weight": "Bolder",
            "text": f"Kurze Rueckfrage – {mitarbeiter.name}",
        },
        {
            "type": "TextBlock",
            "wrap": True,
            "text": rueckfrage,
        },
        {
            "type": "TextBlock",
            "isSubtle": True,
            "wrap": True,
            "text": f"Deine Nachricht: “{rohtext}”",
        },
        {
            "type": "Input.ChoiceSet",
            "id": "los_nummer",
            "label": "Los-Nr.",
            "isRequired": True,
            "value": vorbelegung.los_nummer,
            "choices": _los_choices(lose),
        },
        {
            "type": "Input.ChoiceSet",
            "id": "schritt",
            "label": "Schritt",
            "isRequired": True,
            "value": vorbelegung.schritt,
            "choices": _schritt_choices_fuer(mitarbeiter),
        },
        {
            "type": "Input.Number",
            "id": "menge_geschafft",
            "label": "Menge",
            "min": 1,
            "isRequired": True,
            "value": vorbelegung.menge_geschafft,
        },
    ]
    actions = [{
        "type": "Action.Submit",
        "title": "Bestaetigen",
        "data": {"action": "tagesmeldung"},
    }]
    return _attachment(body, actions)


def tagesplan_card(plan: Tagesplan) -> dict:
    """Kompakter Tagesplan als In-Chat-Karte."""
    tabelle: list[dict] = [{
        "type": "TextBlock",
        "size": "Large",
        "weight": "Bolder",
        "text": f"Tagesplan – {plan.datum.isoformat()}",
    }, {
        "type": "TextBlock",
        "isSubtle": True,
        "text": f"{len(plan.zuweisungen)} Zuweisungen"
                f"{f', {len(plan.nicht_eingeplante_lose)} Hinweise' if plan.nicht_eingeplante_lose else ''}",
    }]

    # Header
    header = {
        "type": "ColumnSet",
        "columns": [
            {"type": "Column", "width": 2, "items": [
                {"type": "TextBlock", "text": "Mitarbeiter", "weight": "Bolder"}]},
            {"type": "Column", "width": 1, "items": [
                {"type": "TextBlock", "text": "Los", "weight": "Bolder"}]},
            {"type": "Column", "width": 2, "items": [
                {"type": "TextBlock", "text": "Schritt", "weight": "Bolder"}]},
            {"type": "Column", "width": 1, "items": [
                {"type": "TextBlock", "text": "Menge", "weight": "Bolder"}]},
            {"type": "Column", "width": 1, "items": [
                {"type": "TextBlock", "text": "Zeit", "weight": "Bolder"}]},
        ],
    }
    tabelle.append(header)

    for z in plan.zuweisungen:
        tabelle.append({
            "type": "ColumnSet",
            "separator": True,
            "columns": [
                {"type": "Column", "width": 2, "items": [
                    {"type": "TextBlock", "text": z.mitarbeiter, "wrap": True}]},
                {"type": "Column", "width": 1, "items": [
                    {"type": "TextBlock", "text": z.los_nummer}]},
                {"type": "Column", "width": 2, "items": [
                    {"type": "TextBlock", "text": z.schritt, "wrap": True}]},
                {"type": "Column", "width": 1, "items": [
                    {"type": "TextBlock", "text": str(z.menge)}]},
                {"type": "Column", "width": 1, "items": [
                    {"type": "TextBlock",
                     "text": f"{z.startzeit.strftime('%H:%M')}–{z.endzeit.strftime('%H:%M')}"}]},
            ],
        })

    if plan.nicht_eingeplante_lose:
        tabelle.append({"type": "TextBlock", "text": "Hinweise",
                         "weight": "Bolder", "spacing": "Large"})
        for h in plan.nicht_eingeplante_lose:
            tabelle.append({"type": "TextBlock", "text": f"• {h}", "wrap": True})

    if plan.freie_mitarbeiter:
        tabelle.append({"type": "TextBlock",
                         "text": f"Frei: {', '.join(plan.freie_mitarbeiter)}",
                         "isSubtle": True, "spacing": "Medium"})

    return _attachment(tabelle)


def prompt_tagesmeldung_card() -> dict:
    """Sammel-Aufforderung im Channel, die jeder via Bot-Reply individuell bekommt."""
    body = [
        {"type": "TextBlock", "size": "Medium", "weight": "Bolder",
         "text": "Tagesmeldung faellig"},
        {"type": "TextBlock", "wrap": True,
         "text": "Bitte meldet bis Schichtende, was ihr geschafft habt. "
                 "Wer auf 'Meldung abgeben' klickt, bekommt die Karte persoenlich."},
    ]
    actions = [{
        "type": "Action.Submit",
        "title": "Meldung abgeben",
        "data": {"action": "request_tagesmeldung"},
    }]
    return _attachment(body, actions)
