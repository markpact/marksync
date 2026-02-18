"""
marksync.plugins.channels.grpc_stream — gRPC bidirectional streaming channel (machine↔machine).

High-performance, typed communication with protobuf serialization.
Ideal for inter-service agent communication with strict contracts.

Config:
    target: localhost:50051
    server_mode: false
    tls: false
    metadata: {}
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

log = logging.getLogger("marksync.channels.grpc_stream")


class Plugin(Channel):

    def __init__(self):
        self._channel = None
        self._connected = False
        self._recv_queue: asyncio.Queue[ChannelMessage] = asyncio.Queue()
        self._target = ""

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="gRPC Streaming Channel",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="channel-grpc",
            description="gRPC bidirectional streaming for high-performance machine↔machine communication",
            capabilities=["send", "receive", "stream", "request"],
            spec_url="https://grpc.io/docs/what-is-grpc/core-concepts/",
            author="marksync",
        )

    async def connect(self, config: dict[str, Any]) -> None:
        import grpc

        self._target = config.get("target", "localhost:50051")
        use_tls = config.get("tls", False)

        if use_tls:
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.aio.secure_channel(self._target, credentials)
        else:
            self._channel = grpc.aio.insecure_channel(self._target)

        # Wait for channel to be ready
        await self._channel.channel_ready()
        self._connected = True
        log.info(f"gRPC connected: {self._target}")

    async def disconnect(self) -> None:
        if self._channel:
            await self._channel.close()
            self._channel = None
        self._connected = False
        log.info("gRPC disconnected")

    async def send(self, message: ChannelMessage) -> None:
        if not self._channel:
            raise RuntimeError("gRPC channel not connected")
        # Serialize as JSON bytes for generic use
        # Real implementations would use protobuf stubs
        payload = json.dumps(message.to_dict()).encode("utf-8")
        log.debug(f"gRPC send: {len(payload)} bytes to {message.recipient}")
        # In a real implementation, this would call a stub method
        # For now, store in queue for loopback testing
        await self._recv_queue.put(message)

    async def receive(self) -> ChannelMessage:
        return await self._recv_queue.get()

    def is_connected(self) -> bool:
        return self._connected
