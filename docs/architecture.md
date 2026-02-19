# marksync Architecture

## Overview

marksync is a multi-agent collaborative editing system for [Markpact](https://github.com/wronai/markpact) projects. It uses CRDT-based delta synchronization to allow multiple AI agents to concurrently edit a single `README.md` file without conflicts.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      marksync Runtime                           │
│                                                                 │
│  .env ─────────► settings.py (centralized config)               │
│                       │                                         │
│  agents.yml ──► Orchestrator ──┬──► editor-1                    │
│  (define once)  (1 process)    ├──► reviewer-1                  │
│                                ├──► deployer-1                  │
│                                └──► monitor-1                   │
│                                       │                         │
│  ┌──────────────┐    ┌────────────────┼────────────────────┐    │
│  │  DSL Shell   │───►│    DSL Executor │                   │    │
│  │  REST API    │───►│  agents · pipelines · routes        │    │
│  │  WS API      │───►│                                     │    │
│  │  Sandbox UI  │───►│                                     │    │
│  └──────────────┘    └────────────────┬────────────────────┘    │
│                                       │                         │
│                      ┌────────────────┴───────────────────┐     │
│                      │        SyncServer (WS:8765)        │     │
│                      │  CRDT doc · delta patches · persist│     │
│                      └────────────────┬───────────────────┘     │
│                                       ▼                         │
│                                README.md (disk)                 │
└─────────────────────────────────────────────────────────────────┘
```

## Layers

### 0. Configuration Layer

Two files control everything:

| File | Module | Purpose |
|------|--------|---------|
| `.env` | `marksync.settings` | Ports, hosts, model, log level |
| `agents.yml` | `marksync.orchestrator` | Agent definitions, pipelines, routes |

Priority: explicit args > `os.environ` > `.env` file > built-in defaults.

### 1. Orchestration Layer (`marksync.orchestrator`)

Reads `agents.yml` and spawns all agents as async tasks in a single process:

- **Orchestrator** — parses YAML, resolves config, manages agent lifecycle
- **OrchestrationPlan** — immutable plan with agents, pipelines, routes
- **CLI** — `marksync orchestrate [-c agents.yml] [--role ROLE] [--dry-run]`
- **Docker** — single `orchestrator` container replaces N agent containers

### 1b. Pipeline Engine (`marksync.pipeline`)

Universal pipeline with **3 actor types** sharing one abstract `Step` interface:

```
┌─────────────────────────────────────────────────────────────┐
│                       Pipeline Run                          │
│                                                             │
│  Step 1        Step 2         Step 3        Step 4          │
│  SCRIPT   →    LLM      →     HUMAN    →    SCRIPT          │
│  validate      generate       blocks        enforce         │
│  (auto)        (auto)         until API     (auto)          │
│                               resolve                       │
│                                                             │
│  Each step receives output_data of the previous step        │
│  Human steps block the asyncio.Future until resolved        │
└─────────────────────────────────────────────────────────────┘
```

| Actor Type | Execution | Examples |
|------------|-----------|----------|
| **LLM** | Async, automatic via Ollama (or simulated) | Code editing, doc writing, root-cause analysis |
| **SCRIPT** | Sync, deterministic Python callable | Lint, validate, format, deploy, fraud-check |
| **HUMAN** | Async, blocks until REST API response | Approve changes, authorize payment, sign off |

#### Human-in-the-loop Flow

```
Pipeline engine            REST API                  Human
      │                       │                        │
      │──── HUMAN step ──────►│                        │
      │     creates task      │◄── GET /tasks ─────────│
      │     blocks Future     │                        │
      │                       │──── task details ─────►│
      │                       │                        │ review
      │                       │◄── POST /tasks/{id} ───│ approve/reject
      │                       │    action=approve      │
      │◄── Future resolves ───│                        │
      │                       │                        │
      │──── next step ────────►                        │
```

1. Pipeline reaches a HUMAN step → creates `HumanTask(prompt, task_type, channel)`
2. Pipeline **blocks** on `asyncio.Future` — does not burn CPU
3. Human sees the task in sandbox UI or polls `GET /api/pipeline/tasks`
4. Human resolves via `POST /api/pipeline/tasks/{id}` → `{action: "approve"}`
5. Future resolves → pipeline continues (or fails if rejected and `required=True`)

**Actions:** `approve` · `reject` · `provide_input` · `complete`
**Channels:** `web` · `email` · `chat` · `webhook` (extensible)

#### 7 Built-in Demo Scenarios

All scenarios are accessible from the sandbox UI (`#/1/pipeline`) or via API.

| ID | Name | Actor sequence |
|----|------|----------------|
| `code-review` | Code Review | LLM → **Human** → Script → Script |
| `account-creation` | Account Creation | Script → **Human** → Script → **Human** |
| `payment` | Payment Authorization | Script → **Human** → Script → **Human** |
| `doc-generation` | Documentation Generation | Script → LLM → **Human** → LLM → Script |
| `incident-response` | Incident Response | Script → **Human** → LLM → **Human** → Script |
| `content-moderation` | Content Moderation | LLM → Script → **Human** → Script |
| `data-migration` | Data Migration | Script → LLM → **Human** → Script → **Human** |

#### Pipeline definition in `agents.yml`

```yaml
pipelines:
  doc-generation:
    steps:
      - name: scrape-api
        actor: script
        config: {script: validate}
      - name: write-docs
        actor: llm
        config: {role: doc-writer, prompt: "Write API docs with examples"}
      - name: human-review-docs
        actor: human
        config: {prompt: "Review the generated docs. Approve or comment.", task_type: approval, channel: web}
      - name: refine-docs
        actor: llm
        config: {role: doc-refiner, prompt: "Incorporate human review comments"}
      - name: publish-docs
        actor: script
        config: {script: deploy}
```

#### How to Run Pipelines

**1. Via sandbox UI** (recommended for demos):
```bash
marksync sandbox --port 8888
# open http://localhost:8888/#/1/pipeline
# click "Run Demo" on any scenario
# pending human tasks appear automatically — click Approve/Reject
```

**2. Via REST API**:
```bash
# Start a demo
curl -X POST http://localhost:8888/api/pipeline/demo \
     -H "Content-Type: application/json" \
     -d '{"scenario": "doc-generation"}'
# → {"run_id": "run-abc123", "scenario": "doc-generation", "message": "..."}

# Check status
curl http://localhost:8888/api/pipeline/runs/run-abc123

# List pending human tasks
curl http://localhost:8888/api/pipeline/tasks

# Resolve a task
curl -X POST http://localhost:8888/api/pipeline/tasks/task-xyz789 \
     -H "Content-Type: application/json" \
     -d '{"action": "approve", "response": {"comment": "LGTM"}, "resolved_by": "alice"}'

# Start any defined pipeline with custom input
curl -X POST http://localhost:8888/api/pipeline/start \
     -H "Content-Type: application/json" \
     -d '{"pipeline": "data-migration", "input_data": {"block_id": "x", "content": "..."}}'
```

**3. Via Python**:
```python
import asyncio
from marksync.pipeline.engine import PipelineEngine, Step, ActorType

engine = PipelineEngine()
engine.define("my-pipeline", [
    Step("validate",     ActorType.SCRIPT, config={"script": "validate"}),
    Step("llm-improve",  ActorType.LLM,    config={"role": "editor"}),
    Step("human-review", ActorType.HUMAN,  config={
        "prompt": "Approve the changes?",
        "task_type": "approval",
        "channel": "web",
    }),
    Step("deploy",       ActorType.SCRIPT, config={"script": "deploy"}),
])

async def main():
    run_id = await engine.start("my-pipeline", {
        "block_id": "my-file.py",
        "content": "def hello(): pass",
    })
    print(f"Started: {run_id}")
    # Poll tasks and resolve them...
    await asyncio.sleep(0.5)
    for task in engine.get_pending_tasks():
        engine.resolve_task(task.id, "approve", {}, "me")
    await asyncio.sleep(0.2)
    print(engine.get_run(run_id).status)  # completed

asyncio.run(main())
```

#### How to Test Pipelines

```bash
# All pipeline tests (23 original + 37 new scenario tests)
pytest tests/test_pipeline.py tests/test_pipeline_scenarios.py -v

# Only new scenario tests
pytest tests/test_pipeline_scenarios.py -v

# Single scenario class
pytest tests/test_pipeline_scenarios.py::TestDocGenerationScenario -v
pytest tests/test_pipeline_scenarios.py::TestIncidentResponseScenario -v
pytest tests/test_pipeline_scenarios.py::TestContentModerationScenario -v
pytest tests/test_pipeline_scenarios.py::TestDataMigrationScenario -v

# Cross-scenario integration tests
pytest tests/test_pipeline_scenarios.py::TestAllScenariosIntegration -v

# Full test suite
pytest tests/ -q
```

**What the tests cover per scenario:**
- Pipeline starts without error and returns a `run_id`
- Step sequence matches expected actor order (SCRIPT/LLM/HUMAN ordering)
- Pipeline blocks at human steps (status = `"blocked"`)
- Approving all tasks leads to `status = "completed"`
- Rejecting a required human step leads to `status = "failed"`
- Data flows between steps via `output_data` → next step's `input_data`
- `agents.yml` definitions parse correctly via `engine.define_from_yaml()`

Demo scenarios available in sandbox: code-review, account-creation, payment, doc-generation, incident-response, content-moderation, data-migration.

### 2. DSL Layer (`marksync.dsl`)

Imperative command interface for interactive/runtime control:

- **Parser** (`dsl/parser.py`) — tokenizes text commands into `DSLCommand` objects; brace expansion (`{1..5}`, `{a,b}`)
- **Executor** (`dsl/executor.py`) — executes commands, manages agent lifecycle, macros, webhooks, state persistence
- **Shell** (`dsl/shell.py`) — interactive REPL with readline tab completion + persistent history
- **API** (`dsl/api.py`) — REST/WebSocket endpoints

DSL v2 commands: `CREATE`, `DASHBOARD`, `LEARN`, `PATTERNS`, `MACRO`, `SAVE`/`LOAD` state.

### 3. Agent Layer (`marksync.agents`)

AI-powered workers that connect to the SyncServer and process block updates:

| Role | Class | Behavior |
|------|-------|----------|
| **editor** | `AgentWorker` | Sends code to LLM for improvement, pushes edits back |
| **reviewer** | `AgentWorker` | Analyzes code quality, logs findings (read-only) |
| **deployer** | `AgentWorker` | Watches `markpact:run`/`markpact:deps`, triggers builds |
| **monitor** | `AgentWorker` | Logs all block changes with size and hash |
| **conversation** | `ConversationAgent` | Processes conversation blocks via LLM, persists history |
| **pactown-monitor** | `PactownMonitor` | Polls Pactown health, writes state/log blocks, triggers autofix |

LLM access via `AgentLLMClient` — wraps `LLMClient` (LiteLLM) with Ollama fallback.

### 4. Sync Layer (`marksync.sync`)

Real-time synchronization via CRDT and delta patches:

- **CRDTDocument** (`sync/crdt.py`) — pycrdt-backed document with per-block Y.Text; `snapshot`/`rollback_to`, `garbage_collect`, `get_blocks_by_kind`, `append_block`
- **SyncServer** (`sync/engine.py`) — WebSocket hub, persists to disk, broadcasts; TLS, rate limiting, git auto-commit, Prometheus metrics, three-way merge
- **SyncClient** (`sync/engine.py`) — connects to server, pushes/pulls changes; TLS client
- **MultiProjectServer** (`sync/engine.py`) — routes by `?project=<name>` query param
- **BlockParser** (`sync/__init__.py`) — extracts `markpact:*` blocks from Markdown
- **SnapshotStore** (`sync/snapshots.py`) — persist/list/load/restore/prune CRDT snapshots

### 5. Contract & Intent Layer (`marksync.contract`, `marksync.intent`)

Generate complete Markpact contracts from natural language:

- **IntentParser** (`intent/parser.py`) — heuristic + LLM parsing of natural language → `ProcessIntent`
- **YAMLGenerator** (`intent/yaml_generator.py`) — `ProcessIntent` → pipeline + orchestration YAML
- **ContractGenerator** (`contract/generator.py`) — generates 10 contract blocks from intent
- **Templates** (`contract/templates.py`) — `RestAPITemplate`, `WebAppTemplate`, `CLITemplate`, `WorkerTemplate`, `GenericTemplate`
- **BlockTypes** (`contract/block_types.py`) — block ID constants, `EnvProfile`, `GeneratedContract`

### 6. Conversation Layer (`marksync.conversation`)

- **ConversationEngine** — appends messages to CRDT history, processes via LLM, supports multi-turn context

### 7. Learning Layer (`marksync.learning`)

Feedback loop for continuous improvement:

- **FeedbackCollector** — records approve/reject/comment events; `complete_run()` saves pattern on success
- **PatternLibrary** — stores/finds/scores patterns by keyword matching; `save_from_contract()`
- **PromptRefiner** — analyzes rejection history, generates refined prompts via LLM or heuristic

### 8. Auth Layer (`marksync.auth`)

- **Tokens** (`auth/tokens.py`) — `create_token`/`verify_token` with JWT (PyJWT) or HMAC fallback
- **Roles** (`auth/roles.py`) — `Role` enum (admin/editor/viewer), `has_permission`
- **Middleware** (`auth/middleware.py`) — `AuthMiddleware` (Starlette), `get_current_user`, `require_role` FastAPI dependency

### 9. Dashboard Layer (`marksync.dashboard`)

- **Dashboard app** (`dashboard/app.py`) — FastAPI app with SSE push; contract lifecycle UI; `GET /api/config`, `GET /api/pipeline/tasks`, `POST /api/pipeline/tasks/{id}/resolve`; `_broadcast_sse` for real-time updates

### 10. Sandbox Layer (`marksync.sandbox`)

Web-based testing UI:

- Browse/edit example README.md files
- View and edit individual code blocks
- Push changes to sync server
- Run pipeline demos, approve/reject human tasks
- Monitor server status

### 11. Plugin Layer (`marksync.plugins`)

Extensible export/import system with lazy loading and entry_points discovery:

- **Formats**: BPMN 2.0 (full collaboration/pools/lanes), XPDL, Petri Net, DMN, CMMN, EPC, UML Activity, BPEL
- **Integrations**: Kubernetes, GitLab CI, GitHub Actions, Airflow, Ansible, n8n, Terraform, Pactown
- **API Adapters**: OpenAPI 3.0, AsyncAPI, GraphQL, gRPC (.proto), JSON Schema
- **Channels**: SSE, WebSocket, MQTT, Redis Pub/Sub, AMQP, NATS, gRPC streaming, Slack, HTTP Webhook, CLI stdio

### 12. Transport Layer (`marksync.transport`)

Extensible transport backends for SyncServer: WebSocket (implemented), MQTT (planned), gRPC (planned).

### 13. Hardware Detection (`marksync.hardware_detect`)

Used by `marksync init` wizard:

- `detect_nvidia_gpu()` / `detect_amd_gpu()` — query nvidia-smi / rocm-smi
- `detect_ram()` — parse `free` or `/proc/meminfo`
- `is_ollama_installed()` / `is_ollama_running()` / `list_ollama_models()`
- `suggest_model(gpu_vram_gb, ram_gb)` — returns `(model_name, recommend_api_instead)`
- `detect(ollama_url)` — full system scan → `SystemInfo`

## Data Flow

1. **Agent edits a block** → generates diff-match-patch delta
2. **Delta sent to SyncServer** via WebSocket (`type: "patch"`)
3. **Server applies patch** to CRDT document, verifies SHA-256
4. **Server broadcasts** patch to all other connected clients
5. **Server persists** updated README.md to disk
6. **Other agents receive** patch, apply locally, trigger role-specific handler

## Delta Strategy

- If `len(patch) < 0.8 * len(full_content)` → send patch (saves bandwidth)
- Otherwise → send full block content (fallback)
- SHA-256 hash verification on every apply (NACK on mismatch)

## Configuration

System configuration priority (highest → lowest):
1. **Explicit function/CLI arguments**
2. **Environment variables** (`os.environ`)
3. **`.env` file** in project root
4. **Built-in defaults** in `settings.py`

Runtime changes via:
- **DSL commands** (`SET server_uri ws://...`)
- **REST API** (`PUT /api/v1/config/server_uri`)
- **Sandbox UI** (web browser)
