"""
marksync.transport — Pluggable transport layer for SyncServer.

Supported transports:
    websocket  — default, built-in
    mqtt       — via paho-mqtt (optional)
    grpc       — via grpcio (optional, long-term)

Usage:
    from marksync.transport import TransportLayer, get_transport

    transport = get_transport("websocket")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable


class TransportLayer(ABC):
    """
    Abstract base class for all SyncServer transports.

    Each transport must implement:
        start(host, port)   — begin listening
        stop()              — graceful shutdown
        broadcast(message)  — send to all connected clients
        on_message(handler) — register incoming message callback
    """

    name: str = "base"

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self._message_handler: Callable | None = None
        self._running = False

    def on_message(self, handler: Callable):
        """Register callback(client_id, message_dict) for incoming messages."""
        self._message_handler = handler

    @abstractmethod
    async def start(self):
        """Start the transport server."""

    @abstractmethod
    async def stop(self):
        """Gracefully shut down the transport."""

    @abstractmethod
    async def broadcast(self, message: str, exclude: Any = None):
        """Send message to all connected clients (excluding `exclude`)."""

    @abstractmethod
    async def send(self, client_id: Any, message: str):
        """Send message to a specific client."""

    def info(self) -> dict:
        return {
            "transport": self.name,
            "host": self.host,
            "port": self.port,
            "running": self._running,
        }


class WebSocketTransport(TransportLayer):
    """
    Default WebSocket transport — thin wrapper around the existing SyncServer
    websocket implementation (used for type registration).
    """

    name = "websocket"

    async def start(self):
        self._running = True

    async def stop(self):
        self._running = False

    async def broadcast(self, message: str, exclude=None):
        pass

    async def send(self, client_id, message: str):
        pass


class MQTTTransport(TransportLayer):
    """
    MQTT transport bridge — routes SyncServer block updates through an MQTT broker.
    Requires: pip install paho-mqtt
    Topic convention: marksync/<project>/<block_id>
    """

    name = "mqtt"

    def __init__(self, host: str = "0.0.0.0", port: int = 1883,
                 topic_prefix: str = "marksync"):
        super().__init__(host, port)
        self.topic_prefix = topic_prefix
        self._client = None

    async def start(self):
        try:
            import paho.mqtt.client as mqtt
            self._client = mqtt.Client(client_id="marksync-server")
            self._client.connect(self.host, self.port)
            self._client.loop_start()
            self._running = True
        except ImportError:
            raise RuntimeError("paho-mqtt not installed. Run: pip install paho-mqtt")

    async def stop(self):
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        self._running = False

    async def broadcast(self, message: str, exclude=None):
        if self._client:
            self._client.publish(f"{self.topic_prefix}/broadcast", message)

    async def send(self, client_id, message: str):
        if self._client:
            self._client.publish(f"{self.topic_prefix}/client/{client_id}", message)


_REGISTRY: dict[str, type[TransportLayer]] = {
    "websocket": WebSocketTransport,
    "mqtt": MQTTTransport,
}


def get_transport(name: str, **kwargs) -> TransportLayer:
    """Instantiate a transport by name. Raises ValueError for unknown names."""
    cls = _REGISTRY.get(name)
    if not cls:
        raise ValueError(f"Unknown transport: {name!r}. Available: {list(_REGISTRY)}")
    return cls(**kwargs)


def register_transport(name: str, cls: type[TransportLayer]):
    """Register a custom transport implementation."""
    _REGISTRY[name] = cls


__all__ = [
    "TransportLayer",
    "WebSocketTransport",
    "MQTTTransport",
    "get_transport",
    "register_transport",
]
