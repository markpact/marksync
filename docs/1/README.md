# Example 1 — Task Manager API

A collaborative REST API for task management, built and maintained by marksync agents.  
Source: [`examples/1/README.md`](../../examples/1/README.md)

## Overview

This example demonstrates the core marksync workflow:

1. **A Markpact README** defines the entire application (models, API server, run command)
2. **marksync agents** collaboratively edit, review, and deploy the code blocks
3. **markpact** extracts the code and runs the application

### Architecture

```
examples/1/README.md
  ├── markpact:deps    → fastapi, uvicorn, pydantic
  ├── markpact:file    → app/models.py   (Task model)
  ├── markpact:file    → app/main.py     (FastAPI server)
  └── markpact:run     → uvicorn app.main:app --port 8088
```

## Quick Start

### 1. Inspect blocks

```bash
marksync blocks examples/1/README.md
```

Expected output:

```
┌─────────────────────────────────────────────────────────┐
│ Blocks in examples/1/README.md                          │
├──────────────────┬──────┬────────┬───────┬──────────────┤
│ Block ID         │ Kind │ Lang   │ Lines │ SHA-256      │
├──────────────────┼──────┼────────┼───────┼──────────────┤
│ markpact:deps    │ deps │ text   │     3 │ a1b2c3d4...  │
│ markpact:file    │ file │ python │    21 │ e5f6a7b8...  │
│ markpact:file    │ file │ python │    71 │ c9d0e1f2...  │
│ markpact:run     │ run  │ bash   │     1 │ 1234abcd...  │
└──────────────────┴──────┴────────┴───────┴──────────────┘
  Total: 4 blocks, 2847 chars
```

### 2. Start the sync server with this example

```bash
# Terminal 1 — sync server
marksync server examples/1/README.md
```

### 3. Start agents

```bash
# Terminal 2 — editor agent (improves code via LLM)
marksync agent --role editor --name editor-1 \
  --server-uri ws://localhost:8765 \
  --ollama-url http://localhost:11434 \
  --model qwen2.5-coder:7b

# Terminal 3 — monitor agent (logs all changes)
marksync agent --role monitor --name monitor-1 \
  --server-uri ws://localhost:8765
```

### 4. Use DSL shell to orchestrate

```bash
marksync shell
```

```
marksync> AGENT editor-1 editor --model qwen2.5-coder:7b --auto-edit
marksync> AGENT reviewer-1 reviewer
marksync> AGENT monitor-1 monitor
marksync> PIPE review-flow editor-1 -> reviewer-1
marksync> LIST agents
marksync> STATUS
```

### 5. Use REST API

```bash
# Terminal — start API server
marksync api --port 8080

# From another terminal
curl http://localhost:8080/api/v1/agents
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "AGENT editor-1 editor --auto-edit"}'
```

### 6. Push local changes

After editing `examples/1/README.md` locally:

```bash
marksync push examples/1/README.md --server-uri ws://localhost:8765
```

### 7. Deploy with markpact

```bash
cd examples/1
markpact README.md --run
```

This extracts all `markpact:file` blocks to disk and executes `markpact:run`:

```
app/
├── models.py    ← extracted from README.md
└── main.py      ← extracted from README.md
```

The Task Manager API starts on `http://localhost:8088`.

## API Endpoints (Task Manager)

Once deployed, the Task Manager exposes:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Service info |
| GET | `/tasks` | List all tasks (optional `?status=todo`) |
| POST | `/tasks` | Create a task |
| GET | `/tasks/{id}` | Get task by ID |
| PATCH | `/tasks/{id}` | Update task fields |
| DELETE | `/tasks/{id}` | Delete task |
| GET | `/health` | Health check |

### Example requests

```bash
# Create a task
curl -X POST http://localhost:8088/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Implement auth", "description": "Add JWT authentication"}'

# List tasks
curl http://localhost:8088/tasks

# Update status
curl -X PATCH http://localhost:8088/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'

# Filter by status
curl http://localhost:8088/tasks?status=todo
```

## Docker Compose

This example is used as the default seed project in `docker-compose.yml`.  
The `init-project` service copies `examples/1/README.md` into the shared volume:

```bash
docker compose up --build
```

All 4 agents + sync server start automatically and collaborate on this project.

## Configuration via .env

All ports and hosts are configurable through the root `.env` file:

```env
MARKSYNC_PORT=8765        # sync server port
MARKSYNC_API_PORT=8080    # DSL API port
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
MARKPACT_PORT=8088        # Task Manager API port
```

## Code Blocks Explained

### `markpact:deps` — Dependencies

Declares Python packages needed by the application. Agents can suggest adding or upgrading packages.

### `markpact:file path=app/models.py` — Data Models

Defines the `Task` Pydantic model with fields: `id`, `title`, `description`, `status`, `created_at`. The editor agent may improve this by adding validators or additional fields.

### `markpact:file path=app/main.py` — API Server

Full FastAPI application with CRUD endpoints. The editor agent may:
- Add error handling
- Improve type hints
- Add pagination
- Suggest security improvements

The reviewer agent analyzes this block for:
- Code quality issues
- Security vulnerabilities
- Best practice violations

### `markpact:run` — Run Command

The command to start the application. Uses `${MARKPACT_PORT:-8088}` for port configuration via environment variable.
