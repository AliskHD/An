"""TeamsActivityHandler: empfaengt Karten-Submits und Freitext-Meldungen."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

import anthropic
from botbuilder.core import MessageFactory, TurnContext
from botbuilder.core.teams import TeamsActivityHandler, TeamsInfo
from botbuilder.schema import Activity, Attachment

from ..claude_understand import verstehe_meldung
from ..models import Los, Mitarbeiter, Tagesmeldung
from ..parsers import parse_losstaende, parse_qualifikationsmatrix
from . import cards
from .refs import ConversationReferenceStore
from .store import TagesmeldungStore


class MontBlancBot(TeamsActivityHandler):
    """Kern-Handler fuer alle Teams-Interaktionen."""

    def __init__(
        self,
        data_dir: Path,
        refs: ConversationReferenceStore,
        meldungen: TagesmeldungStore,
        anthropic_client: anthropic.Anthropic | None,
        anthropic_model: str,
    ) -> None:
        self._data_dir = data_dir
        self._refs = refs
        self._meldungen = meldungen
        self._anthropic = anthropic_client
        self._model = anthropic_model

    # ---- Helpers ----

    def _load_stammdaten(self) -> tuple[list[Los], list[Mitarbeiter]]:
        lose = parse_losstaende(self._data_dir / "losstaende.md")
        mitarbeiter = parse_qualifikationsmatrix(self._data_dir / "qualifikationsmatrix.md")
        return lose, mitarbeiter

    def _mitarbeiter_fuer(
        self, alle: list[Mitarbeiter], absender_name: str
    ) -> Mitarbeiter | None:
        key = absender_name.strip().casefold()
        for m in alle:
            if m.name.casefold() == key:
                return m
        return None

    # ---- Activity-Events ----

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        activity = turn_context.activity
        absender = activity.from_property.name if activity.from_property else "unbekannt"

        # ConversationReference fuer proaktives Senden merken
        self._refs.capture(turn_context, absender)

        # 1) Karten-Submit (Action.Submit -> Activity mit leerem text + value)
        if activity.value:
            await self._handle_card_submit(turn_context, absender, activity.value)
            return

        # 2) Freitext -> Claude parst -> bei Unklarheit Rueckfrage-Karte
        await self._handle_freetext(turn_context, absender, activity.text or "")

    async def _handle_card_submit(
        self, turn_context: TurnContext, absender: str, value: dict
    ) -> None:
        action = (value or {}).get("action")

        lose, alle_mitarbeiter = self._load_stammdaten()
        mitarbeiter = self._mitarbeiter_fuer(alle_mitarbeiter, absender)

        if action == "request_tagesmeldung":
            if not mitarbeiter:
                await turn_context.send_activity(
                    f"Konnte dich ({absender}) nicht in der Qualifikationsmatrix finden."
                )
                return
            karte = cards.tagesmeldung_card(mitarbeiter, lose)
            await turn_context.send_activity(
                MessageFactory.attachment(Attachment(**karte))
            )
            return

        if action == "tagesmeldung":
            if not mitarbeiter:
                await turn_context.send_activity(
                    f"Ich konnte dich ({absender}) keinem Mitarbeiter zuordnen."
                )
                return
            meldung = Tagesmeldung(
                mitarbeiter=mitarbeiter.name,
                los_nummer=value.get("los_nummer"),
                schritt=value.get("schritt"),
                menge_geschafft=int(value.get("menge_geschafft") or 0) or None,
                rohtext=value.get("bemerkung") or "",
                verstanden=True,
            )
            self._meldungen.add(date.today(), meldung)
            await turn_context.send_activity(
                f"Danke, eingetragen: {meldung.los_nummer} / "
                f"{meldung.schritt} / {meldung.menge_geschafft} Stueck."
            )
            return

        await turn_context.send_activity("Aktion nicht erkannt.")

    async def _handle_freetext(
        self, turn_context: TurnContext, absender: str, text: str
    ) -> None:
        if not text.strip():
            return

        lose, alle_mitarbeiter = self._load_stammdaten()
        mitarbeiter = self._mitarbeiter_fuer(alle_mitarbeiter, absender)
        if not mitarbeiter:
            await turn_context.send_activity(
                f"Hallo {absender}, ich finde dich nicht in der Qualifikationsmatrix – "
                f"bitte meldet euch beim Meister."
            )
            return

        if not self._anthropic:
            # Kein Claude konfiguriert -> einfach die Karte schicken
            karte = cards.tagesmeldung_card(mitarbeiter, lose)
            await turn_context.send_activity(
                MessageFactory.attachment(Attachment(**karte))
            )
            return

        meldung = verstehe_meldung(
            rohtext=text,
            absender=absender,
            mitarbeiter=alle_mitarbeiter,
            lose=lose,
            client=self._anthropic,
            model=self._model,
        )
        meldung.mitarbeiter = mitarbeiter.name

        if meldung.verstanden and meldung.los_nummer and meldung.schritt and meldung.menge_geschafft:
            self._meldungen.add(date.today(), meldung)
            await turn_context.send_activity(
                f"Verstanden: {meldung.los_nummer} / {meldung.schritt} / "
                f"{meldung.menge_geschafft} Stueck. Eingetragen."
            )
            return

        # Unklar -> Rueckfrage als Karte mit Vorbelegung
        karte = cards.rueckfrage_card(
            mitarbeiter=mitarbeiter,
            lose=lose,
            rohtext=text,
            rueckfrage=meldung.rueckfrage or "Kannst du das bitte strukturiert ergaenzen?",
            vorbelegung=meldung,
        )
        await turn_context.send_activity(
            MessageFactory.attachment(Attachment(**karte))
        )

    async def on_members_added_activity(self, members_added, turn_context) -> None:
        for m in members_added:
            if m.id == turn_context.activity.recipient.id:
                continue
            await turn_context.send_activity(
                "Hallo! Schreib mir am Schichtende deine Tagesmeldung – "
                "ich bereite sie strukturiert auf."
            )
