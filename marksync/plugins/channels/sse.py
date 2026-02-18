"""
marksync.plugins.channels.sse — Server-Sent Events channel (human↔machine, one-way push).

One-way server→client push for live dashboards, progress bars,
and status updates. Clients connect via EventSource API in browser.

Config:
    base_url: http://localhost:8080
    endpoint: /events/pipeline
    reconnect_ms: 3000
    auth_token: ""
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

log = logging.getLogger("marksync.channels.sse")


class Plugin(Channel):

    def __init__(self):
        self._connected = False
        self._subscribers: list[asyncio.Queue] = []
        self._recv_queue: asyncio.Queue[ChannelMessage] = asyncio.Queue()

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="SSE Channel",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="channel-sse",
            description="Server-Sent Events for one-way push to browser dashboards and live status",
            capabilities=["send", "subscribe"],
            spec_url="https://html.spec.whatwg.org/multipage/server-sent-events.html",
            author="marksync",
        )

    async def connect(self, config: dict[str, Any]) -> None:
        self._connected = True
        log.info("SSE channel ready (server-side push)")

    async def disconnect(self) -> None:
        self._connected = False
        self._subscribers.clear()
        log.info("SSE channel disconnected")

    async def send(self, message: ChannelMessage) -> None:
        """Broadcast SSE event to all connected subscribers."""
        event_type = message.headers.get("event", "message")
        data = json.dumps(message.payload)
        sse_line = f"event: {event_type}\ndata: {data}\nid: {message.id}\n\n"

        for q in self._subscribers:
            try:
                q.put_nowait(sse_line)
            except asyncio.QueueFull:
                pass

    async def receive(self) -> ChannelMessage:
        return await self._recv_queue.get()

    def add_subscriber(self) -> asyncio.Queue:
        """Add a new SSE client subscriber. Returns queue to read from."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        return q

    def remove_subscriber(self, q: asyncio.Queue) -> None:
        """Remove a disconnected SSE client."""
        self._subscribers = [s for s in self._subscribers if s is not q]

    def is_connected(self) -> bool:
        return self._connected

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
