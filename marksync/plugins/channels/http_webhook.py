"""
marksync.plugins.channels.http_webhook — HTTP Webhook channel (human↔machine).

REST-based callbacks for approval links, status notifications,
and integration with external services that use webhooks.

Config:
    base_url: http://localhost:8080
    callback_path: /webhooks/marksync
    auth_token: ""
    timeout: 30
    verify_ssl: true
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from marksync.plugins.base import (
    Channel, PluginMeta, PluginType, ChannelMessage,
)

log = logging.getLogger("marksync.channels.http_webhook")


class Plugin(Channel):

    def __init__(self):
        self._base_url = ""
        self._auth_token = ""
        self._timeout = 30
        self._connected = False
        self._recv_queue: asyncio.Queue[ChannelMessage] = asyncio.Queue()
        self._http_client = None

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="HTTP Webhook Channel",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="channel-http-webhook",
            description="HTTP Webhook callbacks for human↔machine approvals and external integrations",
            capabilities=["send", "receive", "request"],
            spec_url="https://webhooks.fyi/best-practices/webhook-providers",
            author="marksync",
        )

    async def connect(self, config: dict[str, Any]) -> None:
        import httpx

        self._base_url = config.get("base_url", "http://localhost:8080").rstrip("/")
        self._auth_token = config.get("auth_token", "")
        self._timeout = config.get("timeout", 30)
        verify_ssl = config.get("verify_ssl", True)

        self._http_client = httpx.AsyncClient(
            timeout=self._timeout,
            verify=verify_ssl,
        )
        self._connected = True
        log.info(f"HTTP Webhook connected: {self._base_url}")

    async def disconnect(self) -> None:
        self._connected = False
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        log.info("HTTP Webhook disconnected")

    async def send(self, message: ChannelMessage) -> None:
        if not self._http_client:
            raise RuntimeError("HTTP client not connected")

        url = message.headers.get("url", f"{self._base_url}/webhooks/marksync")
        headers = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        response = await self._http_client.post(
            url, json=message.to_dict(), headers=headers,
        )
        response.raise_for_status()
        log.debug(f"Webhook sent: {url} → {response.status_code}")

        # If response has a body, treat it as a reply
        if response.text:
            try:
                data = response.json()
                reply = ChannelMessage(
                    id=data.get("id", str(uuid.uuid4())),
                    channel="http-webhook",
                    sender=data.get("sender", "webhook"),
                    recipient=message.sender,
                    payload=data.get("payload", data),
                    reply_to=message.id,
                    timestamp=time.time(),
                )
                await self._recv_queue.put(reply)
            except (json.JSONDecodeError, ValueError):
                pass

    async def receive(self) -> ChannelMessage:
        return await self._recv_queue.get()

    def is_connected(self) -> bool:
        return self._connected

    def inject_webhook(self, data: dict[str, Any]) -> None:
        """Called by the webhook HTTP endpoint to inject incoming messages."""
        msg = ChannelMessage(
            id=data.get("id", str(uuid.uuid4())),
            channel="http-webhook",
            sender=data.get("sender", "external"),
            recipient=data.get("recipient", ""),
            payload=data.get("payload", data),
            headers=data.get("headers", {}),
            reply_to=data.get("reply_to", ""),
            timestamp=data.get("timestamp", time.time()),
        )
        self._recv_queue.put_nowait(msg)
