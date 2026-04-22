"""Proaktives Senden: Karten/Nachrichten an gespeicherte ConversationReferences."""
from __future__ import annotations

from botbuilder.core import MessageFactory, TurnContext
from botbuilder.integration.aiohttp import CloudAdapter
from botbuilder.schema import Attachment, ConversationReference

from .refs import ConversationReferenceStore


async def send_card(
    adapter: CloudAdapter,
    bot_app_id: str,
    ref: ConversationReference,
    card_attachment: dict,
) -> None:
    async def callback(turn_context: TurnContext) -> None:
        await turn_context.send_activity(
            MessageFactory.attachment(Attachment(**card_attachment))
        )

    await adapter.continue_conversation(ref, callback, bot_app_id)


async def send_text(
    adapter: CloudAdapter,
    bot_app_id: str,
    ref: ConversationReference,
    text: str,
) -> None:
    async def callback(turn_context: TurnContext) -> None:
        await turn_context.send_activity(text)

    await adapter.continue_conversation(ref, callback, bot_app_id)


async def broadcast_card(
    adapter: CloudAdapter,
    bot_app_id: str,
    refs: ConversationReferenceStore,
    card_attachment: dict,
    nur_an: list[str] | None = None,
) -> None:
    for name, ref in refs.all().items():
        if nur_an and name not in nur_an:
            continue
        await send_card(adapter, bot_app_id, ref, card_attachment)
