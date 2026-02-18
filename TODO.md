# TODO — marksync

## High Priority

- [ ] **MQTT transport** — implement `marksync.transport.mqtt` for IoT/edge agent communication
- [ ] **gRPC transport** — high-performance binary transport for large-scale deployments
- [ ] **Agent persistence** — save/restore agent state across restarts
- [ ] **Pipeline execution engine** — actually route block updates through pipeline stages
- [ ] **Authentication** — token-based auth for REST/WS API and sync server
- [ ] **TLS/WSS support** — encrypted WebSocket connections

## Medium Priority

- [ ] **DSL tab completion** — readline/prompt_toolkit integration in shell
- [ ] **DSL command history** — persistent history file (~/.marksync_history)
- [ ] **Agent health monitoring** — automatic restart on failure, health check endpoints
- [ ] **Block conflict resolution** — interactive merge UI for conflicting edits
- [ ] **Metrics & telemetry** — Prometheus/OpenTelemetry integration
- [ ] **Web dashboard** — React-based UI for real-time agent monitoring
- [ ] **Rate limiting** — prevent agents from flooding the sync server
- [ ] **Batch operations** — DSL support for `AGENT coder-{1..5} editor` expansion

## Low Priority

- [ ] **Plugin system** — loadable agent roles from external packages
- [ ] **Multi-project support** — single server managing multiple README.md files
- [ ] **Git integration** — automatic commit on deploy, branch-per-agent
- [ ] **Ollama model auto-pull** — detect missing models and pull automatically
- [ ] **CRDT garbage collection** — compact document history periodically
- [ ] **DSL macros** — user-defined command aliases and templates
- [ ] **Webhook notifications** — notify external services on agent events
- [ ] **Docker Swarm / K8s** — orchestration templates for production deployment

## Completed

- [x] Core sync engine (SyncServer, SyncClient)
- [x] CRDT document with pycrdt (Yjs-compatible)
- [x] Block parser for markpact:* code blocks
- [x] Agent worker with 4 roles (editor, reviewer, deployer, monitor)
- [x] Ollama LLM integration
- [x] CLI with Click (server, agent, push, blocks)
- [x] Docker Compose multi-container setup
- [x] DSL parser and executor
- [x] DSL interactive shell (REPL)
- [x] REST/WS API for remote orchestration
- [x] Delta sync with diff-match-patch + SHA-256 verification
