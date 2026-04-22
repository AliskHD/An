"""aiohttp-App fuer den Messaging-Endpoint + Bot-Adapter-Setup."""
from __future__ import annotations

from pathlib import Path

import anthropic
from aiohttp import web
from botbuilder.integration.aiohttp import (
    CloudAdapter,
    ConfigurationBotFrameworkAuthentication,
)
from botbuilder.schema import Activity

from ..config import Config
from .handler import MontBlancBot
from .refs import ConversationReferenceStore
from .store import TagesmeldungStore


class _AuthSettings:
    """Adapter-Shape, die ConfigurationBotFrameworkAuthentication erwartet."""

    def __init__(self, cfg: Config) -> None:
        self.APP_ID = cfg.bot_app_id or ""
        self.APP_PASSWORD = cfg.bot_app_password or ""
        self.APP_TYPE = cfg.bot_app_type
        self.APP_TENANTID = cfg.bot_tenant_id or ""


def build_adapter(cfg: Config) -> CloudAdapter:
    auth = ConfigurationBotFrameworkAuthentication(_AuthSettings(cfg))
    return CloudAdapter(auth)


def build_bot(cfg: Config) -> MontBlancBot:
    refs = ConversationReferenceStore(cfg.state_dir / "conversation_refs.json")
    meldungen = TagesmeldungStore(cfg.state_dir / "meldungen")
    anthropic_client = (
        anthropic.Anthropic() if cfg.anthropic_api_key else None
    )
    return MontBlancBot(
        data_dir=cfg.data_dir,
        refs=refs,
        meldungen=meldungen,
        anthropic_client=anthropic_client,
        anthropic_model=cfg.anthropic_model,
    )


def build_app(cfg: Config) -> web.Application:
    adapter = build_adapter(cfg)
    bot = build_bot(cfg)

    async def messages(req: web.Request) -> web.Response:
        if "application/json" not in (req.headers.get("Content-Type") or ""):
            return web.Response(status=415)
        body = await req.json()
        activity = Activity().deserialize(body)
        auth_header = req.headers.get("Authorization", "")
        response = await adapter.process_activity(auth_header, activity, bot.on_turn)
        if response:
            return web.json_response(data=response.body, status=response.status)
        return web.Response(status=201)

    async def health(_req: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app = web.Application(middlewares=[])
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/health", health)
    app["cfg"] = cfg
    app["adapter"] = adapter
    app["bot"] = bot
    return app


def run_app(cfg: Config) -> None:
    web.run_app(build_app(cfg), host="0.0.0.0", port=cfg.bot_port)
