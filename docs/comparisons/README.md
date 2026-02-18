# marksync — Porównania z innymi systemami

| Dokument | Porównanie |
|---|---|
| [vs-camunda.md](./vs-camunda.md) | Camunda BPM — workflow engine, BPMN orchestration |
| [vs-n8n.md](./vs-n8n.md) | n8n — visual workflow automation |
| [vs-airflow.md](./vs-airflow.md) | Apache Airflow — DAG-based task orchestration |
| [vs-temporal.md](./vs-temporal.md) | Temporal — durable execution, workflow-as-code |
| [vs-iac.md](./vs-iac.md) | Ansible / Terraform / Chef / Puppet — IaC tools |

## Pozycjonowanie marksync

```
                    Collaboration ──────────────────►
                    │
                    │   Google Docs    marksync
                    │   (human only)   (human + AI + script)
                    │
        Complexity  │   n8n            Camunda
                    │   (visual)       (enterprise BPMN)
                    │
                    │   Airflow        Temporal
                    │   (data DAGs)    (durable execution)
                    │
                    │   Ansible/TF
                    │   (IaC)
                    ▼
```

**marksync** łączy:
- **Kolaborację** (CRDT, real-time sync) z **orkiestracją** (pipelines, agents)
- **Ludzi** (human-in-the-loop) z **AI** (LLM agents) i **skryptami**
- **Markdown jako kontrakt** (README.md) z **wieloformatowym eksportem** (BPMN, OpenAPI, K8s...)
- **Kanały komunikacji** (MQTT, gRPC, WebSocket, Slack) z **BPMN message flows**

---

**Powiązane dokumenty:**
- [Plugin System](../plugins.md)
- [Channels](../channels.md)
- [BPM Formats](../formats.md)
- [Pipeline Generation](../generate.md)
