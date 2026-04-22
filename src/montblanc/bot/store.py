"""Persistenter Tagesmeldung-Store.

Der Bot schreibt eingehende Meldungen hier rein; der Orchestrator liest sie
am Schichtende zur Tagesplanerstellung.
"""
from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

from ..models import Tagesmeldung


class TagesmeldungStore:
    def __init__(self, basis_pfad: Path) -> None:
        self._basis = basis_pfad
        self._lock = threading.Lock()
        self._basis.mkdir(parents=True, exist_ok=True)

    def _pfad(self, tag: date) -> Path:
        return self._basis / f"tagesmeldungen_{tag.isoformat()}.json"

    def add(self, tag: date, meldung: Tagesmeldung) -> None:
        with self._lock:
            pfad = self._pfad(tag)
            liste = json.loads(pfad.read_text(encoding="utf-8")) if pfad.exists() else []
            liste.append(meldung.model_dump(mode="json"))
            pfad.write_text(
                json.dumps(liste, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    def list_for(self, tag: date) -> list[Tagesmeldung]:
        pfad = self._pfad(tag)
        if not pfad.exists():
            return []
        raw = json.loads(pfad.read_text(encoding="utf-8"))
        return [Tagesmeldung.model_validate(r) for r in raw]
