from __future__ import annotations

import httpx

from ..core.config import settings


class WhatsAppClient:
    def __init__(self) -> None:
        self.token = settings.whatsapp_token
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.api_version = settings.facebook_graph_api_version

    def is_configured(self) -> bool:
        return bool(self.token and self.phone_number_id)

    async def send_quick_replies(self, to: str, body: str, replies: list[tuple[str, str]]) -> dict:
        """
        Send interactive reply buttons to WhatsApp via Cloud API.
        replies: list of (id, title)
        """
        assert self.is_configured(), "WhatsApp client not configured"

        url = (
            f"https://graph.facebook.com/{self.api_version}/"
            f"{self.phone_number_id}/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": rid, "title": title}}
                        for rid, title in replies[:3]
                    ]
                },
            },
        }

        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()


