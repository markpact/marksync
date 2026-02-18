# marksync REST & WebSocket API

The DSL API server exposes the full marksync DSL command set over HTTP REST and WebSocket, enabling external tools, dashboards, and CI/CD integrations.

## Starting the API Server

```bash
marksync api --host 0.0.0.0 --port 8080
```

Interactive docs are available at `http://localhost:8080/docs` (Swagger UI).

## REST Endpoints

Base URL: `http://localhost:8080/api/v1`

### Health Check

```
GET /api/v1/health
```

**Response:**
```json
{"ok": true, "service": "marksync", "ts": 1708275600.0}
```

### Execute Command

```
POST /api/v1/execute
Content-Type: application/json

{"command": "AGENT coder editor --auto-edit"}
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "ok": true,
    "agent": {"name": "coder", "role": "editor", "status": "registered", ...}
  },
  "ts": 1708275600.0
}
```

### Execute Script

```
POST /api/v1/script
Content-Type: application/json

{
  "script": "SET ollama_model llama3:8b\nAGENT coder editor\nAGENT watcher monitor"
}
```

### System Status

```
GET /api/v1/status
```

### Agents

```
GET    /api/v1/agents          # list all agents
GET    /api/v1/agents/{name}   # agent details
DELETE /api/v1/agents/{name}   # kill agent
```

### Pipelines & Routes

```
GET /api/v1/pipelines
GET /api/v1/routes
```

### Configuration

```
GET /api/v1/config              # get all config
PUT /api/v1/config/{key}        # set config value
    Body: {"value": "new-value"}
```

### Full Snapshot

```
GET /api/v1/snapshot
```

Returns the complete runtime state: agents, pipelines, routes, config.

## WebSocket API

```
WS ws://localhost:8080/ws/dsl
```

### Protocol

The WebSocket endpoint provides bidirectional DSL command streaming.

**Client → Server (send command):**
```json
{"command": "AGENT coder editor --auto-edit"}
```

Or plain text:
```
AGENT coder editor --auto-edit
```

**Server → Client (command result):**
```json
{
  "type": "result",
  "command": "AGENT coder editor --auto-edit",
  "data": {"ok": true, "agent": {...}},
  "ts": 1708275600.0
}
```

**Server → Client (event broadcast):**
```json
{
  "type": "event",
  "command": "KILL coder",
  "data": {"ok": true, "killed": "coder"},
  "ts": 1708275600.0
}
```

**Initial snapshot** is sent on connect:
```json
{
  "type": "snapshot",
  "data": {"agents": {}, "pipelines": {}, "routes": [], "config": {...}},
  "ts": 1708275600.0
}
```

### WebSocket Example (Python)

```python
import asyncio
import json
import websockets

async def main():
    async with websockets.connect("ws://localhost:8080/ws/dsl") as ws:
        # Receive initial snapshot
        snapshot = json.loads(await ws.recv())
        print(f"Connected: {snapshot['data']['config']}")

        # Spawn an agent
        await ws.send(json.dumps({"command": "AGENT coder editor --auto-edit"}))
        result = json.loads(await ws.recv())
        print(f"Agent: {result['data']}")

        # List agents
        await ws.send(json.dumps({"command": "LIST agents"}))
        result = json.loads(await ws.recv())
        print(f"Agents: {result['data']}")

asyncio.run(main())
```

### WebSocket Example (JavaScript)

```javascript
const ws = new WebSocket("ws://localhost:8080/ws/dsl");

ws.onopen = () => {
  ws.send(JSON.stringify({ command: "AGENT coder editor --auto-edit" }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg.type, msg.data);
};
```

## CORS

The API server allows all origins by default (`*`). Configure via middleware settings in production.

## Error Handling

All endpoints return consistent error responses:

```json
{
  "ok": false,
  "data": {"ok": false, "error": "Agent 'coder' not found"},
  "error": null,
  "ts": 1708275600.0
}
```

HTTP status codes:
- `200` — success
- `404` — resource not found
- `422` — validation error
- `500` — internal error
