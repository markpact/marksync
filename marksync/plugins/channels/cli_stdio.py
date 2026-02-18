"""
marksync.plugins.channels.cli_stdio — CLI stdin/stdout channel (human↔machine).

Terminal-based interaction for human-in-the-loop tasks.
Reads from stdin, writes to stdout. Used for local development
and approval prompts in non-GUI environments.

Config:
    prompt_prefix: "[marksync] "
    color: true
    timeout: 0  # 0 = no timeout (wait forever)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import uuid
from typing import Any

from marksync.plugins.base import (
    Channel, PluginMeta, PluginType, ChannelMessage,
)

log = logging.getLogger("marksync.channels.cli_stdio")


class Plugin(Channel):

    def __init__(self):
        self._connected = False
        self._prefix = "[marksync] "
        self._recv_queue: asyncio.Queue[ChannelMessage] = asyncio.Queue()

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="CLI stdin/stdout Channel",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="channel-cli",
            description="Terminal stdin/stdout for local human↔machine interaction and approval prompts",
            capabilities=["send", "receive", "request"],
            author="marksync",
        )

    async def connect(self, config: dict[str, Any]) -> None:
        self._prefix = config.get("prompt_prefix", "[marksync] ")
        self._connected = True
        log.info("CLI stdio channel connected")

    async def disconnect(self) -> None:
        self._connected = False
        log.info("CLI stdio channel disconnected")

    async def send(self, message: ChannelMessage) -> None:
        payload = message.payload
        text = payload.get("text", "") or payload.get("message", "") or json.dumps(payload)
        sys.stdout.write(f"{self._prefix}{text}\n")
        sys.stdout.flush()

    async def receive(self) -> ChannelMessage:
        loop = asyncio.get_event_loop()
        line = await loop.run_in_executor(None, sys.stdin.readline)
        line = line.strip()

        return ChannelMessage(
            id=str(uuid.uuid4()),
            channel="cli",
            sender="human",
            payload={"text": line},
            timestamp=time.time(),
        )

    def is_connected(self) -> bool:
        return self._connected

    async def request(self, message: ChannelMessage, timeout: float = 0) -> ChannelMessage:
        """Send a prompt and wait for user input."""
        await self.send(message)
        if timeout > 0:
            return await asyncio.wait_for(self.receive(), timeout=timeout)
        return await self.receive()
