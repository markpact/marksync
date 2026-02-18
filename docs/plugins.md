# marksync Plugin System — Formats, API Adapters, Integrations & Channels

> **Szczegółowa dokumentacja poszczególnych kategorii:**
> - [Kanały komunikacji](./channels.md) — Human↔Machine, Machine↔Machine (MQTT, gRPC, WebSocket, Slack...)
> - [Formaty BPM](./formats.md) — BPMN, XPDL, BPEL, Petri Net, EPC, DMN, CMMN, UML
> - [Adaptery API](./api-adapters.md) — OpenAPI, AsyncAPI, GraphQL, gRPC/Protobuf, JSON Schema
> - [Integracje](./integrations.md) — GitHub Actions, GitLab CI, K8s, Terraform, Ansible, Airflow, n8n
> - [Pipeline Generation](./generate.md) — Prompt → LLM → Docker service
> - [Porównania](./comparisons/) — vs Camunda, n8n, Airflow, Temporal, Ansible/Terraform

## Spis treści

1. [Architektura pluginów](#architektura-pluginów)
2. [Formaty BPM / Workflow](#formaty-bpm--workflow)
3. [Adaptery API](#adaptery-api)
4. [Integracje z systemami zewnętrznymi](#integracje-z-systemami-zewnętrznymi)
5. [Kanały komunikacji](#kanały-komunikacji)
6. [Tabela mapowań](#tabela-mapowań)
7. [Użycie](#użycie)
8. [Tworzenie własnych pluginów](#tworzenie-własnych-pluginów)

---

## Architektura pluginów

```
marksync/plugins/
├── __init__.py              # Eksporty + PluginRegistry
├── base.py                  # Klasy bazowe: FormatPlugin, APIAdapter, Integration
├── registry.py              # Rejestr pluginów, lazy-loading, discovery
├── formats/                 # Konwertery formatów BPM / workflow
│   ├── bpmn.py              # BPMN 2.0 (ISO 19510)
│   ├── xpdl.py              # XPDL 2.2 (WfMC)
│   ├── bpel.py              # WS-BPEL 2.0 (OASIS)
│   ├── petri.py             # Petri Net (PNML, ISO/IEC 15909-2)
│   ├── epc.py               # Event-driven Process Chain (EPML)
│   ├── dmn.py               # DMN 1.3 (OMG)
│   ├── cmmn.py              # CMMN 1.1 (OMG)
│   └── uml_activity.py      # UML Activity Diagram (XMI 2.5)
├── api/                     # Adaptery schematów API
│   ├── openapi.py           # OpenAPI 3.x / Swagger
│   ├── asyncapi.py          # AsyncAPI 2.6
│   ├── graphql.py           # GraphQL SDL
│   ├── grpc.py              # gRPC / Protocol Buffers 3
│   └── jsonschema.py        # JSON Schema 2020-12
├── channels/               # Kanały komunikacji (human↔machine, machine↔machine)
│   ├── websocket.py         # WebSocket (real-time, full-duplex)
│   ├── mqtt.py              # MQTT 5.0 (lightweight pub/sub)
│   ├── grpc_stream.py       # gRPC bidirectional streaming
│   ├── redis_pubsub.py      # Redis Pub/Sub (in-cluster)
│   ├── amqp.py              # AMQP 0.9.1 / RabbitMQ
│   ├── nats.py              # NATS (cloud-native messaging)
│   ├── http_webhook.py      # HTTP Webhook (callbacks)
│   ├── cli_stdio.py         # CLI stdin/stdout (terminal)
│   ├── slack.py             # Slack Bot (chat approvals)
│   └── sse.py               # Server-Sent Events (push)
└── integrations/            # Integracje z systemami zewnętrznymi
    ├── github.py            # GitHub Actions workflows
    ├── gitlab.py            # GitLab CI pipelines
    ├── kubernetes.py        # Kubernetes Job manifests
    ├── terraform.py         # Terraform HCL
    ├── ansible.py           # Ansible Playbooks
    ├── airflow.py           # Apache Airflow DAGs
    └── n8n.py               # n8n workflow JSON
```

### Trzy typy pluginów

| Typ | Klasa bazowa | Cel | Metody |
|-----|-------------|-----|--------|
| **Format** | `FormatPlugin` | Konwersja pipeline ↔ format BPM | `export_pipeline()`, `import_pipeline()`, `validate()` |
| **API** | `APIAdapter` | Konwersja pipeline ↔ schemat API | `export_schema()`, `import_schema()`, `validate_schema()` |
| **Integration** | `Integration` | Most do systemu zewnętrznego | `export_pipeline()`, `import_pipeline()`, `deploy()`, `status()` |

### Wspólny model danych

Wszystkie pluginy operują na `PipelineSpec` — znormalizowanej reprezentacji pipeline'u:

```python
@dataclass
class PipelineSpec:
    name: str
    description: str = ""
    steps: list[StepSpec] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    triggers: list[dict[str, Any]] = field(default_factory=list)

@dataclass
class StepSpec:
    name: str
    actor: str            # "llm", "script", "human"
    config: dict = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    timeout: float = 0.0
    required: bool = True
```

---

## Formaty BPM / Workflow

### BPMN 2.0 (ISO 19510)

**Standard:** Business Process Model and Notation 2.0
**Spec:** https://www.omg.org/spec/BPMN/2.0/
**Pliki:** `.bpmn`, `.bpmn20.xml`

| marksync | → | BPMN 2.0 |
|----------|---|----------|
| Pipeline start | → | `<startEvent>` |
| Step (LLM) | → | `<serviceTask>` (AI service) |
| Step (SCRIPT) | → | `<scriptTask>` |
| Step (HUMAN) | → | `<userTask>` |
| Pipeline end | → | `<endEvent>` |
| Step connection | → | `<sequenceFlow>` |
| Config | → | `<extensionElements>` (marksync:property) |

### XPDL 2.2 (WfMC)

**Standard:** XML Process Definition Language 2.2
**Spec:** https://www.wfmc.org/standards/xpdl
**Pliki:** `.xpdl`, `.xml`

| marksync | → | XPDL 2.2 |
|----------|---|----------|
| Pipeline | → | `<WorkflowProcess>` |
| Step (LLM) | → | `<Activity>` → `<TaskService>` |
| Step (SCRIPT) | → | `<Activity>` → `<TaskScript>` |
| Step (HUMAN) | → | `<Activity>` → `<TaskUser>` |
| Step connection | → | `<Transition>` |

### WS-BPEL 2.0 (OASIS)

**Standard:** Web Services Business Process Execution Language 2.0
**Spec:** http://docs.oasis-open.org/wsbpel/2.0/OS/wsbpel-v2.0-OS.html
**Pliki:** `.bpel`, `.xml`

| marksync | → | WS-BPEL |
|----------|---|---------|
| Pipeline | → | `<process>` → `<sequence>` |
| Step (LLM) | → | `<invoke>` (AI service partner) |
| Step (SCRIPT) | → | `<invoke>` (script service) |
| Step (HUMAN) | → | `<receive>` (wait for human input) |
| Pipeline I/O | → | `<partnerLinks>`, `<variables>` |

### Petri Net (PNML, ISO/IEC 15909-2)

**Standard:** Petri Net Markup Language
**Spec:** http://www.pnml.org/
**Pliki:** `.pnml`, `.xml`

| marksync | → | PNML |
|----------|---|------|
| Step | → | `<transition>` |
| Between steps | → | `<place>` |
| Pipeline start | → | `<place>` z `<initialMarking>` (1 token) |
| Connection | → | `<arc>` |
| Actor type | → | `<toolspecific>` (marksync annotation) |

### EPC (Event-driven Process Chain)

**Standard:** EPML (EPC Markup Language)
**Spec:** https://en.wikipedia.org/wiki/Event-driven_process_chain
**Pliki:** `.epml`, `.xml`

| marksync | → | EPC |
|----------|---|-----|
| Step | → | `<function>` |
| After step | → | `<event>` (state change) |
| Connection | → | `<arc>` → `<flow>` |
| Actor info | → | `marksync:config` attribute |

### DMN 1.3 (Decision Model and Notation)

**Standard:** DMN 1.3 (OMG)
**Spec:** https://www.omg.org/spec/DMN/1.3/
**Pliki:** `.dmn`, `.xml`

| marksync | → | DMN 1.3 |
|----------|---|---------|
| Step (HUMAN/LLM) | → | `<decision>` |
| Step (SCRIPT) | → | `<businessKnowledgeModel>` |
| Config | → | `<extensionElements>` |

### CMMN 1.1 (Case Management Model and Notation)

**Standard:** CMMN 1.1 (OMG)
**Spec:** https://www.omg.org/spec/CMMN/1.1/
**Pliki:** `.cmmn`, `.xml`

| marksync | → | CMMN 1.1 |
|----------|---|----------|
| Pipeline | → | `<case>` → `<casePlanModel>` |
| Step (HUMAN) | → | `<humanTask>` + `<milestone>` |
| Step (LLM/SCRIPT) | → | `<processTask>` |

### UML Activity Diagram (XMI 2.5)

**Standard:** UML 2.5.1 Activity Diagram
**Spec:** https://www.omg.org/spec/UML/2.5.1/
**Pliki:** `.xmi`, `.uml`, `.xml`

| marksync | → | UML-AD |
|----------|---|--------|
| Pipeline | → | `<uml:Activity>` |
| Step | → | `<uml:CallBehaviorAction>` ze stereotypem |
| LLM step | → | stereotype `«ai-service»` |
| SCRIPT step | → | stereotype `«script»` |
| HUMAN step | → | stereotype `«user-task»` |
| Pipeline start | → | `<uml:InitialNode>` |
| Pipeline end | → | `<uml:ActivityFinalNode>` |
| Connection | → | `<uml:ControlFlow>` |

---

## Adaptery API

### OpenAPI 3.x

**Standard:** OpenAPI Specification 3.1.0
**Spec:** https://spec.openapis.org/oas/v3.1.0
**Pliki:** `.openapi.yaml`, `.openapi.json`

Generuje pełny REST API spec z:
- `POST /pipelines/{name}/start` — start pipeline
- `GET /pipelines/{name}/runs/{run_id}` — status
- `POST /pipelines/{name}/tasks/{task_id}/resolve` — human approval
- Schematy: `PipelineRun`, `StepResult`, `HumanTask`, `TaskResolution`

### AsyncAPI 2.6

**Standard:** AsyncAPI Specification 2.6.0
**Spec:** https://www.asyncapi.com/docs/reference/specification/v2.6.0
**Pliki:** `.asyncapi.yaml`, `.asyncapi.json`

Generuje event-driven API spec z:
- Channels per step (publish/subscribe)
- Messages: `PipelineStarted`, `StepCompleted`, `HumanTaskCreated/Resolved`
- Servers: marksync SyncServer (ws), DSL API (ws)

### GraphQL SDL

**Standard:** GraphQL Specification
**Spec:** https://spec.graphql.org/
**Pliki:** `.graphql`, `.gql`

Generuje pełny GraphQL schema z:
- Types: `PipelineRun`, `Step`, `StepResult`, `HumanTask`
- Enums: `ActorType`, `StepStatus`, `TaskAction`
- Queries: `pipelineRun`, `pendingTasks`
- Mutations: `startPipeline`, `resolveTask`
- Subscriptions: `pipelineStarted`, `stepCompleted`, `humanTaskCreated`

### gRPC / Protocol Buffers 3

**Standard:** Protocol Buffers 3
**Spec:** https://protobuf.dev/
**Pliki:** `.proto`

Generuje `.proto` z:
- `service PipelineService` (StartPipeline, GetRun, ResolveTask, StreamEvents)
- Messages dla Step, StepResult, HumanTask, PipelineRun
- Server streaming: `StreamEvents` (real-time events)

### JSON Schema 2020-12

**Standard:** JSON Schema Draft 2020-12
**Spec:** https://json-schema.org/draft/2020-12/
**Pliki:** `.schema.json`

Generuje schema walidacyjny z:
- `$defs`: ActorType, StepStatus, TaskAction, Step, StepResult, HumanTask
- `prefixItems`: specific step constraints (name + actor per step)

---

## Integracje z systemami zewnętrznymi

### GitHub Actions

**Spec:** https://docs.github.com/en/actions
**Pliki:** `.yml`

| marksync | → | GitHub Actions |
|----------|---|----------------|
| Pipeline | → | Workflow (`on: workflow_dispatch`) |
| Step (LLM) | → | Job step (`run: marksync agent ...`) |
| Step (SCRIPT) | → | Job step (`run: python ...`) |
| Step (HUMAN) | → | Job with `environment` (required reviewers) |
| Step sequence | → | Job `needs` dependencies |

### GitLab CI

**Spec:** https://docs.gitlab.com/ee/ci/yaml/
**Pliki:** `.gitlab-ci.yml`

| marksync | → | GitLab CI |
|----------|---|-----------|
| Pipeline | → | Pipeline (stages + jobs) |
| Step (LLM/SCRIPT) | → | Job (`stage`, `script`) |
| Step (HUMAN) | → | Job (`when: manual`, `allow_failure: false`) |
| Step sequence | → | Stages (ordered) |

### Kubernetes

**Spec:** https://kubernetes.io/docs/
**Pliki:** `.k8s.yaml`

| marksync | → | Kubernetes |
|----------|---|------------|
| Pipeline | → | `Job` (batch/v1) |
| Step | → | `initContainer` (ordered) |
| Step (HUMAN) | → | Wait container (poll for approval file) |
| Config | → | `ConfigMap` (marksync-config) |

### Terraform HCL

**Spec:** https://developer.hashicorp.com/terraform/language
**Pliki:** `.tf`

Generuje infrastrukturę Docker:
- `docker_network.marksync`
- `docker_container.sync_server` (SyncServer)
- `docker_container.api_server` (DSL API)
- `docker_container.orchestrator` (agents.yml runner)
- Variables, outputs, step definitions w `locals`

### Ansible Playbook

**Spec:** https://docs.ansible.com/ansible/latest/playbook_guide/
**Pliki:** `.ansible.yml`

| marksync | → | Ansible |
|----------|---|---------|
| Pipeline | → | Play (`hosts: marksync_servers`) |
| Step (LLM) | → | Task (`ansible.builtin.shell: marksync agent ...`) |
| Step (SCRIPT) | → | Task (`ansible.builtin.shell: python ...`) |
| Step (HUMAN) | → | Task (`ansible.builtin.pause: prompt`) |
| Step tags | → | `tags: [actor, step_name]` |

### Apache Airflow

**Spec:** https://airflow.apache.org/docs/
**Pliki:** `.py` (DAG file)

| marksync | → | Airflow |
|----------|---|---------|
| Pipeline | → | `DAG` |
| Step (LLM) | → | `PythonOperator` (calls marksync agent) |
| Step (SCRIPT) | → | `PythonOperator` / `BashOperator` |
| Step (HUMAN) | → | `ExternalTaskSensor` (wait for approval) |
| Step sequence | → | `task1 >> task2 >> task3` |

### n8n

**Spec:** https://docs.n8n.io/workflows/
**Pliki:** `.n8n.json`

| marksync | → | n8n |
|----------|---|-----|
| Pipeline | → | Workflow |
| Step (LLM) | → | HTTP Request node (Ollama API) |
| Step (SCRIPT) | → | Code node (JavaScript) |
| Step (HUMAN) | → | Wait node (webhook approval) |
| Step sequence | → | Node connections |

---

## Tabela mapowań

### marksync ActorType → formaty BPM

| Actor | BPMN | XPDL | BPEL | PNML | EPC | CMMN | UML-AD |
|-------|------|------|------|------|-----|------|--------|
| **LLM** | serviceTask | TaskService | invoke | transition | function | processTask | CallBehaviorAction «ai-service» |
| **SCRIPT** | scriptTask | TaskScript | invoke | transition | function | processTask | CallBehaviorAction «script» |
| **HUMAN** | userTask | TaskUser | receive | transition | function | humanTask | CallBehaviorAction «user-task» |

### marksync ActorType → systemy zewnętrzne

| Actor | GitHub Actions | GitLab CI | K8s | Terraform | Ansible | Airflow | n8n |
|-------|---------------|-----------|-----|-----------|---------|---------|-----|
| **LLM** | Job step (shell) | Job (script) | initContainer | Container | shell task | PythonOperator | HTTP Request |
| **SCRIPT** | Job step (shell) | Job (script) | initContainer | Container | shell task | PythonOperator | Code node |
| **HUMAN** | Environment (approval) | manual job | Wait container | N/A | pause task | ExternalTaskSensor | Wait node |

---

## Użycie

### Python API

```python
from marksync.plugins import PluginRegistry
from marksync.plugins.base import PipelineSpec, StepSpec

# Inicjalizacja rejestru
registry = PluginRegistry()
registry.discover()

# Lista dostępnych pluginów
print(registry.available_formats())
# ['airflow', 'ansible', 'asyncapi', 'bpel', 'bpmn', 'cmmn', 'dmn',
#  'epc', 'github-actions', 'gitlab-ci', 'graphql', 'grpc', 'jsonschema',
#  'kubernetes', 'n8n', 'openapi', 'petri', 'terraform', 'uml-activity', 'xpdl']

# Definicja pipeline
pipeline = PipelineSpec(
    name="code-review",
    description="AI code review with human approval",
    steps=[
        StepSpec(name="llm-edit", actor="llm", config={"role": "editor"}),
        StepSpec(name="human-review", actor="human", config={"task_type": "approval"}),
        StepSpec(name="lint", actor="script", config={"script": "lint"}),
        StepSpec(name="deploy", actor="script", config={"script": "deploy"}),
    ],
)

# Export do BPMN 2.0
result = registry.export("bpmn", pipeline)
print(result.content)  # BPMN 2.0 XML

# Export do OpenAPI
result = registry.export("openapi", pipeline)
print(result.content)  # OpenAPI 3.1 YAML

# Export do GitHub Actions
result = registry.export("github-actions", pipeline)
print(result.content)  # .github/workflows/*.yml

# Import z BPMN
imported = registry.import_from("bpmn", bpmn_xml)
print(imported.steps)
```

### Z marksync Pipeline Engine

```python
from marksync.pipeline.engine import PipelineEngine
from marksync.plugins import PluginRegistry

engine = PipelineEngine()
engine.define_from_yaml(yaml_config)

# Konwersja istniejącej definicji
registry = PluginRegistry()
registry.discover()

for name, steps in engine.list_definitions().items():
    pipeline = registry.pipeline_from_marksync(name, steps)
    bpmn = registry.export("bpmn", pipeline)
    openapi = registry.export("openapi", pipeline)
```

---

## Tworzenie własnych pluginów

### Format Plugin

```python
from marksync.plugins.base import (
    FormatPlugin, PluginMeta, PluginType,
    PipelineSpec, ConversionResult,
)

class MyFormatPlugin(FormatPlugin):
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="My Custom Format",
            version="0.1.0",
            plugin_type=PluginType.FORMAT,
            format_id="my-format",
            description="Custom BPM format converter",
            file_extensions=[".myf"],
            capabilities=["export", "import"],
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        # Convert pipeline to your format
        content = f"PIPELINE {pipeline.name}\n"
        for step in pipeline.steps:
            content += f"  STEP {step.name} {step.actor}\n"
        return ConversionResult(ok=True, format_id="my-format", content=content)

    def import_pipeline(self, source: str) -> PipelineSpec:
        # Parse your format into PipelineSpec
        ...
```

### Rejestracja

```python
from marksync.plugins import PluginRegistry

registry = PluginRegistry()
registry.discover()                      # built-in plugins
registry.register(MyFormatPlugin())      # custom plugin
```

### Konwencja: klasa `Plugin`

Każdy plik pluginu musi eksportować klasę `Plugin` (z dużej litery), która jest automatycznie wykrywana przez `PluginRegistry`:

```python
# marksync/plugins/formats/my_format.py
class Plugin(FormatPlugin):
    ...
```

---

## Kanały komunikacji

> **Pełna dokumentacja:** [docs/channels.md](./channels.md)
> **Konfiguracja YAML:** [`examples/channels/channel_config.yaml`](../examples/channels/channel_config.yaml)
> **Testy E2E:** [`examples/channels/test_channels_e2e.py`](../examples/channels/test_channels_e2e.py)

| Kanał | Typ | Driver | Użycie |
|---|---|---|---|
| **WebSocket** | Human↔Machine | `websocket` | Browser UI, live editing |
| **HTTP Webhook** | Human↔Machine | `http_webhook` | Approval links, callbacks |
| **CLI stdio** | Human↔Machine | `cli_stdio` | Terminal dev/test |
| **Slack Bot** | Human↔Machine | `slack` | Chat approvals |
| **SSE** | Broadcast | `sse` | Dashboard push |
| **MQTT 5.0** | Machine↔Machine | `mqtt` | Agent messaging (QoS 0/1/2) |
| **Redis Pub/Sub** | Machine↔Machine | `redis_pubsub` | In-cluster signaling |
| **AMQP/RabbitMQ** | Machine↔Machine | `amqp` | Reliable task queues |
| **NATS** | Machine↔Machine | `nats` | Cloud-native request/reply |
| **gRPC Stream** | Machine↔Machine | `grpc_stream` | High-performance typed RPC |

E2E test infrastructure:
```bash
docker compose -f examples/channels/docker-compose.e2e.yml up -d
python examples/channels/test_channels_e2e.py
```

---

## BPMN Multi-Agent Patterns — Komunikacja synchroniczna i asynchroniczna

### Architektura komunikacji agentów w BPMN

```
┌────────────────────────────────────────────────────────────────────┐
│                    marksync Multi-Agent BPMN                       │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Pool: Editor System                                         │   │
│  │ ┌──────────────┐  sync   ┌──────────────┐                   │   │
│  │ │ Lane: Editor  │───────→│Lane: Formatter│──✉throw(ready)   │   │
│  │ │ ☐ serviceTask │  seqF  │ ☐ scriptTask  │                  │   │
│  │ └──────────────┘         └──────────────┘                   │   │
│  └─────────────────────────────┬───────────────────────────────┘   │
│                                │ messageFlow (async, dashed)       │
│  ┌─────────────────────────────▼───────────────────────────────┐   │
│  │ Pool: Review System                                         │   │
│  │ ┌──────────────┐         ┌──────────────┐                   │   │
│  │ │Lane: Reviewer │  ◆AND  │Lane: Approver │                  │   │
│  │ │ ☐☐☐ ||| task  │──fork──│ ☐ userTask    │──✉throw(ok)      │   │
│  │ │(multi-inst.)  │  join  │ (approval)    │                  │   │
│  │ └──────────────┘         └──────────────┘                   │   │
│  └─────────────────────────────┬───────────────────────────────┘   │
│                                │ messageFlow (async)               │
│  ┌─────────────────────────────▼───────────────────────────────┐   │
│  │ Pool: Deployment System                                     │   │
│  │ ✉catch(ok) ──→ ☐ Deploy ──→ ☐ Monitor ──→ ●                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘

Legenda:
  ──→  sequenceFlow (sync, w obrębie pool)
  - -→ messageFlow (async, między pool-ami)
  ☐    task (serviceTask / scriptTask / userTask)
  ☐☐☐  multi-instance task |||
  ◆    gateway (AND/XOR/OR/Event)
  ✉    message event (throw/catch)
  ○    startEvent
  ●    endEvent
```

### Pools i Lanes — role agentów

**Pool** = niezależny uczestnik / system agentów (komunikacja async przez messageFlow)
**Lane** = rola agenta wewnątrz jednego systemu (komunikacja sync przez sequenceFlow)

```python
from marksync.plugins import Pool, Lane

# Pool dla niezależnych systemów (B2B-like, async)
pools = [
    Pool(
        id="editor-system",
        name="Editor System",
        agent_type="llm",
        lanes=[
            Lane(id="editor", name="Editor", role="editor", step_refs=["llm-edit"]),
            Lane(id="formatter", name="Formatter", role="formatter", step_refs=["auto-format"]),
        ],
    ),
    Pool(
        id="review-system",
        name="Review System",
        agent_type="llm",
        lanes=[
            Lane(id="reviewer", name="Reviewer", role="reviewer", step_refs=["llm-review"]),
            Lane(id="approver", name="Approver", role="approver", step_refs=["human-approve"]),
        ],
    ),
]
```

### Multi-instance tasks ||| — wielu agentów równolegle

BPMN multi-instance (oznaczenie: |||) uruchamia N instancji zadania — idealne dla wielu agentów przetwarzających równocześnie:

```python
from marksync.plugins import StepSpec, MultiInstanceType, CommMode

# 3 agenci LLM reviewerzy analizują kod równolegle
review_step = StepSpec(
    name="llm-review",
    actor="llm",
    config={"role": "reviewer", "model": "qwen2.5-coder:7b"},
    multi_instance=MultiInstanceType.PARALLEL,    # ||| (trzy paski)
    collection=["block-api", "block-db", "block-ui"],  # dane dla każdej instancji
    completion_condition="allCompleted",           # AND: czekaj na wszystkich
    comm_mode=CommMode.SYNC,
)

# Sekwencyjne przetwarzanie (jeden po drugim)
sequential_step = StepSpec(
    name="llm-translate",
    actor="llm",
    multi_instance=MultiInstanceType.SEQUENTIAL,  # jeden po drugim
    collection=["en", "de", "pl", "ja"],
)
```

| MultiInstanceType | BPMN | Zachowanie |
|---|---|---|
| `PARALLEL` | `isSequential="false"` | Wszystkie instancje uruchomione jednocześnie |
| `SEQUENTIAL` | `isSequential="true"` | Instancje uruchamiane jedna po drugiej |
| `NONE` | brak | Pojedyncza instancja (domyślne) |

### Komunikacja synchroniczna — Service Tasks

Synchroniczna = proces **blokuje** do otrzymania odpowiedzi.
W BPMN: `serviceTask` z bezpośrednim wywołaniem usługi.

```python
# Agent A wywołuje agenta B synchronicznie (blokuje do odpowiedzi)
sync_step = StepSpec(
    name="llm-edit",
    actor="llm",
    config={"role": "editor"},
    comm_mode=CommMode.SYNC,     # ← blokujące wywołanie
)
```

W obrębie **jednego Pool** — sequence flows (strzałki →):
```
☐ LLM Edit ──→ ☐ Auto-format ──→ ☐ Lint
   (sync)           (sync)          (sync)
```

### Komunikacja asynchroniczna — Message Events

Asynchroniczna = nadawca **nie czeka** na odpowiedź (fire-and-forget + callback).
W BPMN: `intermediateThrowEvent` (wysyłanie) i `intermediateCatchEvent` (odbiór).

```python
from marksync.plugins import MessageFlow

# Agent wysyła wiadomość async (nie blokuje)
throw_step = StepSpec(
    name="auto-format",
    actor="script",
    pool="editor-system",
    comm_mode=CommMode.ASYNC,
    message_ref="edit-ready",
    is_throwing=True,               # ← wysyła (throw event)
)

# Inny agent czeka na wiadomość (catch)
catch_step = StepSpec(
    name="llm-review",
    actor="llm",
    pool="review-system",
    comm_mode=CommMode.ASYNC,
    message_ref="edit-ready",
    is_throwing=False,              # ← odbiera (catch event)
)

# Message flow między pool-ami (linia przerywana w BPMN)
msg_flow = MessageFlow(
    id="mf-edit-to-review",
    name="Edit ready for review",
    source_pool="editor-system",
    source_step="auto-format",
    target_pool="review-system",
    target_step="llm-review",
    message_name="edit-ready",
    comm_mode=CommMode.ASYNC,
)
```

**Pattern request-acknowledge-callback:**
```
Pool A:  ☐ Task ──→ ✉ throw(request) ──→ ...
                        │
                   - - -┤- - -  (message flow, async)
                        ▼
Pool B:         ✉ catch(request) ──→ ☐ Process ──→ ✉ throw(response)
                                                        │
                   - - - - - - - - - - - - - - - - - - -┤
                                                        ▼
Pool A:  ... ──→ ✉ catch(response) ──→ ☐ Continue
```

### Gateways — koordynacja agentów

| Gateway | BPMN | Opis | Użycie |
|---|---|---|---|
| **PARALLEL (AND)** | `parallelGateway` | Wszystkie ścieżki równolegle | Fork: editor + reviewer + tester równocześnie |
| **EXCLUSIVE (XOR)** | `exclusiveGateway` | Dokładnie jedna ścieżka | Route: approved → deploy, rejected → re-edit |
| **INCLUSIVE (OR)** | `inclusiveGateway` | Jedna lub więcej ścieżek | Wybierz agentów: security AND/OR performance |
| **EVENT** | `eventBasedGateway` | Pierwszy event wygrywa | Race: pierwszy agent z odpowiedzią |

```python
from marksync.plugins import Gateway, GatewayType

# AND fork → agenci pracują równolegle → AND join
fork = Gateway(
    id="fork-reviewers",
    gateway_type=GatewayType.PARALLEL,
    direction="diverging",         # fork (rozdzielenie)
)
join = Gateway(
    id="join-reviewers",
    gateway_type=GatewayType.PARALLEL,
    direction="converging",        # join (synchronizacja)
)

# XOR: routing na podstawie wyniku approval
approval_gate = Gateway(
    id="approval-check",
    name="Approval result?",
    gateway_type=GatewayType.EXCLUSIVE,
    direction="diverging",
    conditions={
        "deploy": "approval == 'approved'",
        "senior-llm-edit": "approval == 'rejected'",
    },
    default_path="senior-llm-edit",
)
```

### Gotowe scenariusze — `examples/bpmn_multiagent.py`

| # | Scenariusz | Elementy BPMN | Opis |
|---|---|---|---|
| 1 | Parallel Code Review | AND gateway, multi-instance ||| | 3 LLM reviewerzy równolegle → human approval |
| 2 | Async Notification | 2 pools, messageFlow, throw/catch | Editor wysyła async do Notifier |
| 3 | Approval Gateway | XOR gateway, conditions | approved → deploy, rejected → senior re-edit |
| 4 | Full Collaboration | 3 pools, lanes, messages, ||| gateways | Editor → Review → Deploy (sync + async) |

```bash
python3 examples/bpmn_multiagent.py
# Generuje pliki .bpmn w examples/output/
# Otwórz w: Camunda Modeler, BPMN.io, lub dowolnym edytorze BPMN 2.0
```

### Tabela: CommMode → BPMN element

| CommMode | BPMN Element | Zachowanie | Użycie |
|---|---|---|---|
| `SYNC` | `serviceTask` / `sequenceFlow` | Blokuje do odpowiedzi | Wewnątrz pool, agent → agent bezpośrednio |
| `ASYNC` | `intermediateThrowEvent` + `intermediateCatchEvent` | Fire-and-forget + callback | Między pool-ami, message flows |
| `FIRE_FORGET` | `intermediateThrowEvent` (tylko throw) | Wyślij i zapomnij | Notyfikacje, logi, metryki |

### Referencje

- [BPMN 2.0 Spec (OMG ISO 19510)](https://www.omg.org/spec/BPMN/2.0/)
- [Camunda: Sync vs Async BPMN](https://camunda.com/blog/2013/11/bpmn-service-synchronous-asynchronous/)
- [Agentic BPMN (arXiv:2412.05958)](https://arxiv.org/html/2412.05958v3)
- [Coordinating AI Teams across BPMN Lanes](https://community.latenode.com/t/coordinating-autonomous-ai-teams-across-bpmn-lanes)
- [Multi-instance Tasks (Spiff Arena)](https://spiff-arena.readthedocs.io/en/latest/reference/bpmn/multiinstance_tasks.html)
- [Camunda Agentic Orchestration](https://docs.camunda.io/docs/guides/getting-started-agentic-orchestration/)

---

*Plugin system v0.3.0 — 30 pluginów (8 formatów BPM + 5 adapterów API + 7 integracji + 10 kanałów) + multi-agent BPMN*

**Powiązane dokumenty:**
- [Kanały komunikacji](./channels.md) — Human↔Machine, Machine↔Machine
- [Formaty BPM](./formats.md) — BPMN, XPDL, BPEL, Petri, EPC, DMN, CMMN, UML
- [Adaptery API](./api-adapters.md) — OpenAPI, AsyncAPI, GraphQL, gRPC, JSON Schema
- [Integracje](./integrations.md) — GitHub, GitLab, K8s, Terraform, Ansible, Airflow, n8n
- [Pipeline Generation](./generate.md) — Prompt → LLM → Docker
- [Porównania](./comparisons/) — vs Camunda, n8n, Airflow, Temporal, IaC
- [DSL Reference](./dsl-reference.md)
- [Architecture](./architecture.md)
- [API](./api.md)
