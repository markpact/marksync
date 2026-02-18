"""
marksync.plugins.channels.redis_pubsub — Redis Pub/Sub channel (machine↔machine).

In-cluster messaging with minimal latency. Supports pub/sub patterns
and optional Redis Streams for persistence.

Config:
    url: redis://localhost:6379/0
    channels: ["marksync:pipeline", "marksync:agents"]
    use_streams: false
    stream_maxlen: 1000
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

log = logging.getLogger("marksync.channels.redis_pubsub")


class Plugin(Channel):

    def __init__(self):
        self._redis = None
        self._pubsub = None
        self._connected = False
        self._recv_queue: asyncio.Queue[ChannelMessage] = asyncio.Queue()
        self._reader_task = None

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="Redis Pub/Sub Channel",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="channel-redis",
            description="Redis Pub/Sub for low-latency in-cluster machine↔machine messaging",
            capabilities=["send", "receive", "subscribe", "publish"],
            spec_url="https://redis.io/docs/interact/pubsub/",
            author="marksync",
        )

    async def connect(self, config: dict[str, Any]) -> None:
        import redis.asyncio as aioredis

        url = config.get("url", "redis://localhost:6379/0")
        self._redis = aioredis.from_url(url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        self._connected = True

        for ch in config.get("channels", []):
            await self.subscribe(ch)

        self._reader_task = asyncio.create_task(self._reader_loop())
        log.info(f"Redis connected: {url}")

    async def disconnect(self) -> None:
        self._connected = False
        if self._reader_task:
            self._reader_task.cancel()
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        self._redis = None
        self._pubsub = None
        log.info("Redis disconnected")

    async def send(self, message: ChannelMessage) -> None:
        if not self._redis:
            raise RuntimeError("Redis not connected")
        channel = message.headers.get("channel", f"marksync:{message.recipient or 'broadcast'}")
        payload = json.dumps(message.to_dict())
        await self._redis.publish(channel, payload)

    async def receive(self) -> ChannelMessage:
        return await self._recv_queue.get()

    async def subscribe(self, topic: str) -> None:
        if self._pubsub:
            await self._pubsub.subscribe(topic)
            log.info(f"Redis subscribed: {topic}")

    async def unsubscribe(self, topic: str) -> None:
        if self._pubsub:
            await self._pubsub.unsubscribe(topic)

    def is_connected(self) -> bool:
        return self._connected

    async def _reader_loop(self):
        try:
            while self._connected and self._pubsub:
                msg = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg["type"] == "message":
                    try:
                        data = json.loads(msg["data"])
                        cm = ChannelMessage(
                            id=data.get("id", str(uuid.uuid4())),
                            channel="redis",
                            sender=data.get("sender", ""),
                            recipient=data.get("recipient", ""),
                            payload=data.get("payload", {}),
                            headers={"redis_channel": msg.get("channel", "")},
                            reply_to=data.get("reply_to", ""),
                            timestamp=data.get("timestamp", time.time()),
                        )
                        await self._recv_queue.put(cm)
                    except json.JSONDecodeError:
                        log.warning(f"Redis non-JSON message on {msg.get('channel')}")
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Redis reader error: {e}")
            self._connected = False
