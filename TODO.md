# TODO — marksync

## High Priority

- [x] **Pipeline execution engine** — `PipelineEngine.attach_to_sync_server()` + `add_block_route(pattern, pipeline)` routes block changes to pipelines
- [x] **Authentication** — token-based auth for REST/WS API and sync server (`marksync/auth/`)
- [x] **TLS/WSS support** — `SyncServer(ssl_certfile, ssl_keyfile)`, `SyncClient(ssl_verify, ssl_ca_cert)`, `marksync server --ssl-cert --ssl-key`
- [ ] **MQTT transport** — implement `marksync.transport.mqtt` for IoT/edge agent communication
- [ ] **gRPC transport** — high-performance binary transport for large-scale deployments

## Medium Priority

- [x] **Agent persistence** — save/restore agent state across restarts (`DSLExecutor.save_state/restore_state`)
- [x] **DSL tab completion** — readline tab completion in shell (`dsl/shell.py`)
- [x] **DSL command history** — persistent history file `~/.marksync_history`
- [x] **Agent health monitoring** — PactownMonitor.watch() loop, Plugin.health_check(), auto-fix pipeline trigger
- [x] **Block conflict resolution** — `_three_way_merge()` + `conflict`/`merge` WebSocket message types in `SyncServer`
- [x] **Metrics & telemetry** — Prometheus `/metrics` endpoint in dashboard + `SyncServer.metrics()`
- [x] **Rate limiting** — sliding-window rate limiter per client in SyncServer
- [x] **Batch operations** — brace expansion `AGENT coder-{1..5} editor` in `dsl/parser.py`

## Low Priority

- [x] **Plugin system** — `PluginRegistry._discover_entry_points()` loads external plugins via `marksync.plugins` entry_points group
- [x] **Multi-project support** — `MultiProjectServer` routes by `?project=<name>` query param
- [x] **Git integration** — `SyncServer(git_auto_commit=True)` auto-commits on save
- [x] **Ollama model auto-pull** — `OllamaClient._ensure_model()` pulls missing models automatically
- [x] **CRDT garbage collection** — `CRDTDocument.garbage_collect()` compacts logs + removes empty blocks
- [x] **DSL macros** — `MACRO NAME = template $1 $2` with argument substitution
- [x] **Webhook notifications** — `DSLExecutor.add_webhook(url, events)` fires on agent events
- [x] **Docker Swarm / K8s** — `deploy/docker-compose.swarm.yml` + `deploy/k8s/` (kustomize: namespace, configmap, PVC, sync-server, dashboard, orchestrator, ingress)

## Completed

- [x] Core sync engine (SyncServer, SyncClient)
- [x] CRDT document with pycrdt (Yjs-compatible)
- [x] Block parser for markpact:* code blocks
- [x] Agent worker with 4 roles (editor, reviewer, deployer, monitor)
- [x] Ollama LLM integration
- [x] CLI with Click (server, agent, push, blocks, shell, api, orchestrate, sandbox)
- [x] Docker Compose setup (simplified: 4 services with orchestrator)
- [x] DSL parser and executor
- [x] DSL interactive shell (REPL)
- [x] REST/WS API for remote orchestration
- [x] Delta sync with diff-match-patch + SHA-256 verification
- [x] Centralized `.env` configuration (`marksync.settings`)
- [x] `agents.yml` — declarative agent definitions (single source of truth)
- [x] Orchestrator — reads agents.yml, spawns all agents in 1 process
- [x] Web sandbox — browser-based UI for editing examples and testing
- [x] 3 example projects (Task Manager API, Chat WebSocket, Data Pipeline CLI)
- [x] 96 tests (DSL, examples, orchestrator, settings)
- [x] Full documentation (architecture, DSL reference, API, example guides)
