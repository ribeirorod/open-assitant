"""WhatsApp channel adapter using Baileys bridge (WhatsApp Web protocol).

Exposes a FastAPI router that:
  1. Receives inbound messages from the Baileys bridge sidecar (POST).
  2. Forwards them to the Claude agent.
  3. Sends replies back via the Baileys bridge REST API.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Request

from src.agent.core import ask_agent
from src.config import settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])


# ── Baileys bridge client ────────────────────────────────────────────────────

def _bridge_url(path: str) -> str:
    return f"{settings.baileys_bridge_url.rstrip('/')}{path}"


async def _bridge_post(path: str, payload: dict) -> dict | None:
    """POST to the Baileys bridge and return the JSON response."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(_bridge_url(path), json=payload)
            if resp.status_code >= 400:
                log.error("Bridge %s failed: %s %s", path, resp.status_code, resp.text)
                return None
            return resp.json()
    except httpx.HTTPError as exc:
        log.error("Bridge %s error: %s", path, exc)
        return None


# ── Outbound helpers ──────────────────────────────────────────────────────────

async def send_text(to: str, message: str, quoted_id: str | None = None) -> dict | None:
    """Send a text message via the Baileys bridge."""
    payload: dict[str, Any] = {"to": to, "message": message[:65536]}
    if quoted_id:
        payload["quotedId"] = quoted_id
    return await _bridge_post("/send/text", payload)


async def send_media(
    to: str,
    file_path: str,
    caption: str | None = None,
    as_voice: bool = False,
    gif_playback: bool = False,
    mimetype: str | None = None,
) -> dict | None:
    """Send media (image, video, audio, document) via the Baileys bridge."""
    payload: dict[str, Any] = {"to": to, "filePath": file_path}
    if caption:
        payload["caption"] = caption
    if as_voice:
        payload["asVoice"] = True
    if gif_playback:
        payload["gifPlayback"] = True
    if mimetype:
        payload["mimetype"] = mimetype
    return await _bridge_post("/send/media", payload)


async def send_sticker(to: str, file_path: str) -> dict | None:
    """Send a sticker via the Baileys bridge."""
    return await _bridge_post("/send/sticker", {"to": to, "filePath": file_path})


async def send_poll(
    to: str, question: str, options: list[str], selectable_count: int = 0
) -> dict | None:
    """Send a poll via the Baileys bridge."""
    return await _bridge_post("/send/poll", {
        "to": to,
        "question": question,
        "options": options,
        "selectableCount": selectable_count,
    })


async def react(
    chat_jid: str, message_id: str, emoji: str = "", remove: bool = False
) -> dict | None:
    """Add or remove a reaction on a message."""
    return await _bridge_post("/react", {
        "chatJid": chat_jid,
        "messageId": message_id,
        "emoji": emoji,
        "remove": remove,
    })


async def edit_message(chat_jid: str, message_id: str, message: str) -> dict | None:
    """Edit a previously sent message."""
    return await _bridge_post("/edit", {
        "chatJid": chat_jid,
        "messageId": message_id,
        "message": message,
    })


async def unsend_message(chat_jid: str, message_id: str) -> dict | None:
    """Delete/unsend a previously sent message."""
    return await _bridge_post("/unsend", {
        "chatJid": chat_jid,
        "messageId": message_id,
    })


# ── Group management ─────────────────────────────────────────────────────────

async def group_create(name: str, participants: list[str]) -> dict | None:
    return await _bridge_post("/group/create", {"name": name, "participants": participants})


async def group_rename(group_id: str, name: str) -> dict | None:
    return await _bridge_post("/group/rename", {"groupId": group_id, "name": name})


async def group_description(group_id: str, description: str) -> dict | None:
    return await _bridge_post("/group/description", {"groupId": group_id, "description": description})


async def group_participants(
    group_id: str, participants: list[str], action: str
) -> dict | None:
    """Manage group participants. action: 'add' | 'remove' | 'promote' | 'demote'."""
    return await _bridge_post("/group/participants", {
        "groupId": group_id,
        "participants": participants,
        "action": action,
    })


async def group_invite_code(group_id: str) -> dict | None:
    return await _bridge_post("/group/invite-code", {"groupId": group_id})


async def group_revoke_invite(group_id: str) -> dict | None:
    return await _bridge_post("/group/revoke-invite", {"groupId": group_id})


async def group_leave(group_id: str) -> dict | None:
    return await _bridge_post("/group/leave", {"groupId": group_id})


async def group_icon(group_id: str, file_path: str) -> dict | None:
    return await _bridge_post("/group/icon", {"groupId": group_id, "filePath": file_path})


async def group_info(group_id: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_bridge_url(f"/group/info/{group_id}"))
            return resp.json() if resp.status_code < 400 else None
    except httpx.HTTPError as exc:
        log.error("Bridge group info error: %s", exc)
        return None


# ── Inbound message webhook (called by the Baileys bridge) ────────────────────

@router.post("/baileys")
async def inbound_from_bridge(request: Request) -> dict:
    """Receive a message forwarded from the Baileys bridge sidecar."""
    msg = await request.json()

    sender = msg.get("from", "")
    msg_type = msg.get("type", "unknown")
    text = msg.get("text")
    msg_id = msg.get("id")

    # Only process text messages for now; media handling can be added later
    if msg_type != "text" or not text:
        log.debug("ignoring non-text message type=%s from=%s", msg_type, sender)
        return {"status": "ignored"}

    log.info("whatsapp from=%s text=%s", sender, text[:80])

    response = await ask_agent(text, chat_id=f"wa:{sender}")
    await send_text(sender, response, quoted_id=msg_id)

    return {"status": "ok"}


# ── Public notification helper (used by scheduler) ───────────────────────────

async def send_notification(to: str, body: str) -> None:
    """Send a proactive message to a WhatsApp number or JID."""
    await send_text(to, body)
