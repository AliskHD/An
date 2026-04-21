"""Teams-Integration.

Lesen: Microsoft Graph API (App-Auth, Client-Credentials).
  Benoetigte App-Permissions (Admin-Consent):
  - ChannelMessage.Read.All  (wenn Reports in einem Channel)
  - Chat.Read.All            (wenn Reports in einem Gruppen-Chat)

Schreiben: Power Automate Webhook.
  Warum nicht Graph direkt?
  - Chat-Nachrichten per App-Permission erfordern Protected-APIs (Sonderantrag).
  - File-Upload + Kachel in Chat ist mit Power Automate in 3 Schritten machbar:
    1) HTTP-Trigger (JSON + Base64-Datei)
    2) Datei in SharePoint/OneDrive ablegen
    3) Chat-Nachricht mit Link/Kachel senden
  - Flow-URL wird als Secret in .env abgelegt.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import msal


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@dataclass
class TeamsConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    team_id: str | None = None
    channel_id: str | None = None
    chat_id: str | None = None
    power_automate_webhook_url: str | None = None


# ----------------------------- LESEN -----------------------------

class GraphClient:
    def __init__(self, cfg: TeamsConfig):
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
        r = httpx.get(url, headers={"Authorization": f"Bearer {self._get_token()}"}, timeout=30)
        r.raise_for_status()
        return r.json()

    def channel_messages_today(self, tag: date | None = None) -> list[dict]:
        """Holt alle Channel-Nachrichten des Tages."""
        if not (self._cfg.team_id and self._cfg.channel_id):
            raise ValueError("team_id und channel_id muessen gesetzt sein")
        tag = tag or date.today()
        url = (
            f"{GRAPH_BASE}/teams/{self._cfg.team_id}"
            f"/channels/{self._cfg.channel_id}/messages?$top=50"
        )
        data = self._get(url)
        out: list[dict] = []
        for msg in data.get("value", []):
            created = msg.get("createdDateTime")
            if not created:
                continue
            ts = datetime.fromisoformat(created.replace("Z", "+00:00")).date()
            if ts == tag:
                out.append(msg)
        return out

    def chat_messages_today(self, tag: date | None = None) -> list[dict]:
        if not self._cfg.chat_id:
            raise ValueError("chat_id muss gesetzt sein")
        tag = tag or date.today()
        url = f"{GRAPH_BASE}/chats/{self._cfg.chat_id}/messages?$top=50"
        data = self._get(url)
        out: list[dict] = []
        for msg in data.get("value", []):
            created = msg.get("createdDateTime")
            if not created:
                continue
            ts = datetime.fromisoformat(created.replace("Z", "+00:00")).date()
            if ts == tag:
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
        import re
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"\s+", " ", content).strip()
    return absender, content


# ----------------------------- SCHREIBEN -----------------------------

def post_tagesplan(
    cfg: TeamsConfig,
    nachricht: str,
    excel_pfad: Path,
) -> None:
    """Postet Nachricht + Excel-Anhang via Power Automate Webhook."""
    if not cfg.power_automate_webhook_url:
        raise ValueError("POWER_AUTOMATE_WEBHOOK_URL nicht gesetzt")
    payload = {
        "nachricht": nachricht,
        "dateiname": excel_pfad.name,
        "datei_base64": base64.b64encode(excel_pfad.read_bytes()).decode("ascii"),
    }
    r = httpx.post(cfg.power_automate_webhook_url, json=payload, timeout=60)
    r.raise_for_status()


def post_rueckfrage(cfg: TeamsConfig, an_mitarbeiter: str, frage: str) -> None:
    """Postet eine Rueckfrage. Nutzt den gleichen Flow mit leerem Anhang."""
    if not cfg.power_automate_webhook_url:
        raise ValueError("POWER_AUTOMATE_WEBHOOK_URL nicht gesetzt")
    payload = {
        "nachricht": f"@{an_mitarbeiter} {frage}",
        "dateiname": None,
        "datei_base64": None,
    }
    r = httpx.post(cfg.power_automate_webhook_url, json=payload, timeout=30)
    r.raise_for_status()
