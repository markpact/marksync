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
┌──────────────────────────────────────────────────────────┐
│                    Pipeline Run                          │
│                                                          │
│  Step 1 (LLM)  →  Step 2 (HUMAN)  →  Step 3 (SCRIPT)     │
│  auto-process      wait for input      deterministic     │
│  via Ollama        via API endpoint    run function      │
└──────────────────────────────────────────────────────────┘
```

| Actor Type | Execution | Examples |
|------------|-----------|----------|
| **LLM** | Async, automatic via Ollama | Code editing, review, summarization |
| **SCRIPT** | Sync, deterministic callable | Lint, validate, format, deploy |
| **HUMAN** | Async, blocks until API response | Approve changes, provide input, authorize payment |

**Human-in-the-loop** works via `HumanTask` objects:
1. Pipeline reaches a HUMAN step → creates a `HumanTask` with prompt + context
2. Pipeline **blocks** (async `Future`) until resolved
3. Human resolves via REST API: `POST /api/pipeline/tasks/{id}` with `approve`/`reject`/`provide_input`
4. Pipeline **unblocks** and continues (or fails if rejected)

Channels: `web` (sandbox UI), `email`, `chat`, `webhook` — extensible.

Example pipeline definition in `agents.yml`:

```yaml
pipelines:
  review-approve-deploy:
    steps:
      - name: llm-edit
        actor: llm
        config: {role: editor}
      - name: human-review
        actor: human
        config: {prompt: "Approve changes?", task_type: approval}
      - name: lint
        actor: script
        config: {script: lint}
      - name: deploy
        actor: script
        config: {script: deploy}
```

Demo scenarios available in sandbox: code-review, account-creation, payment.

### 2. DSL Layer (`marksync.dsl`)

Imperative command interface for interactive/runtime control:

- **Parser** (`dsl/parser.py`) — tokenizes text commands into `DSLCommand` objects
- **Executor** (`dsl/executor.py`) — executes commands, manages agent lifecycle
- **Shell** (`dsl/shell.py`) — interactive REPL with rich terminal output
- **API** (`dsl/api.py`) — REST/WebSocket endpoints

### 3. Agent Layer (`marksync.agents`)

AI-powered workers that connect to the SyncServer and process block updates:

| Role | Behavior |
|------|----------|
| **Editor** | Sends code to Ollama LLM for improvement, pushes edits back |
| **Reviewer** | Analyzes code quality, logs findings (read-only) |
| **Deployer** | Watches for `markpact:run`/`markpact:deps` changes, triggers builds |
| **Monitor** | Logs all block changes with size and hash |

### 4. Sync Layer (`marksync.sync`)

Real-time synchronization via CRDT and delta patches:

- **CRDTDocument** (`sync/crdt.py`) — pycrdt-backed document with per-block Y.Text
- **SyncServer** (`sync/engine.py`) — WebSocket hub, persists to disk, broadcasts
- **SyncClient** (`sync/engine.py`) — connects to server, pushes/pulls changes
- **BlockParser** (`sync/__init__.py`) — extracts `markpact:*` blocks from Markdown

### 5. Sandbox Layer (`marksync.sandbox`)

Web-based testing UI:

- Browse/edit example README.md files
- View and edit individual code blocks
- Push changes to sync server
- View orchestration plans
- Monitor server status

### 6. Transport Layer (`marksync.transport`)

Extensible transport backends (currently WebSocket, planned: MQTT, gRPC).

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
