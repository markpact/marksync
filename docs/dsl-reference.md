# DSL Reference

The marksync DSL (Domain-Specific Language) controls agent orchestration, pipelines, routing, and system configuration.

## Usage

```bash
# Interactive shell
marksync shell

# Execute script file
marksync shell --script setup.msdsl

# Via REST API
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "AGENT editor-1 editor --auto-edit"}'

# Via WebSocket
ws://localhost:8080/ws/dsl
```

> **Note:** For agent definitions, prefer `agents.yml` with `marksync orchestrate` over manual DSL commands. The DSL is best for interactive use, scripting, and runtime changes.

## Commands

### AGENT — Create Agent

```
AGENT <name> <role> [--model MODEL] [--auto-edit] [--watch block1,block2]
```

| Arg | Description |
|-----|-------------|
| `name` | Unique agent name |
| `role` | `editor`, `reviewer`, `deployer`, `monitor` |
| `--model` | Ollama model (default: from `.env`) |
| `--auto-edit` | Auto-push LLM improvements (editor only) |
| `--watch` | Comma-separated block IDs to watch (default: all) |

```
AGENT editor-1 editor --model qwen2.5-coder:7b --auto-edit
AGENT reviewer-1 reviewer
AGENT monitor-1 monitor --watch markpact:file=app/main.py
```

### KILL — Stop Agent

```
KILL <name>
```

### LIST — List Resources

```
LIST [agents|pipelines|routes|config]
```

### PIPE — Define Pipeline

```
PIPE <name> <agent1> -> <agent2> -> <agent3>
```

Routes block updates through a chain of agents in order.

```
PIPE review-flow editor-1 -> reviewer-1
PIPE full-flow editor-1 -> reviewer-1 -> deployer-1
```

### ROUTE — Map Blocks to Agents

```
ROUTE <pattern> -> <agent>
```

```
ROUTE markpact:file=* -> editor-1
ROUTE markpact:deps -> reviewer-1
ROUTE markpact:run -> deployer-1
```

### SET — Configure

```
SET <key> <value>
```

```
SET server_uri ws://localhost:8765
SET ollama_url http://localhost:11434
SET ollama_model qwen2.5-coder:7b
SET auto_edit true
SET log_level DEBUG
```

### STATUS — System Status

```
STATUS              # full system status
STATUS <agent>      # single agent details
```

### SEND — Message Agent

```
SEND <agent> <message>
```

### DEPLOY — Trigger Build

```
DEPLOY [--force]
```

### SYNC — Synchronization

```
SYNC [push|pull|status]
```

### CONNECT / DISCONNECT

```
CONNECT [ws://host:port]
DISCONNECT
```

### LOAD / SAVE — Script Files & State

```
LOAD setup.msdsl           # execute script file
LOAD state.json --state    # restore persisted executor state
SAVE current-state.msdsl   # export current config as DSL script
SAVE state.json --state    # persist agents/pipelines/routes/config to JSON
```

### LOG — Command History

```
LOG [--tail N]
```

### HELP

```
HELP              # all commands
HELP agent        # specific command
```

## DSL v2 Commands

### CREATE — Generate Contract

```
CREATE <prompt> [--output DIR] [--no-llm] [--deploy] [--open-dashboard]
```

Generate a full Markpact contract from a natural language prompt.

```
CREATE "REST API for task management" --output ./my-service
CREATE "payment service with approval" --deploy
```

### DASHBOARD — Open Dashboard UI

```
DASHBOARD [--port N] [--host H]
```

### LEARN — Save Contract as Pattern

```
LEARN <contract_path> [--success true|false]
```

Save a completed contract to the pattern library for future reuse.

```
LEARN ./my-service --success true
LEARN ./failed-attempt --success false
```

### PATTERNS — List Saved Patterns

```
PATTERNS
```

### MACRO — Define Command Alias

```
MACRO <name> = <command template with $1 $2 ...>
```

Define a reusable command alias with positional argument substitution.

```
MACRO review-chain = PIPE $1 editor-1 -> reviewer-1 -> deployer-1
review-chain my-flow
```

## Brace Expansion

Brace expressions in agent names are expanded automatically:

```
AGENT coder-{1..3} editor --auto-edit
# expands to: AGENT coder-1 editor, AGENT coder-2 editor, AGENT coder-3 editor

AGENT {editor,reviewer}-1 {editor,reviewer}
# expands to: AGENT editor-1 editor, AGENT reviewer-1 reviewer
```

## Type Coercion

Values in `--options` are automatically coerced:

| Input | Type | Value |
|-------|------|-------|
| `true`, `yes`, `on` | `bool` | `True` |
| `false`, `no`, `off` | `bool` | `False` |
| `42` | `int` | `42` |
| `3.14` | `float` | `3.14` |
| `hello` | `str` | `"hello"` |

## DSL vs agents.yml

| Feature | DSL (`.msdsl`) | `agents.yml` |
|---------|----------------|--------------|
| Format | Imperative commands | Declarative YAML |
| Used by | `marksync shell` | `marksync orchestrate` |
| Agents | ✓ | ✓ |
| Pipelines | ✓ | ✓ |
| Routes | ✓ | ✓ |
| SET/SEND/DEPLOY/SYNC | ✓ | ✗ |
| CREATE/LEARN/PATTERNS | ✓ | ✗ |
| MACRO/brace expansion | ✓ | ✗ |
| Best for | Interactive, runtime changes | Static config, Docker |

For most use cases, `agents.yml` + `marksync orchestrate` is simpler.
The DSL shell is for interactive exploration, runtime changes, and contract generation.
