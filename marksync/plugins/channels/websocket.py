"""
marksync.plugins.channels.websocket — WebSocket channel (human↔machine, machine↔machine).

Full-duplex, real-time communication. Primary channel for:
    - Browser UI ↔ marksync agents (collaborative editing)
    - Agent ↔ Agent (low-latency sync within cluster)

Config:
    uri: ws://localhost:8765
    ping_interval: 30
    max_message_size: 1048576  # 1MB
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from marksync.plugins.base import (
    Channel, PluginMeta, PluginType, ChannelType, ChannelMessage,
)

log = logging.getLogger("marksync.channels.websocket")


class Plugin(Channel):

    def __init__(self):
        self._ws = None
        self._uri = ""
        self._connected = False
        self._recv_queue: asyncio.Queue[ChannelMessage] = asyncio.Queue()

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="WebSocket Channel",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="channel-websocket",
            description="Full-duplex WebSocket for real-time human↔machine and agent↔agent communication",
            capabilities=["send", "receive", "subscribe", "request"],
            spec_url="https://datatracker.ietf.org/doc/html/rfc6455",
            author="marksync",
        )

    async def connect(self, config: dict[str, Any]) -> None:
        import websockets
        self._uri = config.get("uri", "ws://localhost:8765")
        ping_interval = config.get("ping_interval", 30)
        self._ws = await websockets.connect(
            self._uri, ping_interval=ping_interval,
        )
        self._connected = True
        log.info(f"WebSocket connected: {self._uri}")

        # Start background receiver
        asyncio.create_task(self._reader_loop())

    async def disconnect(self) -> None:
        self._connected = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        log.info("WebSocket disconnected")

    async def send(self, message: ChannelMessage) -> None:
        if not self._ws:
            raise RuntimeError("WebSocket not connected")
        await self._ws.send(json.dumps(message.to_dict()))

    async def receive(self) -> ChannelMessage:
        return await self._recv_queue.get()

    async def subscribe(self, topic: str) -> None:
        # WebSocket: send a subscribe control message
        await self.send(ChannelMessage(
            id=str(uuid.uuid4()), channel="websocket",
            sender="system", payload={"action": "subscribe", "topic": topic},
        ))

    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    async def _reader_loop(self):
        try:
            async for raw in self._ws:
                try:
                    data = json.loads(raw)
                    msg = ChannelMessage(
                        id=data.get("id", str(uuid.uuid4())),
                        channel="websocket",
                        sender=data.get("sender", ""),
                        recipient=data.get("recipient", ""),
                        payload=data.get("payload", {}),
                        headers=data.get("headers", {}),
                        reply_to=data.get("reply_to", ""),
                        timestamp=data.get("timestamp", time.time()),
                    )
                    await self._recv_queue.put(msg)
                except json.JSONDecodeError:
                    log.warning(f"Non-JSON WebSocket message: {raw[:100]}")
        except Exception as e:
            self._connected = False
            log.error(f"WebSocket reader error: {e}")
