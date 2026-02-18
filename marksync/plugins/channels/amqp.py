"""
marksync.plugins.channels.amqp — AMQP 0.9.1 channel (machine↔machine).

Reliable message queuing via RabbitMQ or compatible brokers.
Supports durable queues, routing keys, and dead-letter exchanges.

Config:
    url: amqp://guest:guest@localhost:5672/
    exchange: marksync
    exchange_type: topic
    queue: ""  # auto-generated if empty
    routing_key: pipeline.#
    durable: true
    prefetch_count: 10
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

log = logging.getLogger("marksync.channels.amqp")


class Plugin(Channel):

    def __init__(self):
        self._connection = None
        self._channel_obj = None
        self._queue_name = ""
        self._exchange = ""
        self._connected = False
        self._recv_queue: asyncio.Queue[ChannelMessage] = asyncio.Queue()

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="AMQP Channel (RabbitMQ)",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="channel-amqp",
            description="AMQP 0.9.1 reliable message queuing for machine↔machine communication via RabbitMQ",
            capabilities=["send", "receive", "subscribe", "publish", "request"],
            spec_url="https://www.amqp.org/specification/0-9-1/amqp-org-download",
            author="marksync",
        )

    async def connect(self, config: dict[str, Any]) -> None:
        import aio_pika

        url = config.get("url", "amqp://guest:guest@localhost:5672/")
        self._exchange = config.get("exchange", "marksync")
        exchange_type = config.get("exchange_type", "topic")
        self._queue_name = config.get("queue", "")
        durable = config.get("durable", True)
        prefetch = config.get("prefetch_count", 10)

        self._connection = await aio_pika.connect_robust(url)
        self._channel_obj = await self._connection.channel()
        await self._channel_obj.set_qos(prefetch_count=prefetch)

        # Declare exchange
        self._amqp_exchange = await self._channel_obj.declare_exchange(
            self._exchange, aio_pika.ExchangeType(exchange_type), durable=durable,
        )

        # Declare queue (auto-name if empty)
        queue = await self._channel_obj.declare_queue(
            self._queue_name or "", durable=durable, auto_delete=not self._queue_name,
        )
        self._queue_name = queue.name

        # Bind to routing key
        routing_key = config.get("routing_key", "pipeline.#")
        await queue.bind(self._amqp_exchange, routing_key)

        # Start consuming
        await queue.consume(self._on_message)
        self._connected = True
        log.info(f"AMQP connected: {url} (exchange={self._exchange}, queue={self._queue_name})")

    async def disconnect(self) -> None:
        self._connected = False
        if self._connection:
            await self._connection.close()
        self._connection = None
        self._channel_obj = None
        log.info("AMQP disconnected")

    async def send(self, message: ChannelMessage) -> None:
        import aio_pika

        if not self._amqp_exchange:
            raise RuntimeError("AMQP not connected")
        routing_key = message.headers.get("routing_key", f"pipeline.{message.recipient or 'broadcast'}")
        body = json.dumps(message.to_dict()).encode("utf-8")
        await self._amqp_exchange.publish(
            aio_pika.Message(body=body, content_type="application/json"),
            routing_key=routing_key,
        )

    async def receive(self) -> ChannelMessage:
        return await self._recv_queue.get()

    async def subscribe(self, topic: str) -> None:
        if self._channel_obj and hasattr(self, "_amqp_exchange"):
            queue = await self._channel_obj.declare_queue("", auto_delete=True)
            await queue.bind(self._amqp_exchange, topic)
            await queue.consume(self._on_message)
            log.info(f"AMQP subscribed: {topic}")

    def is_connected(self) -> bool:
        return self._connected

    async def _on_message(self, message) -> None:
        async with message.process():
            try:
                data = json.loads(message.body.decode("utf-8"))
                cm = ChannelMessage(
                    id=data.get("id", str(uuid.uuid4())),
                    channel="amqp",
                    sender=data.get("sender", ""),
                    recipient=data.get("recipient", ""),
                    payload=data.get("payload", {}),
                    headers={"routing_key": message.routing_key or "", "exchange": self._exchange},
                    reply_to=data.get("reply_to", ""),
                    timestamp=data.get("timestamp", time.time()),
                )
                await self._recv_queue.put(cm)
            except Exception as e:
                log.warning(f"AMQP message parse error: {e}")
