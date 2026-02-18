# marksync vs Camunda BPM

> Camunda — enterprise BPMN workflow engine (Java/Spring)

## Porównanie

| Aspekt | marksync | Camunda |
|---|---|---|
| **Fokus** | Collaborative editing + AI agents + pipeline orchestration | Enterprise BPMN execution engine |
| **Język** | Python | Java/Spring Boot |
| **Model procesu** | Markdown (README.md) + PipelineSpec | BPMN 2.0 XML |
| **Aktorzy** | LLM + Human + Script | Human + Service + External |
| **BPMN** | Export/Import plugin (pools, lanes, gateways, multi-instance) | Natywny BPMN 2.0 runtime |
| **Sync** | CRDT real-time (WebSocket) | Brak (single-writer) |
| **Human tasks** | Inline (CLI, Slack, webhook, WebSocket) | Tasklist webapp |
| **AI/LLM** | Natywny (LiteLLM, Ollama, OpenRouter) | Brak (wymaga custom connectora) |
| **Kanały** | 8 pluginów (MQTT, gRPC, Redis, AMQP, NATS, WS, Slack, SSE) | REST API + External Tasks |
| **Deployment** | Docker, single binary | Java app server, Spring Boot |
| **Licencja** | Apache 2.0 | Community (Apache 2.0) / Enterprise (paid) |
| **Maturity** | Wczesna faza | Dojrzały (10+ lat) |

## Kiedy marksync

- Potrzebujesz **AI agentów** (LLM) w procesie
- Chcesz **collaborative editing** (CRDT, real-time sync)
- Preferujesz **Python** i lekkie narzędzia
- Markdown jest twoim "źródłem prawdy"
- Potrzebujesz wielu **kanałów komunikacji** (MQTT, Slack, gRPC)

## Kiedy Camunda

- Potrzebujesz **pełnego BPMN runtime** z historią i audytem
- Enterprise compliance, BPMN ISO 19510 strict
- Duża organizacja z **dedykowanym Tasklist UI**
- Java/Spring ekosystem
- Potrzebujesz **Operate** (monitoring) i **Optimize** (analytics)

## Integracja

marksync eksportuje natywne BPMN 2.0 XML → import do Camunda Modeler:

```bash
# Export z marksync do BPMN
python examples/bpmn_multiagent.py
# Otwórz w Camunda Modeler:
#   examples/output/4_full_collaboration.bpmn
```

---

[← Powrót do porównań](./README.md) | [Plugin System](../plugins.md) | [BPMN Patterns](../plugins.md#bpmn-multi-agent-patterns--komunikacja-synchroniczna-i-asynchroniczna)
