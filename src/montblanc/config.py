"""Konfiguration aus .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    data_dir: Path
    output_dir: Path
    state_dir: Path
    graph_tenant_id: str | None
    graph_client_id: str | None
    graph_client_secret: str | None
    teams_team_id: str | None
    teams_channel_id: str | None
    teams_chat_id: str | None
    bot_app_id: str | None
    bot_app_password: str | None
    bot_tenant_id: str | None
    bot_app_type: str
    bot_port: int
    anthropic_api_key: str | None
    anthropic_model: str


def load() -> Config:
    load_dotenv()
    return Config(
        data_dir=Path(os.getenv("DATA_DIR", "./data")).resolve(),
        output_dir=Path(os.getenv("OUTPUT_DIR", "./output")).resolve(),
        state_dir=Path(os.getenv("BOT_STATE_DIR", "./state")).resolve(),
        graph_tenant_id=os.getenv("GRAPH_TENANT_ID"),
        graph_client_id=os.getenv("GRAPH_CLIENT_ID"),
        graph_client_secret=os.getenv("GRAPH_CLIENT_SECRET"),
        teams_team_id=os.getenv("TEAMS_TEAM_ID"),
        teams_channel_id=os.getenv("TEAMS_CHANNEL_ID"),
        teams_chat_id=os.getenv("TEAMS_CHAT_ID"),
        bot_app_id=os.getenv("MICROSOFT_APP_ID"),
        bot_app_password=os.getenv("MICROSOFT_APP_PASSWORD"),
        bot_tenant_id=os.getenv("MICROSOFT_APP_TENANT_ID"),
        bot_app_type=os.getenv("MICROSOFT_APP_TYPE", "SingleTenant"),
        bot_port=int(os.getenv("BOT_PORT", "3978")),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7"),
    )
