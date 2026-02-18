# marksync

Multi-agent collaborative editing and deployment of [Markpact](https://github.com/wronai/markpact) projects via CRDT delta sync.

```
pip install marksync[all]
```

## What it does

Multiple AI agents work simultaneously on a single Markpact `README.md` — editing code, reviewing quality, deploying changes — all synchronized in real-time through delta patches (only changed code blocks are transmitted, not the entire file).

A built-in **DSL** (Domain-Specific Language) lets you orchestrate agents, define pipelines, and control the entire architecture from an interactive shell or via REST/WebSocket API.

```
┌─────────────────────────────────────────────────────────────┐
│                    marksync Runtime                         │
│                                                             │
│  ┌────────────┐   ┌──────────────────────────────────────┐  │
│  │ DSL Shell  │──►│         DSL Executor                 │  │
│  │ (CLI REPL) │   │  agents · pipelines · routes · config│  │
│  └────────────┘   └──────────┬───────────────────────────┘  │
│  ┌────────────┐              │ spawns / controls            │
│  │ REST API   │──►           ▼                              │
│  │ port 8080  │   ┌──────────────────────────────────────┐  │
│  └────────────┘   │         Agent Workers                │  │
│  ┌────────────┐   │  editor · reviewer · deployer · mon  │  │
│  │  WS API    │──►└──────────┬───────────────────────────┘  │
│  │  /ws/dsl   │              │                              │
│  └────────────┘              ▼                              │
│                   ┌──────────────────────────────────────┐  │
│                   │     SyncServer (WebSocket:8765)      │  │
│                   │  CRDT doc · delta patches · persist  │  │
│                   └──────────────┬───────────────────────┘  │
│                                  ▼                          │
│                           README.md (disk)                  │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

**Ollama** running locally on your host (not inside Docker):

```bash
# Install ollama: https://ollama.ai
ollama pull qwen2.5-coder:7b
ollama serve  # keep running
```

## Quick Start — Docker Compose

```bash
git clone https://github.com/wronai/marksync.git
cd marksync
docker compose up --build
```

This starts 5 containers:

| Container | Role | What it does |
|-----------|------|-------------|
| `sync-server` | Hub | WebSocket server, persists README.md, broadcasts changes |
| `agent-editor` | Editor | Receives code blocks, sends to Ollama for improvements |
| `agent-reviewer` | Reviewer | Analyzes code quality via LLM, logs findings |
| `agent-deployer` | Deployer | Watches for changes, triggers `markpact` builds |
| `agent-monitor` | Monitor | Logs every block change with size and hash |

Then push changes from your host:

```bash
# Install marksync locally
pip install -e .

# Push your README changes to the running server
marksync push README.md --server-uri ws://localhost:8765

# See what blocks are in a README
marksync blocks demo-project.md
```

## Quick Start — Without Docker

```bash
pip install marksync[all]

# Terminal 1: Start sync server
marksync server README.md --port 8765

# Terminal 2: Start a monitor agent
marksync agent --role monitor --name watcher-1 \
  --server-uri ws://localhost:8765 \
  --ollama-url http://localhost:11434

# Terminal 3: Push changes
marksync push README.md --server-uri ws://localhost:8765
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

### DSL Script Files (.msdsl)

```bash
marksync shell --script setup.msdsl
```

```bash
# setup.msdsl
SET server_uri ws://localhost:8765
SET ollama_model qwen2.5-coder:7b
AGENT coder editor --auto-edit
AGENT reviewer-1 reviewer
PIPE review-flow coder -> reviewer-1
ROUTE markpact:run -> deployer-1
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
marksync server README.md [--host 0.0.0.0] [--port 8765]
marksync agent --role {editor|reviewer|deployer|monitor} --name NAME
               [--server-uri ws://...] [--ollama-url http://...]
               [--model MODEL] [--auto-edit]
marksync push README.md [--server-uri ws://...]
marksync blocks README.md
marksync shell [--script FILE] [--server-uri ws://...] [--ollama-url http://...]
marksync api [--host 0.0.0.0] [--port 8080] [--server-uri ws://...] [--ollama-url http://...]
```

## Agent Roles

### Editor (`--role editor`)

Receives block updates, sends code to Ollama for improvement (error handling, type hints, docstrings). Use `--auto-edit` to automatically push improvements back to server.

### Reviewer (`--role reviewer`)

Analyzes every changed block for bugs, security issues, and best practices. Results are logged — does not modify code.

### Deployer (`--role deployer`)

Watches for changes to `markpact:run` and `markpact:deps` blocks. Triggers `markpact README.md --run` to rebuild and redeploy the application.

### Monitor (`--role monitor`)

Logs every block change with block ID, content size, and SHA-256 hash. Useful for audit trails and debugging.

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
print(executor.snapshot())
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
├── pyproject.toml           # Package config (pip install .)
├── Dockerfile               # Single image for server + agents
├── docker-compose.yml       # Full ecosystem (5 containers)
├── TODO.md                  # Project roadmap
├── CHANGELOG.md             # Version history
├── docs/
│   ├── architecture.md      # System design & data flow
│   ├── dsl-reference.md     # DSL command reference
│   └── api.md               # REST & WebSocket API docs
├── marksync/
│   ├── __init__.py          # Package exports
│   ├── cli.py               # Click CLI (server, agent, push, blocks, shell, api)
│   ├── dsl/
│   │   ├── __init__.py      # DSL public API
│   │   ├── parser.py        # DSLParser, DSLCommand, CommandType
│   │   ├── executor.py      # DSLExecutor, AgentHandle, Pipeline, Route
│   │   ├── shell.py         # Interactive REPL (DSLShell)
│   │   └── api.py           # FastAPI REST + WebSocket endpoints
│   ├── sync/
│   │   ├── __init__.py      # BlockParser, MarkpactBlock
│   │   ├── crdt.py          # CRDTDocument (pycrdt/Yjs)
│   │   └── engine.py        # SyncServer, SyncClient
│   ├── agents/
│   │   ├── __init__.py      # AgentWorker, AgentConfig, OllamaClient
│   │   └── base.py          # Re-exports
│   └── transport/
│       └── __init__.py      # MQTT/gRPC extension point
├── tests/
│   ├── test_marksync.py     # Import & smoke tests
│   └── test_dsl.py          # DSL parser & executor tests
└── demo-project.md          # Example Markpact README
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MARKSYNC_SERVER` | `ws://sync-server:8765` | Sync server URI |
| `OLLAMA_URL` | `http://host.docker.internal:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen2.5-coder:7b` | LLM model for agents |

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
- [Changelog](CHANGELOG.md) — version history
- [TODO](TODO.md) — roadmap and planned features

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
