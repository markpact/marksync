# marksync vs Apache Airflow

> Airflow — DAG-based task orchestration platform (Python)

## Porównanie

| Aspekt | marksync | Apache Airflow |
|---|---|---|
| **Fokus** | Collaborative AI agent orchestration | Data pipeline / ETL orchestration |
| **Model** | Pipeline + Agents + CRDT | DAG (Directed Acyclic Graph) |
| **Język** | Python | Python |
| **Definicja** | Markdown + YAML + PipelineSpec | Python DAG files |
| **Aktorzy** | LLM + Human + Script (multi-agent) | Operators (Python, Bash, HTTP, DB...) |
| **AI/LLM** | Natywny (LiteLLM, Ollama, multi-model) | Brak natywnego (custom operator) |
| **Kolaboracja** | CRDT real-time sync | Brak (single-author DAGs) |
| **Human tasks** | Inline (Slack, CLI, webhook) | ExternalTaskSensor (ograniczone) |
| **Scheduling** | Event-driven + pipeline trigger | Cron-based scheduling (core feature) |
| **BPMN** | Export/Import (multi-agent) | Brak |
| **Kanały** | 8 pluginów (MQTT, gRPC, Redis...) | Connections (DB, S3, HTTP...) |
| **UI** | CLI + API + WebSocket | Webserver (monitoring, trigger, logs) |
| **Deployment** | Docker, pip | Docker, Kubernetes (Helm), managed (MWAA, Cloud Composer) |
| **Licencja** | Apache 2.0 | Apache 2.0 |

## Kiedy marksync

- Potrzebujesz **agentów AI** w pipeline (LLM editor, reviewer)
- **Real-time collaboration** między ludźmi i AI
- Chcesz **BPMN export** i multi-agent patterns
- Pipeline definiowany przez **prompt** (LLM generuje kod)
- Komunikacja przez **różne kanały** (MQTT, Slack, gRPC)

## Kiedy Airflow

- **Data engineering / ETL** — codzienne batch joby
- Potrzebujesz **scheduling** (cron, timetable, data-aware)
- Monitorowanie **tysięcy DAG-ów** z UI
- Integracja z **data stack** (Spark, BigQuery, Snowflake, dbt)
- Managed hosting (AWS MWAA, Google Cloud Composer)
- Dojrzały ekosystem z **setkami operatorów**

## Integracja

marksync eksportuje pipeline jako Airflow DAG:

```python
from marksync.plugins.integrations.airflow import Plugin as AirflowPlugin

result = airflow_plugin.export_pipeline(pipeline)
# → airflow_dag.py (PythonOperator, ExternalTaskSensor)
```

---

[← Powrót do porównań](./README.md) | [Integrations](../integrations.md)
