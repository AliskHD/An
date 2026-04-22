"""Microsoft-Graph-Lese-Pfad (Fallback).

Der Bot (siehe montblanc.bot) empfaengt Nachrichten live ueber den
Messaging-Endpoint und ist der primaere Eingangsweg. Die Graph-API wird
nur noch genutzt, wenn man z.B. am Abend einen Backfill machen moechte
oder Mitarbeiter noch nicht mit dem Bot interagiert haben.

Schreiben laeuft komplett ueber den Bot (Bot Framework + Adaptive Cards) –
hier gibt es bewusst keine Schreibfunktionen mehr.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx
import msal


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@dataclass
class GraphConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    team_id: str | None = None
    channel_id: str | None = None
    chat_id: str | None = None


class GraphClient:
    def __init__(self, cfg: GraphConfig):
        self._cfg = cfg
        self._app = msal.ConfidentialClientApplication(
            cfg.client_id,
            authority=f"https://login.microsoftonline.com/{cfg.tenant_id}",
            client_credential=cfg.client_secret,
        )
        self._token: str | None = None
        self._token_exp: datetime | None = None

    def _get_token(self) -> str:
        if self._token and self._token_exp and datetime.now(timezone.utc) < self._token_exp:
            return self._token
        result = self._app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(f"MSAL-Fehler: {result.get('error_description')}")
        self._token = result["access_token"]
        self._token_exp = datetime.now(timezone.utc) + timedelta(
            seconds=int(result.get("expires_in", 3600)) - 60
        )
        return self._token

    def _get(self, url: str) -> dict:
        r = httpx.get(
            url, headers={"Authorization": f"Bearer {self._get_token()}"}, timeout=30
        )
        r.raise_for_status()
        return r.json()

    def channel_messages_today(self, tag: date | None = None) -> list[dict]:
        if not (self._cfg.team_id and self._cfg.channel_id):
            raise ValueError("team_id und channel_id muessen gesetzt sein")
        tag = tag or date.today()
        url = (
            f"{GRAPH_BASE}/teams/{self._cfg.team_id}"
            f"/channels/{self._cfg.channel_id}/messages?$top=50"
        )
        return self._filter_by_day(self._get(url).get("value", []), tag)

    def chat_messages_today(self, tag: date | None = None) -> list[dict]:
        if not self._cfg.chat_id:
            raise ValueError("chat_id muss gesetzt sein")
        tag = tag or date.today()
        url = f"{GRAPH_BASE}/chats/{self._cfg.chat_id}/messages?$top=50"
        return self._filter_by_day(self._get(url).get("value", []), tag)

    @staticmethod
    def _filter_by_day(msgs: list[dict], tag: date) -> list[dict]:
        out: list[dict] = []
        for msg in msgs:
            created = msg.get("createdDateTime")
            if not created:
                continue
            if datetime.fromisoformat(created.replace("Z", "+00:00")).date() == tag:
                out.append(msg)
        return out


def extract_report_text(msg: dict) -> tuple[str, str]:
    """Gibt (Absender, Plaintext) zurueck."""
    absender = (
        msg.get("from", {}).get("user", {}).get("displayName")
        or msg.get("from", {}).get("application", {}).get("displayName")
        or "unbekannt"
    )
    body = msg.get("body", {}) or {}
    content = body.get("content", "") or ""
    if body.get("contentType") == "html":
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"\s+", " ", content).strip()
    return absender, content
