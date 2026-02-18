"""
marksync.plugins.channels.nats — NATS channel (machine↔machine).

Cloud-native messaging for microservices. Supports pub/sub,
request/reply, and JetStream for persistence.

Config:
    servers: ["nats://localhost:4222"]
    subject: marksync.pipeline.>
    queue_group: marksync-agents
    token: ""
    use_jetstream: false
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

log = logging.getLogger("marksync.channels.nats")


class Plugin(Channel):

    def __init__(self):
        self._nc = None
        self._connected = False
        self._recv_queue: asyncio.Queue[ChannelMessage] = asyncio.Queue()
        self._subscriptions = []

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="NATS Channel",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="channel-nats",
            description="NATS cloud-native messaging for machine↔machine pub/sub and request/reply",
            capabilities=["send", "receive", "subscribe", "publish", "request"],
            spec_url="https://docs.nats.io/",
            author="marksync",
        )

    async def connect(self, config: dict[str, Any]) -> None:
        import nats as nats_client

        servers = config.get("servers", ["nats://localhost:4222"])
        token = config.get("token", "")

        connect_opts = {"servers": servers}
        if token:
            connect_opts["token"] = token

        self._nc = await nats_client.connect(**connect_opts)
        self._connected = True

        subject = config.get("subject", "")
        queue_group = config.get("queue_group", "")
        if subject:
            await self.subscribe(subject, queue_group=queue_group)

        log.info(f"NATS connected: {servers}")

    async def disconnect(self) -> None:
        self._connected = False
        for sub in self._subscriptions:
            await sub.unsubscribe()
        self._subscriptions.clear()
        if self._nc:
            await self._nc.drain()
            self._nc = None
        log.info("NATS disconnected")

    async def send(self, message: ChannelMessage) -> None:
        if not self._nc:
            raise RuntimeError("NATS not connected")
        subject = message.headers.get("subject", f"marksync.{message.recipient or 'broadcast'}")
        payload = json.dumps(message.to_dict()).encode("utf-8")
        reply = message.reply_to or ""
        await self._nc.publish(subject, payload, reply=reply if reply else None)

    async def receive(self) -> ChannelMessage:
        return await self._recv_queue.get()

    async def subscribe(self, topic: str, queue_group: str = "") -> None:
        if not self._nc:
            return

        async def handler(msg):
            try:
                data = json.loads(msg.data.decode("utf-8"))
                cm = ChannelMessage(
                    id=data.get("id", str(uuid.uuid4())),
                    channel="nats",
                    sender=data.get("sender", ""),
                    recipient=data.get("recipient", ""),
                    payload=data.get("payload", {}),
                    headers={"subject": msg.subject, "reply": msg.reply or ""},
                    reply_to=data.get("reply_to", ""),
                    timestamp=data.get("timestamp", time.time()),
                )
                await self._recv_queue.put(cm)
            except Exception as e:
                log.warning(f"NATS message parse error: {e}")

        if queue_group:
            sub = await self._nc.subscribe(topic, queue=queue_group, cb=handler)
        else:
            sub = await self._nc.subscribe(topic, cb=handler)
        self._subscriptions.append(sub)
        log.info(f"NATS subscribed: {topic}")

    def is_connected(self) -> bool:
        return self._connected and self._nc is not None and self._nc.is_connected

    async def request(self, message: ChannelMessage, timeout: float = 30.0) -> ChannelMessage:
        if not self._nc:
            raise RuntimeError("NATS not connected")
        subject = message.headers.get("subject", f"marksync.{message.recipient}")
        payload = json.dumps(message.to_dict()).encode("utf-8")
        resp = await self._nc.request(subject, payload, timeout=timeout)
        data = json.loads(resp.data.decode("utf-8"))
        return ChannelMessage(
            id=data.get("id", str(uuid.uuid4())),
            channel="nats",
            sender=data.get("sender", ""),
            payload=data.get("payload", {}),
            reply_to=message.id,
            timestamp=data.get("timestamp", time.time()),
        )
