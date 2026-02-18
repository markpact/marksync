## [0.2.10] - 2026-02-18

### Summary

feat(docs): deep code analysis engine with 5 supporting modules

### Docs

- docs: update comparison.md

### Other

- update project.functions.toon
- update project.toon


## [0.2.9] - 2026-02-18

### Summary

feat(docs): deep code analysis engine with 6 supporting modules

### Docs

- docs: update pipelines.md

### Build

- update pyproject.toml

### Other

- update marksync/sandbox/app.py


## [0.2.8] - 2026-02-18

### Summary

feat(marksync): core module improvements

### Other

- update marksync/sandbox/html.py


## [0.2.7] - 2026-02-18

### Summary

feat(tests): configuration management system

### Docs

- docs: update architecture.md

### Test

- update tests/test_orchestrator.py
- update tests/test_pipeline_scenarios.py

### Other

- config: update agents.yml
- update marksync/pipeline/api.py
- update marksync/sandbox/html.py


## [0.2.6] - 2026-02-18

### Summary

chore(config): code relationship mapping with 2 supporting modules

### Build

- update pyproject.toml


## [0.2.5] - 2026-02-18

### Summary

chore(config): code relationship mapping with 2 supporting modules

### Build

- update pyproject.toml


## [0.2.4] - 2026-02-18

### Summary

feat(docs): CLI interface improvements

### Docs

- docs: update README
- docs: update TODO.md
- docs: update architecture.md
- docs: update dsl-reference.md

### Test

- update tests/test_orchestrator.py
- update tests/test_pipeline.py

### Build

- update pyproject.toml

### Other

- config: update agents.yml
- update examples/1/orchestrate.msdsl
- update examples/2/orchestrate.msdsl
- update examples/3/orchestrate.msdsl
- update marksync/cli.py
- update marksync/pipeline/__init__.py
- update marksync/pipeline/api.py
- update marksync/pipeline/engine.py
- update marksync/sandbox/__init__.py
- update marksync/sandbox/app.py
- ... and 2 more


## [0.2.3] - 2026-02-18

### Summary

feat(examples): CLI interface improvements

### Docs

- docs: update README

### Test

- update tests/test_orchestrator.py

### Build

- update pyproject.toml

### Other

- config: update agents.yml
- config: update agents.yml
- update examples/1/orchestrate.msdsl
- config: update agents.yml
- update examples/2/orchestrate.msdsl
- config: update agents.yml
- update examples/3/orchestrate.msdsl
- update marksync/__init__.py
- update marksync/cli.py
- update marksync/orchestrator.py
- ... and 2 more


## [0.2.2] - 2026-02-18

### Summary

feat(docs): CLI interface improvements

### Docs

- docs: update README
- docs: update README
- docs: update README

### Test

- update tests/test_examples.py
- update tests/test_settings.py

### Other

- update marksync/cli.py
- update marksync/dsl/executor.py
- update marksync/settings.py


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
