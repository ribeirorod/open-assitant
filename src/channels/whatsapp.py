"""WhatsApp channel adapter using Meta's Cloud API.

Exposes a FastAPI router that:
  1. Verifies the webhook during setup (GET).
  2. Receives inbound messages (POST), forwards them to the Claude agent,
     and sends the reply back via the Cloud API.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Query, Request, Response

from src.agent.core import ask_agent
from src.config import settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])

GRAPH_API = "https://graph.facebook.com/v21.0"


# ── Webhook verification (GET) ─────────────────────────────────────────────

@router.get("")
async def verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
) -> Response:
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(status_code=403)


# ── Inbound message (POST) ─────────────────────────────────────────────────

@router.post("")
async def inbound(request: Request) -> dict:
    body = await request.json()

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    continue
                sender = msg["from"]
                text = msg["text"]["body"]
                log.info("whatsapp from=%s text=%s", sender, text[:80])

                response = await ask_agent(text, chat_id=f"wa:{sender}")
                await _send_text(sender, response)

    return {"status": "ok"}


# ── Outbound helper ────────────────────────────────────────────────────────

async def _send_text(to: str, body: str) -> None:
    url = f"{GRAPH_API}/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body[:4096]},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            log.error("WhatsApp send failed: %s %s", resp.status_code, resp.text)


async def send_notification(to: str, body: str) -> None:
    """Public helper for the scheduler to push proactive messages."""
    await _send_text(to, body)
