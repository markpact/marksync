# marksync Architecture

## Overview

marksync is a multi-agent collaborative editing system for [Markpact](https://github.com/wronai/markpact) projects. It uses CRDT-based delta synchronization to allow multiple AI agents to concurrently edit a single `README.md` file without conflicts.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      marksync Runtime                           │
│                                                                 │
│  ┌──────────────┐    ┌─────────────────────────────────────┐    │
│  │  DSL Shell   │───►│         DSL Executor                │    │
│  │  (CLI REPL)  │    │  • Agent lifecycle management       │    │
│  └──────────────┘    │  • Pipeline orchestration           │    │
│                      │  • Route configuration              │    │
│  ┌──────────────┐    │  • Config management                │    │
│  │  REST API    │───►│                                     │    │
│  │  (FastAPI)   │    └──────────┬──────────────────────────┘    │
│  │  port 8080   │               │                               │
│  └──────────────┘               │ spawns / controls             │
│                                 ▼                               │
│  ┌──────────────┐    ┌──────────────────────────────────┐       │
│  │  WS API      │───►│         Agent Workers            │       │
│  │  /ws/dsl     │    │  ┌────────┐ ┌────────┐           │       │
│  └──────────────┘    │  │ Editor │ │Reviewer│  ...      │       │
│                      │  └───┬────┘ └───┬────┘           │       │
│                      └──────┼──────────┼────────────────┘       │
│                             │          │                        │
│                             ▼          ▼                        │
│                      ┌──────────────────────────────────┐       │
│                      │        SyncServer (WS)           │       │
│                      │  • CRDT document (pycrdt/Yjs)    │       │
│                      │  • Block-level delta patches     │       │
│                      │  • Manifest-based sync           │       │
│                      │  port 8765                       │       │
│                      └──────────────┬───────────────────┘       │
│                                     │                           │
│                                     ▼                           │
│                              README.md (disk)                   │
└─────────────────────────────────────────────────────────────────┘
```

## Layers

### 1. DSL Layer (`marksync.dsl`)

The DSL (Domain-Specific Language) provides a unified interface for controlling the entire system:

- **Parser** (`dsl/parser.py`) — tokenizes text commands into `DSLCommand` objects
- **Executor** (`dsl/executor.py`) — executes commands, manages agent lifecycle, pipelines, routes
- **Shell** (`dsl/shell.py`) — interactive REPL with rich terminal output
- **API** (`dsl/api.py`) — REST/WebSocket endpoints exposing the executor to external tools

### 2. Agent Layer (`marksync.agents`)

AI-powered workers that connect to the SyncServer and process block updates:

| Role | Behavior |
|------|----------|
| **Editor** | Sends code to Ollama LLM for improvement, pushes edits back |
| **Reviewer** | Analyzes code quality, logs findings (read-only) |
| **Deployer** | Watches for `markpact:run`/`markpact:deps` changes, triggers builds |
| **Monitor** | Logs all block changes with size and hash |

### 3. Sync Layer (`marksync.sync`)

Real-time synchronization via CRDT and delta patches:

- **CRDTDocument** (`sync/crdt.py`) — pycrdt-backed document with per-block Y.Text
- **SyncServer** (`sync/engine.py`) — WebSocket hub, persists to disk, broadcasts
- **SyncClient** (`sync/engine.py`) — connects to server, pushes/pulls changes
- **BlockParser** (`sync/__init__.py`) — extracts `markpact:*` blocks from Markdown

### 4. Transport Layer (`marksync.transport`)

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

System configuration can be set via:
1. **Environment variables** (`MARKSYNC_SERVER`, `OLLAMA_URL`, `OLLAMA_MODEL`)
2. **CLI flags** (`--server-uri`, `--ollama-url`, `--model`)
3. **DSL commands** (`SET server_uri ws://...`)
4. **REST API** (`PUT /api/v1/config/server_uri`)
5. **Script files** (`.msdsl` format, loaded with `LOAD` command)
