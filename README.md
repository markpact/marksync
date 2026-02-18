# marksync

Multi-agent collaborative editing and deployment of [Markpact](https://github.com/wronai/markpact) projects via CRDT delta sync.

```
pip install marksync[all]
```

## What it does

Multiple AI agents work simultaneously on a single Markpact `README.md` — editing code, reviewing quality, deploying changes — all synchronized in real-time through delta patches (only changed code blocks are transmitted, not the entire file).

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ sync-server  │◄───►│ agent-editor │     │ agent-deploy │
│ (WebSocket)  │◄───►│ (LLM edits)  │     │ (markpact)   │
│ port 8765    │◄───►│              │     │              │
└──────┬───────┘     └──────────────┘     └──────────────┘
       │              ┌───────────────┐     ┌──────────────┐
       ├─────────────►│agent-reviewer │     │ agent-monitor│
       │              │ (code review) │     │ (log changes)│
       │              └───────────────┘     └──────────────┘
       │
  /project/README.md  ← single source of truth
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
marksync blocks examples/demo-project.md
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

## CLI Reference

```
marksync server README.md [--host 0.0.0.0] [--port 8765]
marksync agent --role {editor|reviewer|deployer|monitor} --name NAME
               [--server-uri ws://...] [--ollama-url http://...]
               [--model MODEL] [--auto-edit]
marksync push README.md [--server-uri ws://...]
marksync blocks README.md
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
├── src/marksync/
│   ├── __init__.py          # Package exports
│   ├── cli.py               # Click CLI (marksync command)
│   ├── sync/
│   │   ├── __init__.py      # BlockParser, MarkpactBlock
│   │   ├── crdt.py          # CRDTDocument (pycrdt/Yjs)
│   │   └── engine.py        # SyncServer, SyncClient
│   ├── agents/
│   │   ├── __init__.py      # AgentWorker, AgentConfig, OllamaClient
│   │   └── base.py          # Re-exports
│   └── transport/
│       └── __init__.py      # MQTT extension point
└── examples/
    └── demo-project.md      # Example Markpact README
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

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
