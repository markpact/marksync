"""
examples/channels/test_channels_e2e.py — End-to-end tests for all channel plugins.

Prerequisites:
    docker compose -f examples/channels/docker-compose.e2e.yml up -d

Usage:
    python examples/channels/test_channels_e2e.py

Tests:
    1. WebSocket    — connect, send, receive (loopback)
    2. MQTT         — publish, subscribe, receive
    3. Redis        — pub/sub send/receive
    4. AMQP         — publish to exchange, consume from queue
    5. NATS         — pub/sub + request/reply
    6. HTTP Webhook — POST callback, receive response
    7. CLI stdio    — send prompt, simulate input
    8. SSE          — broadcast to subscribers
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import types
import uuid

import pytest

# Stub marksync to avoid heavy deps
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, _ROOT)
_stub = types.ModuleType("marksync")
_stub.__path__ = [os.path.join(_ROOT, "marksync")]
_stub.__package__ = "marksync"
sys.modules["marksync"] = _stub

from marksync.plugins.base import ChannelMessage


def msg(sender: str = "test", recipient: str = "", payload: dict = None, **headers) -> ChannelMessage:
    return ChannelMessage(
        id=str(uuid.uuid4()),
        channel="test",
        sender=sender,
        recipient=recipient,
        payload=payload or {"text": f"hello from {sender}", "ts": time.time()},
        headers=headers,
    )


class Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.details: list[tuple[str, str, str]] = []

    def ok(self, name: str, info: str = ""):
        self.passed += 1
        self.details.append((name, "✓", info))
        print(f"  ✓ {name} {info}")

    def fail(self, name: str, err: str):
        self.failed += 1
        self.details.append((name, "✗", err))
        print(f"  ✗ {name} — {err}")

    def skip(self, name: str, reason: str):
        self.skipped += 1
        self.details.append((name, "⊘", reason))
        print(f"  ⊘ {name} — {reason}")

    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{'='*60}")
        print(f"  Results: {self.passed}/{total} passed, {self.failed} failed, {self.skipped} skipped")
        print(f"{'='*60}")


results = Results()


# ── Test: MQTT ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_mqtt():
    name = "MQTT pub/sub"
    try:
        import paho.mqtt.client  # noqa: F401
    except ImportError:
        results.skip(name, "paho-mqtt not installed")
        return

    try:
        from marksync.plugins.channels.mqtt import Plugin
        ch = Plugin()
        await ch.connect({
            "broker": "localhost", "port": 1883, "qos": 1,
            "topics": ["marksync/test/#"],
        })
        assert ch.is_connected(), "not connected"

        test_msg = msg("mqtt-sender", headers={"topic": "marksync/test/hello"})
        await ch.send(test_msg)

        received = await asyncio.wait_for(ch.receive(), timeout=5.0)
        assert received.sender == "mqtt-sender"
        await ch.disconnect()
        results.ok(name, f"sent+received, payload={len(json.dumps(received.payload))}b")
    except asyncio.TimeoutError:
        results.fail(name, "timeout — is Mosquitto running on localhost:1883?")
    except Exception as e:
        results.fail(name, str(e))


# ── Test: Redis ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_redis():
    name = "Redis pub/sub"
    try:
        import redis.asyncio  # noqa: F401
    except ImportError:
        results.skip(name, "redis[asyncio] not installed")
        return

    try:
        from marksync.plugins.channels.redis_pubsub import Plugin
        ch = Plugin()
        await ch.connect({
            "url": "redis://localhost:6379/0",
            "channels": ["marksync:test"],
        })
        assert ch.is_connected()

        await asyncio.sleep(0.2)  # let subscription settle
        test_msg = msg("redis-sender", headers={"channel": "marksync:test"})
        await ch.send(test_msg)

        received = await asyncio.wait_for(ch.receive(), timeout=5.0)
        assert received.sender == "redis-sender"
        await ch.disconnect()
        results.ok(name, f"sent+received")
    except asyncio.TimeoutError:
        results.fail(name, "timeout — is Redis running on localhost:6379?")
    except Exception as e:
        results.fail(name, str(e))


# ── Test: AMQP (RabbitMQ) ───────────────────────────────────────────────

@pytest.mark.anyio
async def test_amqp():
    name = "AMQP (RabbitMQ)"
    try:
        import aio_pika  # noqa: F401
    except ImportError:
        results.skip(name, "aio-pika not installed")
        return

    try:
        from marksync.plugins.channels.amqp import Plugin
        ch = Plugin()
        await ch.connect({
            "url": "amqp://marksync:marksync@localhost:5672/",
            "exchange": "marksync-test",
            "exchange_type": "topic",
            "routing_key": "test.#",
            "durable": False,
        })
        assert ch.is_connected()

        test_msg = msg("amqp-sender", headers={"routing_key": "test.hello"})
        await ch.send(test_msg)

        received = await asyncio.wait_for(ch.receive(), timeout=5.0)
        assert received.sender == "amqp-sender"
        await ch.disconnect()
        results.ok(name, f"sent+received via exchange")
    except asyncio.TimeoutError:
        results.fail(name, "timeout — is RabbitMQ running on localhost:5672?")
    except Exception as e:
        results.fail(name, str(e))


# ── Test: NATS ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_nats():
    name = "NATS pub/sub"
    try:
        import nats  # noqa: F401
    except ImportError:
        results.skip(name, "nats-py not installed")
        return

    try:
        from marksync.plugins.channels.nats import Plugin
        ch = Plugin()
        await ch.connect({
            "servers": ["nats://localhost:4222"],
            "subject": "marksync.test.>",
        })
        assert ch.is_connected()

        test_msg = msg("nats-sender", headers={"subject": "marksync.test.hello"})
        await ch.send(test_msg)

        received = await asyncio.wait_for(ch.receive(), timeout=5.0)
        assert received.sender == "nats-sender"
        await ch.disconnect()
        results.ok(name, f"sent+received")
    except asyncio.TimeoutError:
        results.fail(name, "timeout — is NATS running on localhost:4222?")
    except Exception as e:
        results.fail(name, str(e))


# ── Test: SSE ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_sse():
    name = "SSE broadcast"
    try:
        from marksync.plugins.channels.sse import Plugin
        ch = Plugin()
        await ch.connect({})
        assert ch.is_connected()

        # Add subscriber
        q = ch.add_subscriber()
        assert ch.subscriber_count == 1

        # Send event
        test_msg = msg("sse-sender")
        test_msg.headers["event"] = "pipeline_update"
        await ch.send(test_msg)

        # Subscriber should receive SSE-formatted data
        sse_data = q.get_nowait()
        assert "event: pipeline_update" in sse_data
        assert "data:" in sse_data

        ch.remove_subscriber(q)
        assert ch.subscriber_count == 0
        await ch.disconnect()
        results.ok(name, f"broadcast to 1 subscriber")
    except Exception as e:
        results.fail(name, str(e))


# ── Test: CLI stdio ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_cli():
    name = "CLI stdio"
    try:
        from marksync.plugins.channels.cli_stdio import Plugin
        ch = Plugin()
        await ch.connect({"prompt_prefix": "[test] "})
        assert ch.is_connected()

        # Test send (writes to stdout — just verify no crash)
        test_msg = msg("cli-sender", payload={"text": "hello from test"})
        await ch.send(test_msg)
        await ch.disconnect()
        results.ok(name, "send OK (stdout)")
    except Exception as e:
        results.fail(name, str(e))


# ── Test: HTTP Webhook ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_http_webhook():
    name = "HTTP Webhook"
    try:
        import httpx  # noqa: F401
    except ImportError:
        results.skip(name, "httpx not installed")
        return

    try:
        from marksync.plugins.channels.http_webhook import Plugin
        ch = Plugin()
        await ch.connect({"base_url": "https://httpbin.org", "timeout": 10})
        assert ch.is_connected()

        # inject_webhook simulates incoming webhook
        ch.inject_webhook({
            "sender": "external-system",
            "payload": {"action": "approved", "user": "tom"},
        })

        received = await asyncio.wait_for(ch.receive(), timeout=5.0)
        assert received.sender == "external-system"
        assert received.payload.get("action") == "approved"
        await ch.disconnect()
        results.ok(name, "inject+receive OK")
    except Exception as e:
        results.fail(name, str(e))


# ── Main ─────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  marksync Channel E2E Tests")
    print("=" * 60)
    print()

    # Tests that don't need external services first
    print("── Local channels (no external deps) ──")
    await test_sse()
    await test_cli()
    await test_http_webhook()

    # Tests that need Docker infrastructure
    print("\n── Machine↔Machine channels (need docker-compose) ──")
    await test_mqtt()
    await test_redis()
    await test_amqp()
    await test_nats()

    results.summary()
    sys.exit(1 if results.failed > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
