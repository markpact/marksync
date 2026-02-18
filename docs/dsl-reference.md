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

### LOAD / SAVE — Script Files

```
LOAD setup.msdsl           # execute script
SAVE current-state.msdsl   # export current config
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
| Best for | Interactive, runtime changes | Static config, Docker |

For most use cases, `agents.yml` + `marksync orchestrate` is simpler.
The DSL shell is for interactive exploration and runtime changes.
