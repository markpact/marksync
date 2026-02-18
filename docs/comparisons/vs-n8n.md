# marksync vs n8n

> n8n — visual workflow automation platform (TypeScript, self-hosted)

## Porównanie

| Aspekt | marksync | n8n |
|---|---|---|
| **Fokus** | Collaborative AI agent orchestration | Visual workflow automation |
| **Interfejs** | CLI + API + WebSocket | Visual drag-and-drop canvas |
| **Język** | Python | TypeScript/Node.js |
| **Definicja procesu** | Markdown + YAML + PipelineSpec | JSON workflow (visual nodes) |
| **Aktorzy** | LLM + Human + Script (multi-agent) | 400+ node types (HTTP, DB, SaaS...) |
| **AI/LLM** | Natywny (LiteLLM, Ollama, multi-model) | AI Agent node (OpenAI, Anthropic) |
| **Kolaboracja** | CRDT real-time sync | Brak real-time (single-editor) |
| **Human tasks** | Inline (Slack, CLI, webhook, WebSocket) | Wait node + Forms |
| **BPMN** | Export/Import (multi-agent pools/lanes) | Brak |
| **Kanały** | 8 pluginów (MQTT, gRPC, Redis, AMQP...) | HTTP Webhook, AMQP (via nodes) |
| **Pipeline gen** | Prompt → LLM → Docker service | Brak (manual node setup) |
| **Deployment** | Docker, pip install | Docker, npm |
| **Licencja** | Apache 2.0 | Sustainable Use License (fair-code) |

## Kiedy marksync

- Potrzebujesz **wielu agentów AI** współpracujących w real-time
- Chcesz **CRDT sync** (conflict-free editing)
- Potrzebujesz **BPMN export** do enterprise narzędzi
- Chcesz **generować pipeline z promptu** (LLM → Docker)
- Potrzebujesz różnych **kanałów komunikacji** (MQTT, gRPC, NATS)
- Python ekosystem

## Kiedy n8n

- Potrzebujesz **visual canvas** do budowania workflow
- Integracja z **400+ usługami SaaS** (Slack, Google, Stripe...)
- **Low-code / no-code** — użytkownicy nietechniczni
- Gotowe triggery (cron, webhook, email, DB change)
- Potrzebujesz gotowego UI do monitoringu wykonań

## Integracja

marksync może eksportować pipeline do formatu n8n:

```python
from marksync.plugins.integrations.n8n import Plugin as N8nPlugin

result = n8n_plugin.export_pipeline(pipeline)
# → n8n workflow JSON (import via n8n UI)
```

---

[← Powrót do porównań](./README.md) | [Integrations](../integrations.md)
