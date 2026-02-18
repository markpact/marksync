# marksync vs Temporal

> Temporal — durable execution platform, workflow-as-code (Go/Java/Python/TypeScript)

## Porównanie

| Aspekt | marksync | Temporal |
|---|---|---|
| **Fokus** | Collaborative AI agent orchestration | Durable execution, fault-tolerant workflows |
| **Model** | Pipeline + Agents + CRDT | Workflow + Activity (durable functions) |
| **Języki** | Python | Go, Java, Python, TypeScript, .NET |
| **Definicja** | Markdown + YAML + PipelineSpec | Code (workflow functions) |
| **Aktorzy** | LLM + Human + Script (multi-agent) | Activities (dowolne funkcje) |
| **AI/LLM** | Natywny (LiteLLM, Ollama, multi-model) | Brak natywnego (activity wrapper) |
| **Durability** | Brak (stateless pipeline) | Core feature — replay, retry, versioning |
| **Kolaboracja** | CRDT real-time sync | Brak (single-executor) |
| **Human tasks** | Inline (Slack, CLI, webhook, WebSocket) | Signal/Query (external trigger) |
| **BPMN** | Export/Import (multi-agent pools/lanes) | Brak |
| **Kanały** | 8 pluginów (MQTT, gRPC, Redis, AMQP...) | gRPC (worker ↔ server) |
| **Fault tolerance** | Podstawowy retry | Pełny: replay, retry, timeout, heartbeat |
| **Deployment** | Docker, pip | Temporal Server (Docker/K8s) + Workers |
| **Licencja** | Apache 2.0 | MIT |

## Kiedy marksync

- Potrzebujesz **agentów AI** (LLM) współpracujących z ludźmi
- **Real-time collaboration** (CRDT sync) jest kluczowa
- Chcesz **BPMN export** do enterprise workflow
- Pipeline generowany z **promptu** (LLM → Docker)
- Potrzebujesz **wielu kanałów** komunikacji (MQTT, Slack, gRPC)
- Lekkie narzędzie, szybki setup

## Kiedy Temporal

- Potrzebujesz **durable execution** — workflow przeżywa crashe
- **Long-running workflows** (dni, tygodnie, miesiące)
- Krytyczne systemy: **finansowe, bankowe, e-commerce**
- Potrzebujesz **retry policies**, timeouts, heartbeats
- **Saga pattern** — kompensacja przy failurach
- Workflow **versioning** bez downtime

## Integracja

marksync pipeline → Temporal workflow (via code generation):

```bash
# marksync generuje Temporal workflow z promptu
marksync generate --prompt temporal-pipeline.yaml
```

---

[← Powrót do porównań](./README.md) | [Pipeline Generation](../generate.md)
