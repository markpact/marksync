# marksync Channels — Komunikacja między agentami i ludźmi

> **Plik źródłowy:** [`marksync/plugins/channels/`](../marksync/plugins/channels/__init__.py)
> **Base class:** [`Channel`](../marksync/plugins/base.py) (linia 475)
> **Konfiguracja:** [`examples/channels/channel_config.yaml`](../examples/channels/channel_config.yaml)
> **Testy E2E:** [`examples/channels/test_channels_e2e.py`](../examples/channels/test_channels_e2e.py)

## Spis treści

1. [Architektura kanałów](#architektura-kanałów)
2. [Human ↔ Machine](#human--machine)
3. [Machine ↔ Machine](#machine--machine)
4. [Konfiguracja YAML](#konfiguracja-yaml)
5. [Routing wiadomości](#routing-wiadomości)
6. [E2E testowanie](#e2e-testowanie)
7. [Porównanie kanałów](#porównanie-kanałów)

---

## Architektura kanałów

```
                     ┌─────────────────────────┐
                     │     Pipeline Engine      │
                     └────────┬────────────────┘
                              │ ChannelMessage
         ┌────────────────────┼────────────────────┐
         │                    │                    │
    Human↔Machine       Machine↔Machine        Broadcast
    ┌─────────┐        ┌─────────────┐       ┌──────────┐
    │WebSocket│        │   MQTT 5.0  │       │   SSE    │
    │HTTP Hook│        │   gRPC      │       │(one-way) │
    │CLI stdio│        │Redis pub/sub│       └──────────┘
    │  Slack  │        │ AMQP/Rabbit │
    └─────────┘        │    NATS     │
                       └─────────────┘

    Patterns:
      → Request / Reply (sync)
      → Publish / Subscribe (async)
      → Fire-and-forget (one-way)
      → Streaming (continuous)
```

Każdy kanał implementuje interfejs `Channel`:

```python
class Channel(abc.ABC):
    async def connect(self, config: dict) -> None: ...
    async def disconnect(self) -> None: ...
    async def send(self, message: ChannelMessage) -> None: ...
    async def receive(self) -> ChannelMessage: ...
    async def subscribe(self, topic: str) -> None: ...
    async def request(self, msg, timeout=30) -> ChannelMessage: ...  # sync request/reply
```

---

## Human ↔ Machine

### WebSocket — [`websocket.py`](../marksync/plugins/channels/websocket.py)

Real-time, full-duplex. Główny kanał dla UI w przeglądarce.

```yaml
browser-ws:
  type: human_machine
  driver: websocket
  config:
    uri: ws://localhost:8765
    ping_interval: 30
```

| Cecha | Wartość |
|---|---|
| **Kierunek** | Dwukierunkowy |
| **Latencja** | ~1ms (LAN) |
| **Protokół** | RFC 6455 |
| **Użycie** | Edycja Markdown, live preview, collaborative editing |

### HTTP Webhook — [`http_webhook.py`](../marksync/plugins/channels/http_webhook.py)

REST callbacks do zatwierdzania zadań i integracji z systemami zewnętrznymi.

```yaml
approval-webhook:
  type: human_machine
  driver: http_webhook
  config:
    base_url: http://localhost:8080
    callback_path: /webhooks/approval
    auth_token: ${WEBHOOK_AUTH_TOKEN:-}
```

| Cecha | Wartość |
|---|---|
| **Kierunek** | Request → Response |
| **Protokół** | HTTP/HTTPS |
| **Użycie** | Approval links (email), status callbacks, CI/CD webhooks |

### CLI stdio — [`cli_stdio.py`](../marksync/plugins/channels/cli_stdio.py)

Terminal stdin/stdout — dla lokalnego developmentu i testowania.

```yaml
terminal:
  type: human_machine
  driver: cli_stdio
  config:
    prompt_prefix: "🔧 marksync> "
    color: true
```

### Slack Bot — [`slack.py`](../marksync/plugins/channels/slack.py)

Chat-based approvals i notyfikacje przez Slack API.

```yaml
slack-bot:
  type: human_machine
  driver: slack
  config:
    bot_token: ${SLACK_BOT_TOKEN}
    channel: ${SLACK_CHANNEL}
```

### SSE (Server-Sent Events) — [`sse.py`](../marksync/plugins/channels/sse.py)

Jednokierunkowy push do przeglądarki (dashboardy, progress bary).

```yaml
dashboard-sse:
  type: broadcast
  driver: sse
  config:
    endpoint: /events/pipeline
    reconnect_ms: 3000
```

---

## Machine ↔ Machine

### MQTT 5.0 — [`mqtt.py`](../marksync/plugins/channels/mqtt.py)

Lekki pub/sub dla agentów. QoS 0/1/2, wildcards `#` `+`.

```yaml
agent-mqtt:
  type: machine_machine
  driver: mqtt
  config:
    broker: localhost
    port: 1883
    qos: 1
    topics:
      - marksync/pipeline/#
      - marksync/agents/#
```

| Cecha | Wartość |
|---|---|
| **QoS** | 0 (at-most-once), 1 (at-least-once), 2 (exactly-once) |
| **Wildcards** | `+` (single level), `#` (multi-level) |
| **Broker** | Mosquitto, HiveMQ, EMQX |
| **Użycie** | Agent↔Agent, IoT, lekki messaging |

### Redis Pub/Sub — [`redis_pubsub.py`](../marksync/plugins/channels/redis_pubsub.py)

Ultra-niskie opóźnienia w obrębie klastra.

```yaml
cluster-redis:
  type: machine_machine
  driver: redis_pubsub
  config:
    url: redis://localhost:6379/0
    channels:
      - marksync:pipeline
      - marksync:agents
```

| Cecha | Wartość |
|---|---|
| **Latencja** | <1ms (localhost) |
| **Persystencja** | Opcjonalna (Redis Streams) |
| **Użycie** | In-cluster events, cache invalidation, fast signaling |

### AMQP / RabbitMQ — [`amqp.py`](../marksync/plugins/channels/amqp.py)

Niezawodne kolejki z routing keys, dead-letter exchanges.

```yaml
task-queue:
  type: machine_machine
  driver: amqp
  config:
    url: amqp://marksync:marksync@localhost:5672/
    exchange: marksync
    exchange_type: topic
    routing_key: pipeline.#
    durable: true
    prefetch_count: 10
```

| Cecha | Wartość |
|---|---|
| **Gwarancja** | At-least-once (durable queues) |
| **Routing** | Topic exchange, direct, fanout, headers |
| **Management** | http://localhost:15672 |
| **Użycie** | Reliable task queuing, work distribution, dead-letter |

### NATS — [`nats.py`](../marksync/plugins/channels/nats.py)

Cloud-native messaging z request/reply i JetStream.

```yaml
service-nats:
  type: machine_machine
  driver: nats
  config:
    servers:
      - nats://localhost:4222
    subject: marksync.pipeline.>
    queue_group: marksync-agents
```

| Cecha | Wartość |
|---|---|
| **Request/Reply** | Natywny pattern |
| **JetStream** | Persystencja, exactly-once |
| **Queue Groups** | Load balancing |
| **Użycie** | Microservices, cloud-native, request/reply |

### gRPC Streaming — [`grpc_stream.py`](../marksync/plugins/channels/grpc_stream.py)

High-performance typed communication z protobuf.

```yaml
agent-grpc:
  type: machine_machine
  driver: grpc_stream
  config:
    target: localhost:50051
    tls: false
```

---

## Konfiguracja YAML

Pełna konfiguracja: [`examples/channels/channel_config.yaml`](../examples/channels/channel_config.yaml)

```yaml
channels:
  my-channel:
    type: human_machine | machine_machine | broadcast
    driver: websocket | mqtt | grpc_stream | redis_pubsub | amqp | nats | ...
    config:
      # parametry specyficzne dla drivera

routing:
  human:
    primary: slack-bot
    fallback: terminal
  llm:
    primary: agent-mqtt
    fallback: cluster-redis
  script:
    primary: task-queue
  events:
    primary: dashboard-sse
```

---

## Routing wiadomości

Pipeline Engine automatycznie kieruje wiadomości do odpowiedniego kanału na podstawie typu aktora:

```
StepSpec(actor="human")  → routing.human.primary  → slack-bot
StepSpec(actor="llm")    → routing.llm.primary    → agent-mqtt
StepSpec(actor="script") → routing.script.primary  → task-queue
CommMode.ASYNC           → routing.async_message   → service-nats
```

Jeśli primary jest niedostępny, fallback jest używany automatycznie.

---

## E2E testowanie

### Uruchomienie infrastruktury

```bash
# Start all brokers (MQTT, Redis, RabbitMQ, NATS)
docker compose -f examples/channels/docker-compose.e2e.yml up -d

# Sprawdź status
docker compose -f examples/channels/docker-compose.e2e.yml ps

# Management UIs:
#   RabbitMQ: http://localhost:15672 (marksync/marksync)
#   NATS:     http://localhost:8222
```

### Uruchomienie testów

```bash
# Zainstaluj zależności testowe
pip install paho-mqtt redis[asyncio] aio-pika nats-py

# Uruchom testy
python examples/channels/test_channels_e2e.py
```

### Oczekiwany wynik

```
══════════════════════════════════════════════════════════════
  marksync Channel E2E Tests
══════════════════════════════════════════════════════════════

── Local channels (no external deps) ──
  ✓ SSE broadcast — broadcast to 1 subscriber
  ✓ CLI stdio — send OK (stdout)
  ✓ HTTP Webhook — inject+receive OK

── Machine↔Machine channels (need docker-compose) ──
  ✓ MQTT pub/sub — sent+received
  ✓ Redis pub/sub — sent+received
  ✓ AMQP (RabbitMQ) — sent+received via exchange
  ✓ NATS pub/sub — sent+received

============================================================
  Results: 7/7 passed, 0 failed, 0 skipped
============================================================
```

### Cleanup

```bash
docker compose -f examples/channels/docker-compose.e2e.yml down -v
```

---

## Porównanie kanałów

| Kanał | Typ | Latencja | Persystencja | QoS | Request/Reply | Użycie |
|---|---|---|---|---|---|---|
| **WebSocket** | H↔M | ~1ms | ✗ | ✗ | ✓ | Browser UI, live editing |
| **HTTP Webhook** | H↔M | ~50ms | ✗ | ✗ | ✓ | Approvals, callbacks |
| **CLI stdio** | H↔M | ~0ms | ✗ | ✗ | ✓ | Terminal dev/test |
| **Slack** | H↔M | ~200ms | ✓ | ✗ | ✓ | Chat approvals |
| **SSE** | Broadcast | ~5ms | ✗ | ✗ | ✗ | Dashboard push |
| **MQTT** | M↔M | ~5ms | ✓¹ | 0/1/2 | ✗ | Agent messaging |
| **Redis** | M↔M | <1ms | ✓² | ✗ | ✗ | Cluster signaling |
| **AMQP** | M↔M | ~10ms | ✓ | ✓ | ✓ | Reliable queues |
| **NATS** | M↔M | ~2ms | ✓³ | ✓ | ✓ | Cloud-native |
| **gRPC** | M↔M | ~1ms | ✗ | ✗ | ✓ | Typed RPC |

¹ MQTT retained messages  ² Redis Streams  ³ NATS JetStream

---

**Powiązane dokumenty:**
- [Plugin System Overview](./plugins.md)
- [BPMN Multi-Agent Patterns](./plugins.md#bpmn-multi-agent-patterns--komunikacja-synchroniczna-i-asynchroniczna)
- [Pipeline Generation](./generate.md)
- [BPM Formats](./formats.md)
- [API Adapters](./api-adapters.md)
- [External Integrations](./integrations.md)
- [Comparisons](./comparisons/)
