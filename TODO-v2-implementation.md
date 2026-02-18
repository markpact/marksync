# MarkSync v2 — Lista zadań do implementacji

**Bazując na:** `project_functions.toon` (89 modułów, wygenerowany 2026-02-18T23:01:59)  
**Cel:** Plan Implementacji v2

---

## Legenda statusów

- ✅ **ZROBIONE** — moduł istnieje i działa (widoczny w project_functions.toon z funkcjami)
- ⚠️ **CZĘŚCIOWO** — moduł istnieje, ale wymaga rozszerzenia
- ❌ **BRAK** — moduł nie istnieje lub jest pusty (0 items)
- 🆕 **NOWY** — moduł do utworzenia od zera

---

## 1. PERSYSTENCJA — Markdown jako baza danych

**Status ogólny: ⚠️ CZĘŚCIOWO**

Bloki Markpact w CRDT działają. Brakuje warstwy, która traktuje je jako pełną bazę danych (query, index, garbage collection).

| Zadanie | Gdzie | Status | Szczegóły |
|---------|-------|--------|-----------|
| Nowe typy bloków w BlockParser | `marksync/sync/__init__.py` | ⚠️ | BlockParser.parse() (linia 53-83) parsuje bloki, ale `test_v2` sprawdza 10 typów — zweryfikować czy intent, pipeline, orchestration, deploy, log, state, history, pattern, config są w pełni obsługiwane |
| Append-only `markpact:log` | `marksync/sync/__init__.py` | ❌ | BlockParser nie ma logiki append-only — set_block nadpisuje. Potrzebny `append_to_block()` w CRDTDocument |
| Query po blokach | `marksync/sync/crdt.py` | ❌ | `get_block()` pobiera po ID, ale brak filtrowania po typie (np. "daj mi wszystkie markpact:file") |
| Garbage collection / compaction | `marksync/sync/crdt.py` | ❌ | Historia rośnie bez końca — brak mechanizmu archiwizacji starych logów |
| Pipeline state persistence | `marksync/pipeline/engine.py` | ❌ | Pipeline runs nadal in-memory (25 funkcji, brak persist). Przy restarcie tracą się |

**Gdzie dodać:**
```
marksync/sync/crdt.py          → append_block(), get_blocks_by_kind(), compact_log()
marksync/sync/__init__.py      → BlockParser: walidacja nowych typów bloków
marksync/pipeline/engine.py    → PipelineEngine: serialize/restore run state z CRDT
```

---

## 2. MULTI-PROVIDER LLM (litellm)

**Status ogólny: ⚠️ CZĘŚCIOWO**

Settings obsługuje już multi-provider. CLI ma `init` wizard z OpenRouter, Ollama, litellm custom. Brakuje propagacji do agents i pipeline.

| Zadanie | Gdzie | Status | Szczegóły |
|---------|-------|--------|-----------|
| Settings.llm_config | `marksync/settings.py` | ✅ | `llm_config()` (linia 137-161) buduje LLMConfig per provider |
| CLI init wizard | `marksync/cli.py` | ✅ | `init()` (linia 486-557) — wybór providera, API key, test connection |
| CLI generate (LiteLLM) | `marksync/cli.py` | ✅ | `generate()` (linia 567-798, cc=53) — generuje serwis via LLM |
| LLMClient multi-provider | `marksync/pipeline/llm_client.py` | ⚠️ | 8 funkcji — sprawdzić czy obsługuje litellm oprócz Ollama |
| AgentWorker multi-provider | `marksync/agents/__init__.py` | ⚠️ | OllamaClient hardcoded w nazwie — potrzebna abstrakcja LLMClient |
| IntentParser z litellm | `marksync/intent/parser.py` | ⚠️ | `_parse_with_llm()` (linia 171-199) — czy używa nowego LLMClient? |

**Gdzie dodać:**
```
marksync/pipeline/llm_client.py  → LLMClient abstraction (Ollama, OpenRouter, litellm)
marksync/agents/__init__.py      → zamień OllamaClient na generyczny LLMClient
marksync/intent/parser.py        → IntentParser._parse_with_llm() → use LLMClient
```

---

## 3. DEPLOY VIA PACTOWN

**Status ogólny: ✅ ZROBIONE (podstawy)**

Plugin Pactown istnieje z pełną implementacją (8 funkcji). Brakuje monitoring loop i auto-fix.

| Zadanie | Gdzie | Status | Szczegóły |
|---------|-------|--------|-----------|
| Pactown plugin | `marksync/plugins/integrations/pactown.py` | ✅ | 8 funkcji: meta, export, import, deploy, status, _build_config, _write_config |
| Deploy z kontraktu | `marksync/contract/generator.py` | ✅ | `generate_deploy_block()` (linia 91-108) — generuje markpact:deploy |
| PactownMonitor (watch loop) | `marksync/agents/__init__.py` | ⚠️ | test_v2 sprawdza `test_pactown_monitor_importable` — ale brak szczegółów implementacji |
| Auto-fix pipeline przy degraded health | — | ❌ | Plan v2 opisuje `PactownMonitor.watch()` z auto-fix — brak w kodzie |
| Feedback loop (health → markpact:state) | — | ❌ | Plan v2: health check → update state block → trigger auto-fix |
| CLI `marksync create --deploy` | `marksync/cli.py` | ⚠️ | `create()` (linia 807-941) ma parametr `deploy` — weryfikować czy wywołuje Pactown |

**Gdzie dodać:**
```
marksync/agents/__init__.py                    → PactownMonitor.watch() (async loop)
marksync/plugins/integrations/pactown.py       → health_check() recurring, log do CRDT
marksync/pipeline/engine.py                    → auto-fix pipeline trigger
```

---

## 4. DASHBOARD

**Status ogólny: ⚠️ CZĘŚCIOWO**

Dashboard app istnieje (6 funkcji, 396 linii `create_dashboard_app`). CLI ma `dashboard` command. Brakuje komponentów React SPA.

| Zadanie | Gdzie | Status | Szczegóły |
|---------|-------|--------|-----------|
| FastAPI backend | `marksync/dashboard/app.py` | ✅ | `create_dashboard_app()` (324 linii), SSE broadcast, contract render |
| CLI dashboard command | `marksync/cli.py` | ✅ | `dashboard_cmd()` (linia 989-1019) |
| HTML template | `marksync/dashboard/html.py` | ❌ | Moduł istnieje ale 0 items — pusty |
| ContractView component (live CRDT) | `marksync/dashboard/static/` | 🆕 | Nie istnieje — plan v2: React/Preact SPA z WebSocket |
| ConversationPanel (chat + voice) | `marksync/dashboard/static/` | 🆕 | Nie istnieje |
| PipelineTimeline | `marksync/dashboard/static/` | 🆕 | Nie istnieje |
| BlockEditor | `marksync/dashboard/static/` | 🆕 | Nie istnieje |
| LogStream | `marksync/dashboard/static/` | 🆕 | Nie istnieje |
| DeployStatus (Pactown) | `marksync/dashboard/static/` | 🆕 | Nie istnieje |
| PatternLibrary UI | `marksync/dashboard/static/` | 🆕 | Nie istnieje |
| WebSocket z SyncServer | `marksync/dashboard/app.py` | ⚠️ | SSE broadcast istnieje, ale brak WebSocket consumer z SyncServer |
| Voice input (Web Speech API) | `marksync/dashboard/` | 🆕 | Plan v2: `voice.py` — nie istnieje |

**Gdzie dodać:**
```
marksync/dashboard/html.py                         → zaimplementować (lub zastąpić SPA)
marksync/dashboard/static/                         → 🆕 cały katalog z komponentami
marksync/dashboard/static/dashboard.js             → 🆕 React/Preact SPA entry
marksync/dashboard/static/components/*.jsx         → 🆕 7 komponentów
marksync/dashboard/voice.py                        → 🆕 Web Speech API + Whisper
marksync/dashboard/app.py                          → WebSocket bridge do SyncServer
```

---

## 5. CONVERSATION ENGINE

**Status ogólny: ✅ ZROBIONE (podstawy)**

Engine istnieje z 9 funkcjami. Brakuje zaawansowanego dialogu i integracji z Dashboard.

| Zadanie | Gdzie | Status | Szczegóły |
|---------|-------|--------|-----------|
| ConversationEngine core | `marksync/conversation/engine.py` | ✅ | 9 funkcji: append, get_history, process_message, _persist, clear |
| CRDT persistence | `marksync/conversation/engine.py` | ✅ | `_persist()` zapisuje do markpact:history |
| process_message z LLM | `marksync/conversation/engine.py` | ✅ | `process_message()` (linia 100-138, cc=7) |
| Multi-turn dialog context | — | ❌ | Brak sliding window / context management dla długich konwersacji |
| Voice input integration | — | 🆕 | Brak — plan v2: Web Speech API → transcription → process_message |
| Dashboard WebSocket bridge | — | ❌ | ConversationEngine nie emituje eventów do Dashboard |

**Gdzie dodać:**
```
marksync/conversation/engine.py    → context_window(), emit_event()
marksync/dashboard/app.py          → WebSocket endpoint dla conversation
```

---

## 6. SELF-LEARNING

**Status ogólny: ✅ ZROBIONE (podstawy)**

Pattern library, feedback collector i prompt refiner istnieją. Brakuje embedding search i auto-trigger.

| Zadanie | Gdzie | Status | Szczegóły |
|---------|-------|--------|-----------|
| PatternLibrary | `marksync/learning/patterns.py` | ✅ | 13 funkcji: find_pattern, list_patterns, save_pattern, save_from_contract |
| FeedbackCollector | `marksync/learning/feedback.py` | ✅ | 5 funkcji: approve, reject, comment, complete_run |
| PromptRefiner | `marksync/learning/prompt_refiner.py` | ✅ | 7 funkcji: refine, _load_history, _extract_rejections, _heuristic_refine, _llm_refine |
| Pattern matching (keyword) | `marksync/learning/patterns.py` | ✅ | `_score()` (linia 157-165) — keyword matching |
| Embedding-based similarity | — | 🆕 | Plan v2 wspomina o lepszym matchingu — brak implementacji |
| Auto-save pattern po sukcesie | `marksync/learning/feedback.py` | ⚠️ | `complete_run()` (linia 52-93) — sprawdzić czy auto-save działa |
| CLI `marksync learn` | `marksync/cli.py` | ⚠️ | test_v2 sprawdza `test_learn_command` — weryfikować implementację |
| CLI `marksync patterns` | `marksync/cli.py` | ⚠️ | test_v2 sprawdza `test_patterns_command_empty` |

**Gdzie dodać:**
```
marksync/learning/patterns.py      → embedding_search() (opcjonalnie, z sentence-transformers)
marksync/learning/feedback.py      → auto-trigger pattern save
```

---

## 7. SECURITY & AUTH

**Status ogólny: ❌ BRAK**

Ani SyncServer, ani Dashboard, ani Pipeline API nie mają żadnego mechanizmu auth.

| Zadanie | Gdzie | Status | Szczegóły |
|---------|-------|--------|-----------|
| SyncServer auth | `marksync/sync/engine.py` | ❌ | `_handler()` (linia 102-119) — WebSocket bez auth |
| Dashboard auth | `marksync/dashboard/app.py` | ❌ | FastAPI bez middleware auth |
| Pipeline API auth | `marksync/pipeline/api.py` | ❌ | 8 funkcji — brak auth |
| DSL API auth | `marksync/dsl/api.py` | ❌ | 2 funkcje — brak auth |
| Secrets management | — | 🆕 | Plan v2 nie rozwiązuje — ale potrzebne dla API keys, DB passwords |
| Token-based auth (JWT) | — | 🆕 | Minimum viable: JWT tokens per agent/user |
| Role-based access | — | 🆕 | Kto może approve, kto może deploy |

**Gdzie dodać:**
```
marksync/auth/                     → 🆕 cały pakiet
marksync/auth/__init__.py          → 🆕 
marksync/auth/tokens.py            → 🆕 JWT generation/validation
marksync/auth/middleware.py        → 🆕 FastAPI middleware
marksync/auth/roles.py             → 🆕 Role definitions (admin, agent, viewer)
marksync/sync/engine.py            → auth w _handler()
marksync/dashboard/app.py          → auth middleware
marksync/pipeline/api.py           → auth na endpoints
marksync/dsl/api.py                → auth na endpoints
```

---

## 8. ROLLBACK & VERSIONING

**Status ogólny: ❌ BRAK**

Historia istnieje w `markpact:history`, ale brak mechanizmu rollback.

| Zadanie | Gdzie | Status | Szczegóły |
|---------|-------|--------|-----------|
| markpact:history block | `marksync/conversation/engine.py` | ✅ | Append do history działa |
| Rollback do poprzedniego stanu | `marksync/sync/crdt.py` | ❌ | CRDTDocument nie ma undo/rollback |
| CLI `marksync rollback` | `marksync/cli.py` | ❌ | Komenda nie istnieje |
| Git-like snapshots | — | 🆕 | Snapshot CRDT state przed każdym deploy |
| Diff między wersjami | — | 🆕 | `markpact:history` → visual diff |

**Gdzie dodać:**
```
marksync/sync/crdt.py              → snapshot(), rollback_to(snapshot_id)
marksync/sync/snapshots.py         → 🆕 SnapshotStore (pliki na dysku)
marksync/cli.py                    → rollback command
marksync/dashboard/app.py          → rollback UI endpoint
```

---

## 9. SKALOWALNOŚĆ & RESILIENCE

**Status ogólny: ❌ BRAK**

SyncServer jest single-node. Brak retry w pipeline. Brak clustering.

| Zadanie | Gdzie | Status | Szczegóły |
|---------|-------|--------|-----------|
| SyncServer single-node | `marksync/sync/engine.py` | ✅ (ale ograniczenie) | Działa, ale nie skaluje się |
| Pipeline retry policies | `marksync/pipeline/engine.py` | ❌ | 25 funkcji — brak retry/timeout logic |
| Pipeline timeout per step | `marksync/pipeline/engine.py` | ❌ | Steps nie mają timeoutów |
| Distributed CRDT | `marksync/sync/crdt.py` | ❌ | Brak replikacji między nodami |
| Health endpoint | `marksync/dashboard/app.py` | ⚠️ | Dashboard ma endpointy, ale brak /health per service |
| Graceful shutdown | `marksync/orchestrator.py` | ✅ | `stop()` (linia 210-220) istnieje |

**Gdzie dodać:**
```
marksync/pipeline/engine.py        → RetryPolicy dataclass, timeout per step
marksync/sync/engine.py            → SyncServer: /health endpoint, reconnect logic
marksync/sync/replication.py       → 🆕 (long-term: multi-node CRDT sync)
```

---

## 10. MULTI-ENVIRONMENT

**Status ogólny: ❌ BRAK**

Jeden README.md = jeden environment. Brak odpowiednika TF workspaces.

| Zadanie | Gdzie | Status | Szczegóły |
|---------|-------|--------|-----------|
| Environment profiles | — | 🆕 | dev/staging/prod configs w kontrakcie |
| markpact:env block | `marksync/contract/block_types.py` | ❌ | Nie zdefiniowany |
| CLI `--env` flag | `marksync/cli.py` | ❌ | Brak |
| Pactown multi-env deploy | `marksync/plugins/integrations/pactown.py` | ❌ | Deploy nie rozróżnia env |

**Gdzie dodać:**
```
marksync/contract/block_types.py   → ENV block type
marksync/cli.py                    → --env flag na create, deploy, dashboard
marksync/plugins/integrations/pactown.py → env-aware deploy config
```

---

## 11. TRANSPORT LAYER

**Status ogólny: ❌ PUSTY (placeholder)**

Transport `__init__.py` ma 0 items. Channels istnieją jako pluginy, ale transport jest niezaimplementowany.

| Zadanie | Gdzie | Status | Szczegóły |
|---------|-------|--------|-----------|
| transport/__init__.py | `marksync/transport/__init__.py` | ❌ | 0 items — pusty placeholder |
| 10 channel plugins | `marksync/plugins/channels/*.py` | ✅ | MQTT(12), Redis(10), AMQP(9), NATS(9), SSE(10), WebSocket(9), gRPC(7), CLI(8), Slack(8), HTTP(8) |
| Transport abstraction | — | 🆕 | Brak warstwy łączącej channels z SyncServer |
| SyncServer → MQTT/gRPC | `marksync/sync/engine.py` | ❌ | Tylko WebSocket — plan v2: multi-transport |

**Gdzie dodać:**
```
marksync/transport/__init__.py     → TransportLayer base class
marksync/transport/websocket.py    → 🆕 WebSocket transport (current default)
marksync/transport/mqtt.py         → 🆕 MQTT transport for SyncServer
marksync/transport/grpc.py         → 🆕 gRPC transport for SyncServer
marksync/sync/engine.py            → pluggable transport w SyncServer
```

---

## 12. IDEMPOTENTNOŚĆ

**Status ogólny: ❌ BRAK (by design)**

Agenci AI są niedeterministyczni — to fundamentalne ograniczenie. Ale można dodać guardrails.

| Zadanie | Gdzie | Status | Szczegóły |
|---------|-------|--------|-----------|
| Idempotency keys per pipeline run | `marksync/pipeline/engine.py` | ❌ | Runs nie mają unique keys |
| Duplicate detection | `marksync/pipeline/engine.py` | ❌ | Brak sprawdzenia czy ten sam prompt już był |
| Output validation | `marksync/agents/__init__.py` | ❌ | Agent nie waliduje czy output zmienił się vs input |
| CRDT convergence | `marksync/sync/crdt.py` | ✅ | CRDT gwarantuje spójność — ale nie determinizm |

**Gdzie dodać:**
```
marksync/pipeline/engine.py        → idempotency_key per run, dedup check
marksync/agents/__init__.py        → output diff validation before push
```

---

## Podsumowanie priorytetów

### P0 — Krytyczne (blokują v2)

1. **Pipeline state persistence** → `pipeline/engine.py` + CRDT
2. **Dashboard SPA** → `dashboard/static/` (7 komponentów)
3. **PactownMonitor watch loop** → `agents/__init__.py`
4. **Dashboard WebSocket bridge** → `dashboard/app.py` ↔ `sync/engine.py`

### P1 — Ważne (v2 core features)

5. **LLMClient abstraction** → `pipeline/llm_client.py` → agents, intent
6. **Voice input** → `dashboard/voice.py`
7. **Pipeline retry/timeout** → `pipeline/engine.py`
8. **Append-only log block** → `sync/crdt.py`
9. **Pattern auto-save** → `learning/feedback.py`

### P2 — Potrzebne (production-readiness)

10. **Auth (JWT + middleware)** → 🆕 `auth/` pakiet
11. **Rollback mechanism** → `sync/crdt.py` + `sync/snapshots.py`
12. **Health endpoints** → `dashboard/app.py`, `sync/engine.py`
13. **Transport layer** → `transport/` pakiet

### P3 — Nice-to-have (long-term)

14. **Multi-environment** → block_types, CLI, Pactown
15. **Distributed CRDT** → `sync/replication.py`
16. **Embedding search** → `learning/patterns.py`
17. **Idempotency keys** → `pipeline/engine.py`
18. **CRDT compaction** → `sync/crdt.py`

---

## Statystyki

| Kategoria | Moduły do utworzenia (🆕) | Moduły do rozszerzenia (⚠️) | Brakujące funkcje (❌) |
|-----------|--------------------------|----------------------------|----------------------|
| Persystencja | 0 | 3 | 4 |
| LLM multi-provider | 0 | 3 | 0 |
| Deploy (Pactown) | 0 | 3 | 2 |
| Dashboard | ~10 (static/) | 2 | 2 |
| Conversation | 0 | 2 | 2 |
| Self-learning | 0 | 2 | 1 |
| Security | 4 (auth/) | 4 | 7 |
| Rollback | 1 (snapshots) | 2 | 3 |
| Skalowalność | 1 (replication) | 2 | 3 |
| Multi-env | 0 | 3 | 3 |
| Transport | 3 | 1 | 1 |
| Idempotentność | 0 | 2 | 2 |
| **RAZEM** | **~19** | **~31** | **~30** |

---

*Na podstawie: project_functions.toon (89 modułów, 2026-02-18), MarkSync Implementation Plan v2, comparison articles*
