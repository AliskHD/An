"""Persistiert ConversationReferences pro Mitarbeiter fuer proaktives Senden."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from botbuilder.core import TurnContext
from botbuilder.schema import ConversationReference


class ConversationReferenceStore:
    def __init__(self, pfad: Path) -> None:
        self._pfad = pfad
        self._lock = threading.Lock()
        self._pfad.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, dict]:
        if not self._pfad.exists():
            return {}
        return json.loads(self._pfad.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, dict]) -> None:
        self._pfad.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def upsert(self, name: str, ref: ConversationReference) -> None:
        with self._lock:
            data = self._load()
            data[name] = ref.serialize()
            self._save(data)

    def get(self, name: str) -> ConversationReference | None:
        raw = self._load().get(name)
        return ConversationReference().deserialize(raw) if raw else None

    def all(self) -> dict[str, ConversationReference]:
        return {k: ConversationReference().deserialize(v) for k, v in self._load().items()}

    def capture(self, turn_context: TurnContext, name: str) -> None:
        self.upsert(name, TurnContext.get_conversation_reference(turn_context.activity))
