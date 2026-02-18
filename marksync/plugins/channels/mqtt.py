"""
marksync.plugins.channels.mqtt — MQTT 5.0 channel (machine↔machine).

Lightweight pub/sub for IoT and microservice communication.
Ideal for agent-to-agent messaging with QoS guarantees.

Config:
    broker: localhost
    port: 1883
    username: ""
    password: ""
    client_id: marksync-agent-1
    qos: 1  # 0=at-most-once, 1=at-least-once, 2=exactly-once
    topics: ["marksync/pipeline/#", "marksync/agents/#"]
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

log = logging.getLogger("marksync.channels.mqtt")


class Plugin(Channel):

    def __init__(self):
        self._client = None
        self._connected = False
        self._recv_queue: asyncio.Queue[ChannelMessage] = asyncio.Queue()
        self._subscriptions: set[str] = set()

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="MQTT 5.0 Channel",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="channel-mqtt",
            description="MQTT 5.0 pub/sub for lightweight machine↔machine agent messaging",
            capabilities=["send", "receive", "subscribe", "publish"],
            spec_url="https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html",
            author="marksync",
        )

    async def connect(self, config: dict[str, Any]) -> None:
        import paho.mqtt.client as mqtt

        broker = config.get("broker", "localhost")
        port = config.get("port", 1883)
        client_id = config.get("client_id", f"marksync-{uuid.uuid4().hex[:8]}")
        username = config.get("username", "")
        password = config.get("password", "")

        self._qos = config.get("qos", 1)
        self._client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv5,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        if username:
            self._client.username_pw_set(username, password)

        self._client.on_message = self._on_message
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        self._client.connect(broker, port)
        self._client.loop_start()
        self._connected = True

        # Auto-subscribe to configured topics
        for topic in config.get("topics", []):
            await self.subscribe(topic)

        log.info(f"MQTT connected: {broker}:{port} (client={client_id})")

    async def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
        self._connected = False
        log.info("MQTT disconnected")

    async def send(self, message: ChannelMessage) -> None:
        if not self._client:
            raise RuntimeError("MQTT not connected")
        topic = message.headers.get("topic", f"marksync/messages/{message.recipient or 'broadcast'}")
        payload = json.dumps(message.to_dict())
        self._client.publish(topic, payload, qos=self._qos)

    async def receive(self) -> ChannelMessage:
        return await self._recv_queue.get()

    async def subscribe(self, topic: str) -> None:
        if self._client:
            self._client.subscribe(topic, qos=self._qos)
            self._subscriptions.add(topic)
            log.info(f"MQTT subscribed: {topic}")

    async def unsubscribe(self, topic: str) -> None:
        if self._client:
            self._client.unsubscribe(topic)
            self._subscriptions.discard(topic)

    def is_connected(self) -> bool:
        return self._connected

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode("utf-8"))
            cm = ChannelMessage(
                id=data.get("id", str(uuid.uuid4())),
                channel="mqtt",
                sender=data.get("sender", ""),
                recipient=data.get("recipient", ""),
                payload=data.get("payload", {}),
                headers={"topic": msg.topic, "qos": str(msg.qos)},
                reply_to=data.get("reply_to", ""),
                timestamp=data.get("timestamp", time.time()),
            )
            asyncio.get_event_loop().call_soon_threadsafe(self._recv_queue.put_nowait, cm)
        except Exception as e:
            log.warning(f"MQTT message parse error: {e}")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        self._connected = True
        # Re-subscribe on reconnect
        for topic in self._subscriptions:
            client.subscribe(topic, qos=self._qos)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self._connected = False
        log.warning(f"MQTT disconnected (rc={rc})")
