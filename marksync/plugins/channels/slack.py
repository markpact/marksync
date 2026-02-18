"""
marksync.plugins.channels.slack — Slack Bot channel (human↔machine).

Chat-based interaction for human tasks: approvals, reviews, notifications.
Uses Slack Web API + Socket Mode for real-time events.

Config:
    bot_token: xoxb-...
    app_token: xapp-...  # for Socket Mode
    channel: C0123456789
    thread_ts: ""  # reply in thread if set
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

log = logging.getLogger("marksync.channels.slack")


class Plugin(Channel):

    def __init__(self):
        self._connected = False
        self._recv_queue: asyncio.Queue[ChannelMessage] = asyncio.Queue()
        self._bot_token = ""
        self._default_channel = ""
        self._http_client = None

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="Slack Bot Channel",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="channel-slack",
            description="Slack Bot for chat-based human↔machine approvals, reviews, and notifications",
            capabilities=["send", "receive", "request"],
            spec_url="https://api.slack.com/apis",
            author="marksync",
        )

    async def connect(self, config: dict[str, Any]) -> None:
        import httpx

        self._bot_token = config.get("bot_token", "")
        self._default_channel = config.get("channel", "")

        if not self._bot_token:
            raise ValueError("Slack bot_token is required")

        self._http_client = httpx.AsyncClient(
            base_url="https://slack.com/api",
            headers={"Authorization": f"Bearer {self._bot_token}"},
            timeout=30,
        )

        # Verify token
        resp = await self._http_client.post("/auth.test")
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack auth failed: {data.get('error')}")

        self._connected = True
        log.info(f"Slack connected: bot={data.get('user')}, team={data.get('team')}")

    async def disconnect(self) -> None:
        self._connected = False
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        log.info("Slack disconnected")

    async def send(self, message: ChannelMessage) -> None:
        if not self._http_client:
            raise RuntimeError("Slack not connected")

        channel = message.headers.get("channel", self._default_channel)
        text = message.payload.get("text", json.dumps(message.payload))
        blocks = message.payload.get("blocks")

        body: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            body["blocks"] = blocks
        if message.headers.get("thread_ts"):
            body["thread_ts"] = message.headers["thread_ts"]

        resp = await self._http_client.post("/chat.postMessage", json=body)
        data = resp.json()
        if not data.get("ok"):
            log.error(f"Slack send failed: {data.get('error')}")

    async def receive(self) -> ChannelMessage:
        return await self._recv_queue.get()

    def is_connected(self) -> bool:
        return self._connected

    def inject_event(self, event: dict[str, Any]) -> None:
        """Called by Slack event webhook/Socket Mode handler to inject messages."""
        msg = ChannelMessage(
            id=event.get("client_msg_id", str(uuid.uuid4())),
            channel="slack",
            sender=event.get("user", ""),
            payload={"text": event.get("text", ""), "event": event},
            headers={
                "channel": event.get("channel", ""),
                "thread_ts": event.get("thread_ts", ""),
                "ts": event.get("ts", ""),
            },
            timestamp=float(event.get("ts", time.time())),
        )
        self._recv_queue.put_nowait(msg)
