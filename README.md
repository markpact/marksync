# marksync: GitOps meets AI Agents -> all in one README


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.2.29-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$2.40-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-10.9h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $2.3972 (30 commits)
- 👤 **Human dev:** ~$1090 (10.9h @ $100/h, 30min dedup)

Generated on 2026-06-18 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

Multi-agent collaborative editing and deployment of [Markpact](https://github.com/wronai/markpact) projects via CRDT delta sync.

```
pip install marksync[all]
```

**Version:** 0.2.23


## Przykład

Wyobraź sobie, że piszesz jedno zdanie ("zbuduj mi API do zamówień z ludzkim zatwierdzaniem płatności"), a system generuje z tego jeden plik Markdown, w którym jest wszystko: konfiguracja pipeline'u, kod aplikacji, komendy uruchomienia, konfiguracja deploymentu, aktualny stan procesu i historia zdarzeń. Potem ten sam plik jest czytany przez silnik, który krok po kroku wykonuje pipeline — część robią skrypty, część AI, a przy krytycznych decyzjach czeka na człowieka. Na końcu wzorzec sukcesu jest zapisywany, żeby następnym razem było szybciej.
Kluczowa idea: jeden plik = kontrakt + kod + stan + logi + deployment.

```bash
python demos/demo_live_marksync.py --prompt "Build a todo API"
source venv/bin/activate && python -m marksync.cli create "Build a chat API with WebSocket"
```

+ [marksync_flow.pdf](marksync_flow.pdf)
+ [marksync_live_custom.pdf](generated/live/marksync_live_custom.pdf)

```yaml markpact:orchestration
pipeline:
name: order-api
steps:
  - name: parse_order
    actor: script
  - name: check_inventory
    actor: llm
  - name: fraud_detection
    actor: script
  - name: human_payment_approval
    actor: human
    config: {channel: web, timeout: 7200}
  - name: process_payment
    actor: script
  - name: deploy_update
    actor: llm
```


### Jaki system z rynku to przypomina?

MarkSync jest hybrydą kilku koncepcji, ale najbliżej mu do tych systemów:

**Najbliższy odpowiednik: [Dagger.io](https://dagger.io/) + [CrewAI](https://crewai.com/) + [Jupyter Notebooks](https://jupyter.org/)**

- **Dagger.io** — pipeline-as-code w jednym pliku, determinizm, powtarzalność, ale Dagger nie ma AI ani human-in-the-loop
- **CrewAI / AutoGen** — multi-agent orchestration z różnymi rolami, ale te systemy nie mają CRDT ani kontraktowego podejścia do jednego pliku
- **Pulumi / Terraform** — Infrastructure as Code z deklaratywnym stanem, ale bez agentów AI i bez self-learningu
- **n8n / Temporal.io** — workflow orchestration z human tasks i retry policies, ale bez Markdown-as-contract
- **Jupyter Notebooks** — plik, który jest jednocześnie kodem, dokumentacją i wynikiem wykonania — filozoficznie najbliżej konceptu "README jako żywy dokument"




## What it does

Multiple AI agents work simultaneously on a single Markpact `README.md` — editing code, reviewing quality, deploying changes — all synchronized in real-time through delta patches (only changed code blocks are transmitted, not the entire file).

A built-in **DSL** (Domain-Specific Language) lets you orchestrate agents, define pipelines, and control the entire architecture from an interactive shell or via REST/WebSocket API. A **Pipeline Engine** supports human-in-the-loop approval steps alongside LLM and script actors. A **Plugin System** enables export/import to BPMN, n8n, Airflow, Kubernetes, GitHub Actions, and more.

```
┌─────────────────────────────────────────────────────────────────┐
│                      marksync Runtime                           │
│                                                                 │
│  .env ─────────► settings.py ◄── hardware_detect.py             │
│                       │                                         │
│  agents.yml ──► Orchestrator ──┬──► editor · reviewer           │
│  (define once)  (1 process)    ├──► deployer · monitor          │
│                                └──► ConversationAgent           │
│                                       │                         │
│  ┌──────────────┐    ┌────────────────┼────────────────────┐    │
│  │  DSL Shell   │───►│    DSL Executor │                   │    │
│  │  REST API    │───►│  agents · pipelines · routes        │    │
│  │  WS API      │───►│  macros · webhooks · state          │    │
│  │  Dashboard   │───►│                                     │    │
│  │  Sandbox UI  │───►│                                     │    │
│  └──────────────┘    └────────────────┬────────────────────┘    │
│                                       │                         │
│  ┌───────────────┐   ┌────────────────┴───────────────────┐     │
│  │ PipelineEngine│──►│        SyncServer (WS:8765)        │     │
│  │ LLM·Script·   │   │  CRDT doc · delta patches · persist│     │
│  │ Human steps   │   └────────────────┬───────────────────┘     │
│  └───────────────┘                    ▼                         │
│                                README.md (disk)                 │
│                                                                 │
│  Plugin System: BPMN · n8n · Airflow · K8s · GitHub · Ansible   │
│  Channels: SSE · WebSocket · MQTT · Redis · AMQP · NATS · Slack │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

**Ollama** running locally (recommended) or a cloud LLM provider:

```bash
# Install ollama: https://ollama.ai
ollama pull qwen2.5-coder:7b
ollama serve  # keep running
```

Run `marksync init` to auto-detect your GPU/RAM and configure the best model.

## Quick Start — First Run Wizard

```bash
pip install marksync[all]
marksync init
```

The `init` wizard:
- Detects GPU (NVIDIA/AMD) and RAM via `hardware_detect`
- Suggests a model based on available VRAM
- Lets you choose: Ollama, OpenRouter, OpenAI, Anthropic, or custom LiteLLM
- Tests the connection and saves config to `.env`

## Quick Start — Docker Compose

```bash
git clone https://github.com/wronai/marksync.git
cd marksync
docker compose up --build
```

This starts 4 services (not 1-per-agent — all agents run in a single orchestrator):

| Container | Role | What it does |
|-----------|------|-------------|
| `sync-server` | Hub | WebSocket server, persists README.md, broadcasts changes |
| `orchestrator` | Agents | Reads `agents.yml`, spawns all agents in 1 process |
| `api-server` | API | REST/WS API for remote DSL control |
| `init-project` | Seed | Copies `examples/1/README.md` into shared volume |

Agent definitions live in `agents.yml` — define once, use everywhere:

```yaml
# agents.yml
agents:
  editor-1:   { role: editor, auto_edit: true }
  reviewer-1: { role: reviewer }
  deployer-1: { role: deployer }
  monitor-1:  { role: monitor }
pipelines:
  review-flow: { stages: [editor-1, reviewer-1] }
```

Then push changes from your host:

```bash
pip install -e .
marksync push README.md
marksync blocks examples/1/README.md
```

## Quick Start — Without Docker

```bash
pip install -e .

# Terminal 1: Start sync server
marksync server examples/1/README.md

# Terminal 2: Start all agents from agents.yml
marksync orchestrate -c agents.yml

# Terminal 3: Web sandbox (edit & test in browser)
marksync sandbox
# Open http://localhost:8888
```

Or start agents individually:

```bash
marksync agent --role editor --name editor-1
```

## DSL — Agent Orchestration

The marksync DSL lets you control agents, pipelines, and architecture from a shell or API.

### Interactive Shell

```bash
marksync shell
```

```
marksync> AGENT coder editor --model qwen2.5-coder:7b --auto-edit
marksync> AGENT reviewer-1 reviewer
marksync> AGENT watcher monitor
marksync> PIPE review-flow coder -> reviewer-1 -> deployer-1
marksync> ROUTE markpact:run -> deployer-1
marksync> LIST agents
marksync> STATUS
```

### Orchestrate from agents.yml

```bash
# Dry-run — preview the plan
marksync orchestrate --dry-run

# Run all agents
marksync orchestrate -c agents.yml

# Run only editors
marksync orchestrate --role editor
```

### REST / WebSocket API

```bash
# Start the API server
marksync api --port 8080
```

```bash
# Execute DSL commands via REST
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "AGENT coder editor --auto-edit"}'

# List agents
curl http://localhost:8080/api/v1/agents

# WebSocket: ws://localhost:8080/ws/dsl
# Swagger docs: http://localhost:8080/docs
```

See [docs/dsl-reference.md](docs/dsl-reference.md) and [docs/api.md](docs/api.md) for full reference.

## CLI Reference

```
marksync init                                                    # First-run wizard (LLM provider + model setup)
marksync server README.md [--host H] [--port P] [--ssl-cert F] [--ssl-key F] [--git-auto-commit] [--rate-limit N]
marksync agent --role ROLE --name NAME [--model M] [--auto-edit] [--server-uri ws://...]
marksync orchestrate [-c agents.yml] [--role ROLE] [--dry-run] [--export-dsl FILE]
marksync push README.md [--server-uri ws://...] [--name NAME]
marksync blocks README.md
marksync shell [--server-uri ws://...] [--ollama-url URL] [--script FILE]
marksync api [--host H] [--port P] [--server-uri ws://...] [--ollama-url URL]
marksync sandbox [--host H] [--port P]
marksync generate PROMPT [--output DIR] [--model M] [--dry-run] [--build] [--up]
marksync create PROMPT [--output DIR] [--no-llm] [--deploy] [--open-dashboard] [--env KEY=VAL]
marksync dashboard [--contract README.md] [--port P] [--host H] [--sync-server ws://...]
marksync snapshot CONTRACT [--label TEXT]
marksync rollback CONTRACT [--snapshot ID] [--list]
```

All commands read defaults from `.env` — no need to pass `--server-uri`, `--ollama-url` etc.

## Agent Roles

### Editor (`--role editor`)

Receives block updates, sends code to Ollama for improvement (error handling, type hints, docstrings). Use `--auto-edit` to automatically push improvements back to server.

### Reviewer (`--role reviewer`)

Analyzes every changed block for bugs, security issues, and best practices. Results are logged — does not modify code.

### Deployer (`--role deployer`)

Watches for changes to `markpact:run` and `markpact:deps` blocks. Triggers `markpact README.md --run` to rebuild and redeploy the application.

### Monitor (`--role monitor`)

Logs every block change with block ID, content size, and SHA-256 hash. Useful for audit trails and debugging.

### ConversationAgent (`--role conversation`)

Processes `markpact:conversation` blocks through an LLM conversation engine, maintaining full history in CRDT.

### PactownMonitor (`--role pactown-monitor`)

Polls Pactown service health, writes `markpact:state` and `markpact:log` blocks, and triggers the `pactown-autofix` pipeline on degraded health.

## Pipeline Engine

The pipeline engine supports 3 actor types in any combination:

| Actor | Execution | Use cases |
|-------|-----------|-----------|
| **LLM** | Async, automatic | Code editing, doc writing, root-cause analysis |
| **SCRIPT** | Sync, deterministic | Lint, validate, format, deploy, fraud-check |
| **HUMAN** | Blocks until API resolve | Code review, payment authorization, content moderation |

```python
from marksync.pipeline.engine import PipelineEngine, Step

engine = PipelineEngine()
engine.define("code-review", [
    Step(name="edit",   actor="llm",    prompt="Improve this code"),
    Step(name="review", actor="human",  description="Approve changes"),
    Step(name="lint",   actor="script", script="lint"),
    Step(name="deploy", actor="script", script="deploy"),
])
run_id = await engine.start("code-review", input_data={"code": "..."})
```

Built-in demo pipelines: `code-review`, `account-creation`, `payment`, `doc-generation`, `incident-response`, `content-moderation`, `data-migration`.

Retry/timeout per step, idempotency keys, CRDT-persisted run history, and event hooks are all supported.

## Plugin System

### Process Formats

Export/import pipelines to standard process formats:

| Format | ID | Description |
|--------|----|-------------|
| BPMN 2.0 | `bpmn` | Full collaboration with pools/lanes, multi-agent |
| XPDL | `xpdl` | XML Process Definition Language |
| Petri Net | `petri` | Petri Net XML |
| DMN | `dmn` | Decision Model and Notation |
| CMMN | `cmmn` | Case Management Model and Notation |
| EPC | `epc` | Event-driven Process Chain |
| UML Activity | `uml-activity` | UML Activity Diagram |
| BPEL | `bpel` | Business Process Execution Language |

### Integrations

| System | ID | Output |
|--------|----|--------|
| Kubernetes | `kubernetes` | K8s Job YAML |
| GitLab CI | `gitlab` | `.gitlab-ci.yml` |
| GitHub Actions | `github` | Workflow YAML |
| Apache Airflow | `airflow` | Python DAG |
| Ansible | `ansible` | Playbook YAML |
| n8n | `n8n` | Workflow JSON |
| Terraform | `terraform` | HCL |
| Pactown | `pactown` | `pactown.yaml` |

### API Adapters

| Schema | ID | Output |
|--------|----|--------|
| OpenAPI 3.0 | `openapi` | YAML spec |
| AsyncAPI | `asyncapi` | YAML spec |
| GraphQL | `graphql` | `.graphql` schema |
| gRPC | `grpc` | `.proto` file |
| JSON Schema | `jsonschema` | JSON |

### Channels

| Channel | Protocol | Use case |
|---------|----------|----------|
| `sse` | HTTP SSE | Browser push notifications |
| `websocket` | WS | Bidirectional real-time |
| `mqtt` | MQTT | IoT / edge agents |
| `redis` | Redis Pub/Sub | High-throughput events |
| `amqp` | AMQP/RabbitMQ | Reliable message queuing |
| `nats` | NATS | Cloud-native messaging |
| `grpc` | gRPC streaming | High-performance binary |
| `slack` | Slack API | Human notifications |
| `http-webhook` | HTTP POST | External integrations |
| `cli-stdio` | stdin/stdout | Local scripting |

## Python API

```python
from marksync import SyncServer, SyncClient, AgentWorker
from marksync.agents import AgentConfig

# Start server programmatically
server = SyncServer(readme="README.md", port=8765)
await server.run()

# Push changes
client = SyncClient(readme="README.md", uri="ws://localhost:8765")
patches, saved = await client.push_changes()

# Start an agent
config = AgentConfig(
    name="my-agent", role="reviewer",
    server_uri="ws://localhost:8765",
    ollama_url="http://localhost:11434",
    ollama_model="qwen2.5-coder:7b",
)
agent = AgentWorker(config)
await agent.run()

# DSL — programmatic orchestration
from marksync.dsl import DSLExecutor
executor = DSLExecutor(server_uri="ws://localhost:8765")
await executor.execute("AGENT coder editor --auto-edit")
await executor.execute("PIPE review coder -> reviewer")
await executor.execute("MACRO deploy-all = PIPE $1 editor-1 -> reviewer-1 -> deployer-1")
print(executor.snapshot())

# Pipeline engine — human-in-the-loop
from marksync.pipeline.engine import PipelineEngine, Step
engine = PipelineEngine()
engine.define("review", [
    Step(name="edit",   actor="llm",    prompt="Improve this code"),
    Step(name="review", actor="human",  description="Approve changes"),
    Step(name="deploy", actor="script", script="deploy"),
])
run_id = await engine.start("review", input_data={"code": "..."})

# Contract generation from natural language
from marksync.intent.parser import IntentParser
from marksync.contract.generator import ContractGenerator
from marksync.sync.crdt import CRDTDocument

crdt = CRDTDocument()
intent = IntentParser(crdt_doc=crdt).parse("REST API for task management")
contract = ContractGenerator(crdt_doc=crdt).generate(intent)

# Pattern learning
from marksync.learning.patterns import PatternLibrary
library = PatternLibrary()
library.save_from_contract("./my-service", intent, success=True)

# Plugin export
from marksync.plugins.registry import PluginRegistry
registry = PluginRegistry()
registry.discover()
result = registry.export("bpmn", pipeline)
result = registry.export("github", pipeline)
```

## Sync Protocol

Communication uses JSON messages over WebSocket:

| Direction | Type | Description |
|-----------|------|-------------|
| S→C | `manifest` | `{block_id: sha256}` map on connect |
| C→S | `patch` | diff-match-patch delta for one block |
| C→S | `full` | Full block content (fallback) |
| S→C | `ack` | Confirmation with sequence number |
| S→C | `nack` | Patch failed, hash mismatch |
| S→C | `patch`/`full` | Broadcast to other clients |
| C→S | `get_snapshot` | Request full README markdown |
| S→C | `snapshot` | Full README content |

Delta strategy: if patch < 80% of full content → send patch. Otherwise send full block. SHA-256 hash verification on every apply.

## Project Structure

```
marksync/
├── .env                     # Centralized config (ports, hosts, model, LLM provider)
├── agents.yml               # Agent definitions (single source of truth)
├── pyproject.toml           # Package config (pip install .)
├── Dockerfile               # Single image for server + agents
├── docker-compose.yml       # 4 services (server, orchestrator, api, init)
├── docs/
│   ├── architecture.md      # System design & data flow
│   ├── dsl-reference.md     # DSL command reference
│   ├── api.md               # REST & WebSocket API docs
│   ├── pipelines.md         # Pipeline engine guide
│   ├── plugins.md           # Plugin system reference
│   ├── channels.md          # Channel transports reference
│   ├── formats.md           # Process format export/import
│   ├── integrations.md      # External system integrations
│   ├── api-adapters.md      # API schema generation
│   └── comparison.md        # vs Airflow, Camunda, n8n, Temporal
├── examples/
│   ├── 1/                   # Task Manager API
│   ├── 2/                   # Chat WebSocket App
│   ├── 3/                   # Data Pipeline CLI
│   ├── bpmn_multiagent.py   # BPMN multi-agent export scenarios
│   └── channels/            # Channel E2E tests (MQTT, Redis, AMQP, NATS, SSE)
├── marksync/
│   ├── __init__.py          # Package exports (lazy imports)
│   ├── cli.py               # Click CLI (init, server, agent, orchestrate, generate,
│   │                        #   create, dashboard, snapshot, rollback, sandbox, ...)
│   ├── settings.py          # Centralized config from .env (Settings, load_settings)
│   ├── hardware_detect.py   # GPU/RAM detection, Ollama check, model suggestion
│   ├── orchestrator.py      # Reads agents.yml, spawns agents (Orchestrator, OrchestrationPlan)
│   ├── dsl/
│   │   ├── parser.py        # DSLParser, DSLCommand, brace expansion
│   │   ├── executor.py      # DSLExecutor (agents, pipelines, routes, macros, webhooks, state)
│   │   ├── shell.py         # Interactive REPL (DSLShell, readline completion)
│   │   └── api.py           # FastAPI REST + WebSocket endpoints
│   ├── sync/
│   │   ├── __init__.py      # BlockParser, MarkpactBlock
│   │   ├── crdt.py          # CRDTDocument (pycrdt/Yjs, snapshot, rollback, GC)
│   │   ├── engine.py        # SyncServer, SyncClient, MultiProjectServer
│   │   └── snapshots.py     # SnapshotStore (save, list, load, restore, prune)
│   ├── pipeline/
│   │   ├── engine.py        # PipelineEngine (LLM/SCRIPT/HUMAN steps, retry, events)
│   │   ├── api.py           # Pipeline REST API (tasks, resolve, demo pipelines)
│   │   ├── llm_client.py    # LLMClient (LiteLLM), LLMConfig, LLMResponse
│   │   └── prompt_generator.py  # PromptGenerator, PromptSpec, GeneratedService
│   ├── contract/
│   │   ├── block_types.py   # Block type constants, EnvProfile, GeneratedContract
│   │   ├── generator.py     # ContractGenerator (intent → 10 contract blocks)
│   │   └── templates.py     # RestAPITemplate, WebAppTemplate, CLITemplate, WorkerTemplate
│   ├── intent/
│   │   ├── parser.py        # IntentParser, ProcessIntent (heuristic + LLM)
│   │   └── yaml_generator.py  # YAMLGenerator (intent → pipeline + orchestration YAML)
│   ├── conversation/
│   │   └── engine.py        # ConversationEngine (history, CRDT persistence, LLM)
│   ├── learning/
│   │   ├── feedback.py      # FeedbackCollector (approve, reject, complete_run)
│   │   ├── patterns.py      # Pattern, PatternLibrary (save, find, score)
│   │   └── prompt_refiner.py  # PromptRefiner (analyze history, refine prompts)
│   ├── auth/
│   │   ├── tokens.py        # create_token, verify_token (JWT or HMAC fallback)
│   │   ├── roles.py         # Role enum, has_permission
│   │   └── middleware.py    # AuthMiddleware, get_current_user, require_role
│   ├── dashboard/
│   │   └── app.py           # Dashboard FastAPI app (contract lifecycle UI, SSE)
│   ├── sandbox/
│   │   └── app.py           # Web sandbox UI (edit, test, orchestrate)
│   ├── agents/
│   │   └── __init__.py      # AgentWorker, AgentConfig, OllamaClient,
│   │                        #   ConversationAgent, PactownMonitor
│   ├── transport/
│   │   └── __init__.py      # TransportLayer, WebSocketTransport, MQTTTransport
│   └── plugins/
│       ├── base.py          # FormatPlugin, APIAdapter, Integration, Channel,
│       │                    #   PipelineSpec, StepSpec, Pool, Lane, Gateway
│       ├── registry.py      # PluginRegistry (discover, export, import_from)
│       ├── formats/         # bpmn, xpdl, petri, dmn, cmmn, epc, uml-activity, bpel
│       ├── integrations/    # kubernetes, gitlab, github, airflow, ansible, n8n,
│       │                    #   terraform, pactown
│       ├── api/             # openapi, asyncapi, graphql, grpc, jsonschema
│       └── channels/        # sse, websocket, mqtt, redis_pubsub, amqp, nats,
│                            #   grpc_stream, slack, http_webhook, cli_stdio
└── tests/
    ├── test_dsl.py              # DSL parser & executor (38 tests)
    ├── test_v2.py               # Contract, pipeline, agents v2 (101 tests)
    ├── test_pipeline.py         # Pipeline engine (24 tests)
    ├── test_pipeline_scenarios.py  # 7 end-to-end scenarios (32 tests)
    ├── test_examples.py         # Example block parsing (24 tests)
    ├── test_orchestrator.py     # Orchestrator & agents.yml (24 tests)
    ├── test_settings.py         # Settings & .env loading (13 tests)
    └── test_hardware_detect.py  # GPU/RAM detection (30 tests)
```

## Configuration

All config lives in two files:

| File | Purpose |
|------|----------|
| `.env` | Ports, hosts, model, log level |
| `agents.yml` | Agent definitions, pipelines, routes |

### Environment Variables (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `MARKSYNC_PORT` | `8765` | Sync server port |
| `MARKSYNC_SERVER` | `ws://localhost:8765` | Sync server URI |
| `MARKSYNC_API_PORT` | `8080` | DSL API port |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen2.5-coder:7b` | LLM model for agents |
| `MARKPACT_PORT` | `8088` | Markpact app port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LLM_PROVIDER` | `ollama` | LLM provider (`ollama`, `openrouter`, `openai`, `anthropic`, `litellm`) |
| `LLM_MODEL` | *(from provider)* | Model name for `marksync generate`/`create` |
| `LLM_API_KEY` | *(empty)* | API key for cloud providers |
| `LLM_API_BASE` | *(empty)* | Custom LiteLLM base URL |
| `MARKSYNC_AUTH_ENABLED` | `false` | Enable token auth for API/sync server |
| `MARKSYNC_SECRET_KEY` | *(random)* | JWT/HMAC signing key |

## Integration with Markpact

marksync is designed to work with [markpact](https://github.com/wronai/markpact):

```bash
# Install both
pip install markpact marksync[all]

# Edit collaboratively with marksync
marksync server README.md

# Deploy with markpact
markpact README.md --run
```

The deployer agent can automatically trigger `markpact` rebuilds when code blocks change.

## Documentation

- [Architecture](docs/architecture.md) — system design, layers, data flow
- [DSL Reference](docs/dsl-reference.md) — full command reference for the orchestration DSL
- [API Reference](docs/api.md) — REST & WebSocket API documentation
- [Pipelines](docs/pipelines.md) — pipeline engine, human-in-the-loop, retry, events
- [Plugins](docs/plugins.md) — plugin system, format export/import, integrations
- [Channels](docs/channels.md) — SSE, WebSocket, MQTT, Redis, AMQP, NATS, Slack
- [Formats](docs/formats.md) — BPMN, XPDL, Petri, DMN, CMMN, EPC, UML, BPEL
- [Integrations](docs/integrations.md) — Kubernetes, GitLab, GitHub, Airflow, Ansible, n8n, Terraform
- [API Adapters](docs/api-adapters.md) — OpenAPI, AsyncAPI, GraphQL, gRPC, JSON Schema
- [Comparison](docs/comparison.md) — vs Airflow, Camunda, n8n, Temporal, Kubernetes
- [Changelog](CHANGELOG.md) — version history
- [TODO](TODO.md) — roadmap and planned features

## License

Licensed under Apache-2.0.
## Author

Tom Sapletta
