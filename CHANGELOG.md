## [0.2.20] - 2026-02-18

### Summary

feat(docs): CLI interface improvements

### Docs

- docs: update README
- docs: update TODO-v2-implementation.md
- docs: update TODO.md

### Test

- update tests/test_dsl.py
- update tests/test_pipeline.py
- update tests/test_pipeline_scenarios.py
- update tests/test_v2.py

### Build

- update pyproject.toml

### Config

- config: update goal.yaml

### Other

- update LICENSE
- build: update Makefile
- config: update agents.yml
- scripts: update demo_scenario.sh
- update marksync/cli.py
- update marksync/sync/engine.py
- update project.functions.toon
- scripts: update project.sh
- update project.toon-schema.json


## [0.2.19] - 2026-02-18

### Summary

refactor(docs): configuration management system

### Docs

- docs: update TODO.md

### Other

- update marksync/agents/__init__.py
- update marksync/dashboard/app.py
- update marksync/dsl/executor.py
- update marksync/dsl/parser.py
- update marksync/sync/crdt.py
- update marksync/sync/engine.py


## [0.2.18] - 2026-02-18

### Summary

feat(docs): CLI interface improvements

### Docs

- docs: update README

### Build

- update pyproject.toml

### Other

- update .gitignore
- update marksync/cli.py
- update marksync/dashboard/app.py
- update marksync/dashboard/html.py
- update marksync/dsl/shell.py


## [0.2.17] - 2026-02-18

### Summary

fix(dashboard): contract path wired from --contract arg; fix deploy error message

### Bug Fixes

- `cli.py` — deploy step showed empty error message: `result.get('error')` was always empty on non-zero exit because the return dict uses key `output`, not `error`; now falls back to `output[:200]` then `rc=N`
- `dashboard/app.py` — `create_dashboard_app()` now accepts `contract_path` arg; stored in `app.state`; exposed via `GET /api/config`; injected into HTML as `__INITIAL_CONTRACT_PATH__` placeholder
- `dashboard/html.py` — `App` component initial `contractPath` state now uses server-injected value instead of hardcoded `'README.md'`; `ContractPanel` syncs local path state when prop changes via `useEffect`
- `.gitignore` — added `build-*/` pattern to catch `build-web-dashboard/` and similar generated dirs
- `cli.py` — `dashboard_cmd` now passes `contract or settings.PROJECT_README` to `create_dashboard_app()`

### Test

- Full suite: 274 passed, 7 skipped

### Other

- update marksync/cli.py
- update marksync/dashboard/app.py
- update marksync/dashboard/html.py
- update .gitignore


## [0.2.16] - 2026-02-18

### Summary

feat(pactown): deploy monitoring, health-check feedback loop, and auto-fix pipeline

### Features

- `Plugin.health_check(crdt_doc=None)` — recurring health check with latency measurement, writes `markpact:state` and `markpact:log`
- `PactownMonitor.watch(crdt_doc, pipeline_engine, stop_after)` — standalone async watch loop (no WebSocket required), polls health, updates CRDT blocks, triggers auto-fix on degraded health
- `PactownMonitor._trigger_autofix(engine, status, crdt_doc)` — starts `pactown-autofix` pipeline run and logs `AUTOFIX_TRIGGERED` event
- `PactownMonitor.set_pipeline_engine(engine)` — inject PipelineEngine for auto-fix integration
- `PipelineEngine.register_autofix_pipeline(restart_fn=None)` — registers built-in `pactown-autofix` pipeline (diagnose → pactown-restart → verify)
- Built-in scripts: `diagnose` (health status analysis), `pactown_restart` (runs `pactown restart <config>`)
- Feedback loop: degraded health → `markpact:state` update → `markpact:history` event → auto-fix pipeline trigger

### Docs

- docs: update TODO-v2-implementation.md

### Test

- 30 new tests covering: `Plugin.health_check`, `PactownMonitor.watch`, `_trigger_autofix`, `register_autofix_pipeline`, `diagnose`/`pactown_restart` scripts
- Full suite: 274 passed, 7 skipped

### Other

- build: update Makefile
- update marksync/plugins/integrations/pactown.py
- update marksync/agents/__init__.py
- update marksync/pipeline/engine.py
- update marksync/sync/crdt.py
- update tests/test_v2.py


## [0.2.14] - 2026-02-18

### Summary

refactor(config): configuration management system

### Docs

- docs: update README

### Test

- update tests/test_v2.py

### Build

- update pyproject.toml

### Other

- update marksync/agents/__init__.py
- update marksync/dsl/executor.py
- update marksync/dsl/parser.py
- update marksync/intent/parser.py
- update marksync/learning/patterns.py
- update marksync/pipeline/api.py
- update marksync/sandbox/app.py
- update marksync/sync/__init__.py
- update project.functions.toon
- update project.toon


## [0.2.13] - 2026-02-18

### Summary

refactor(docs): CLI interface improvements

### Docs

- docs: update generate.md
- docs: update pipelines.md
- docs: update plugins.md

### Other

- update marksync/cli.py
- update marksync/contract/__init__.py
- update marksync/contract/block_types.py
- update marksync/contract/generator.py
- update marksync/contract/templates.py
- update marksync/conversation/__init__.py
- update marksync/conversation/engine.py
- update marksync/dashboard/__init__.py
- update marksync/dashboard/app.py
- update marksync/dashboard/html.py
- ... and 13 more


## [0.2.12] - 2026-02-18

### Summary

feat(docs): CLI interface improvements

### Docs

- docs: update api-adapters.md
- docs: update channels.md
- docs: update README
- docs: update vs-airflow.md
- docs: update vs-camunda.md
- docs: update vs-iac.md
- docs: update vs-n8n.md
- docs: update vs-temporal.md
- docs: update formats.md
- docs: update generate.md
- ... and 3 more

### Test

- update tests/test_hardware_detect.py

### Build

- update pyproject.toml

### Other

- update .env.example
- update .gitignore
- config: update channel_config.yaml
- config: update docker-compose.e2e.yml
- update examples/channels/mosquitto.conf
- update examples/channels/test_channels_e2e.py
- config: update pipeline_prompt.yaml
- update marksync/__init__.py
- update marksync/cli.py
- update marksync/hardware_detect.py
- ... and 18 more


## [0.2.11] - 2026-02-18

### Summary

feat(examples): configuration management system

### Docs

- docs: update plugins.md

### Other

- update examples/bpmn_multiagent.py
- update examples/output/1_parallel_review.bpmn
- update examples/output/2_async_notification.bpmn
- update examples/output/3_approval_gateway.bpmn
- update examples/output/4_full_collaboration.bpmn
- update marksync/plugins/__init__.py
- update marksync/plugins/api/__init__.py
- update marksync/plugins/api/asyncapi.py
- update marksync/plugins/api/graphql.py
- update marksync/plugins/api/grpc.py
- ... and 21 more


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
