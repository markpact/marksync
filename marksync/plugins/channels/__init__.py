"""
marksync.plugins.channels — Communication channel plugins.

Channel types:
    Human ↔ Machine:
        websocket.py    — WebSocket (browser UI, real-time collaboration)
        http_webhook.py — HTTP Webhook (REST callbacks, approval links)
        cli_stdio.py    — CLI stdin/stdout (terminal interaction)
        slack.py        — Slack Bot (chat-based human tasks)
        sse.py          — Server-Sent Events (one-way push to browser)

    Machine ↔ Machine:
        mqtt.py         — MQTT 5.0 (IoT, lightweight pub/sub)
        grpc_stream.py  — gRPC bidirectional streaming
        redis_pubsub.py — Redis Pub/Sub (in-cluster messaging)
        amqp.py         — AMQP 0.9.1 / RabbitMQ (reliable queues)
        nats.py         — NATS (cloud-native messaging)
"""
