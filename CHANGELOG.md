## [0.2.1] - 2026-02-18

### Summary

feat(docs): configuration management system

### Docs

- docs: update README

### Test

- update tests/test_dsl.py

### Build

- update pyproject.toml

### Other

- update marksync/__init__.py
- update marksync/dsl/parser.py
- update project.functions.toon
- scripts: update project.sh
- update project.toon-schema.json


## [0.1.3] - 2026-02-18

### Summary

feat(docs): CLI interface improvements

### Docs

- docs: update TODO.md
- docs: update api.md
- docs: update architecture.md

### Other

- update .gitignore
- update marksync/cli.py
- update marksync/dsl/api.py
- update marksync/dsl/shell.py


# Changelog

All notable changes to **marksync** are documented here.

## [0.2.0] - 2026-02-18

### Added

- **DSL Layer** (`marksync.dsl`) — domain-specific language for agent orchestration
  - `DSLParser` — tokenizer/parser for text commands and `.msdsl` script files
  - `DSLExecutor` — runtime engine managing agents, pipelines, routes, config
  - `DSLShell` — interactive REPL with rich terminal output
  - REST/WS API (`FastAPI`) for remote control via HTTP and WebSocket
- **CLI commands**: `marksync shell`, `marksync api`
- **Documentation**: `docs/architecture.md`, `docs/dsl-reference.md`, `docs/api.md`
- **TODO.md** — project roadmap and task tracking
- DSL commands: AGENT, KILL, LIST, PIPE, SEND, SET, STATUS, DEPLOY, SYNC, ROUTE, LOG, CONNECT, DISCONNECT, LOAD, SAVE, HELP
- Script file support (`.msdsl`) with LOAD/SAVE commands
- Event system in DSLExecutor for reactive integrations
- `pytest-asyncio` added to dev dependencies

### Fixed

- `pyproject.toml`: author #2 must be inline table (was plain string — broke `hatchling` build)
- `pyproject.toml`: wheel packages path `src/marksync` → `marksync`
- `Dockerfile`: `COPY src/` → `COPY marksync/` (matched actual layout)

---

## [0.1.1] - 2026-02-18

### Added

- Core sync engine: `SyncServer`, `SyncClient` (WebSocket, CRDT, delta patches)
- CRDT document with `pycrdt` (Yjs-compatible, per-block Y.Text)
- Block parser for `markpact:*` fenced code blocks
- Agent worker with 4 roles: editor, reviewer, deployer, monitor
- Ollama LLM integration (`OllamaClient`)
- CLI: `marksync server`, `marksync agent`, `marksync push`, `marksync blocks`
- Docker Compose multi-container setup (5 services)
- diff-match-patch delta sync with SHA-256 verification

---

## [0.1.0] - 2026-02-18

- Initial project scaffold
