# marksync — Analiza, porównanie i dokumentacja

## Spis treści

1. [Czym jest marksync](#czym-jest-marksync)
2. [Architektura i kluczowe komponenty](#architektura-i-kluczowe-komponenty)
3. [Do czego służy marksync](#do-czego-służy-marksync)
4. [Czym marksync różni się od Ansible, Terraform, Chef, Puppet](#czym-marksync-różni-się-od-ansible-terraform-chef-puppet)
5. [Tabela porównawcza](#tabela-porównawcza)
6. [Podobieństwa](#podobieństwa)
7. [Unikalne cechy marksync](#unikalne-cechy-marksync)
8. [Ograniczenia marksync](#ograniczenia-marksync)
9. [Przypadki użycia](#przypadki-użycia)
10. [Podsumowanie](#podsumowanie)

---

## Czym jest marksync

**marksync** to platforma do kolaboratywnej edycji i orkiestracji kontraktów (artefaktów) aplikacji w formacie Markdown, opartych na konwencji [Markpact](https://github.com/wronai/markpact). Umożliwia jednoczesną pracę **ludzi**, **agentów AI** (LLM) i **algorytmów** (skryptów) nad wspólnym dokumentem — kontraktem opisującym aplikację web/desktop/mobile.

Kluczowe założenie: **Markdown jest kontraktem** (`README.md`) — pojedynczy plik opisuje zależności, kod źródłowy, konfigurację i instrukcje uruchomienia aplikacji. marksync synchronizuje edycje tego kontraktu w czasie rzeczywistym za pomocą **CRDT** (Conflict-free Replicated Data Types), zapewniając bezkonfliktową współpracę wielu uczestników.

### Filozofia

| Ansible/Terraform/Chef/Puppet | marksync |
|-------------------------------|----------|
| Infrastruktura jako kod (IaC) | **Kontrakt jako kod (CaC)** — dokument Markdown definiujący artefakt aplikacji |
| Zarządzanie serwerami/chmurą | Zarządzanie procesem tworzenia i edycji kontraktu aplikacji |
| Automatyzacja provisioningu | Automatyzacja kolaboracji ludzie ↔ AI ↔ algorytmy |

---

## Architektura i kluczowe komponenty

```
┌─────────────────────────────────────────────────────────────┐
│                    marksync Runtime                         │
│                                                             │
│  ┌───────────────┐   ┌──────────────────────────────────┐   │
│  │ DSL Shell/API │──►│     DSL Executor                 │   │
│  │ (REPL/REST/WS)│   │ agents · pipelines · routes      │   │
│  └───────────────┘   └──────────┬───────────────────────┘   │
│                                 │ spawns / controls         │
│                                 ▼                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Agent Workers                           │   │
│  │  editor (LLM) · reviewer (LLM) · deployer · monitor  │   │
│  └──────────┬───────────────────────────────────────────┘   │
│             │                                               │
│  ┌──────────▼───────────────────────────────────────────┐   │
│  │          Pipeline Engine                             │   │
│  │  LLM steps → HUMAN steps → SCRIPT steps              │   │
│  │  (human-in-the-loop, approval gates)                 │   │
│  └──────────┬───────────────────────────────────────────┘   │
│             │                                               │
│  ┌──────────▼───────────────────────────────────────────┐   │
│  │     SyncServer (WebSocket + CRDT)                    │   │
│  │  pycrdt (Yjs) · delta patches · SHA-256 verify       │   │
│  └──────────┬───────────────────────────────────────────┘   │
│             ▼                                               │
│        README.md (kontrakt Markpact)                        │
└─────────────────────────────────────────────────────────────┘
```

### Moduły (z `project.functions.toon`)

| Moduł | Pliki | Funkcji | Opis |
|-------|-------|---------|------|
| `marksync/sync/` | `crdt.py`, `engine.py`, `__init__.py` | 31 | CRDT document, SyncServer/Client, BlockParser, delta patches |
| `marksync/agents/` | `__init__.py`, `base.py` | 18 | AgentWorker (editor/reviewer/deployer/monitor), OllamaClient |
| `marksync/dsl/` | `parser.py`, `executor.py`, `shell.py`, `api.py` | 49 | DSL parser, executor, interaktywny shell REPL, REST/WS API |
| `marksync/pipeline/` | `engine.py`, `api.py` | 33 | Pipeline engine z aktorami LLM/SCRIPT/HUMAN, human-in-the-loop |
| `marksync/orchestrator.py` | 1 plik | 12 | Odczyt `agents.yml`, orkiestracja cyklu życia agentów |
| `marksync/settings.py` | 1 plik | 9 | Konfiguracja z `.env`, centralne ustawienia |
| `marksync/sandbox/` | `app.py` | 2 | Web sandbox UI do edycji i testów w przeglądarce |
| `marksync/cli.py` | 1 plik | 10 | CLI (Click): server, agent, orchestrate, shell, sandbox, api |
| **tests/** | 7 plików | **157** | Testy DSL, pipeline, orchestrator, scenarios, examples, settings |

---

## Do czego służy marksync

### Główny cel

Kolaboracja **ludzi**, **agentów AI** i **algorytmów** przy tworzeniu i edycji kontraktu (artefaktu) dla aplikacji Markpact:

1. **Ludzie** — edytują bloki kodu/konfiguracji w README.md, zatwierdzają zmiany (human-in-the-loop), podejmują decyzje
2. **Agenci AI (LLM)** — automatycznie ulepszają kod (editor), recenzują jakość (reviewer), generują dokumentację
3. **Algorytmy (skrypty)** — lint, walidacja, formatowanie, deploy, migracja danych

### Scenariusze użycia (zaimplementowane pipeline'y)

| Pipeline | Aktorzy | Przepływ |
|----------|---------|----------|
| **Code Review** | LLM → Human → Script → Script | LLM edytuje → Człowiek recenzuje → Lint → Deploy |
| **Account Creation** | Script → Human → Script → Human | Walidacja → Człowiek podaje dane → Tworzenie → Potwierdzenie |
| **Payment** | Script → Human → Script → Human | Fraud check → Autoryzacja → Przetwarzanie → Potwierdzenie |
| **Doc Generation** | Script → LLM → Human → LLM → Script | Analiza kodu → LLM pisze docs → Recenzja → Poprawa → Publikacja |
| **Incident Response** | Script → Human → LLM → Human → Script | Detekcja → Potwierdzenie → Analiza AI → Rozwiązanie → Zamknięcie |
| **Content Moderation** | LLM → Script → Human → Script | Skan AI → Scoring → Decyzja człowieka → Egzekucja |
| **Data Migration** | Script → LLM → Human → Script → Human | Walidacja schematu → Transformacja → Spot-check → Migracja → Audyt |

---

## Czym marksync różni się od Ansible, Terraform, Chef, Puppet

### Fundamentalna różnica: domena problemu

| Aspekt | Ansible / Terraform / Chef / Puppet | marksync |
|--------|-------------------------------------|----------|
| **Domena** | Zarządzanie infrastrukturą (serwery, chmura, sieć) | Zarządzanie kontraktem aplikacji (dokument Markdown) |
| **Cel** | Provisioning, konfiguracja, utrzymanie infrastruktury | Kolaboratywna edycja artefaktów aplikacji przez ludzi + AI |
| **Obiekt zarządzania** | Serwery, kontenery, usługi chmurowe, pakiety | Bloki kodu/konfiguracji w pliku README.md (Markpact) |
| **Użytkownicy** | DevOps, SysAdminy, Platform Engineers | Deweloperzy, AI agenci, algorytmy — pracujący wspólnie |
| **Paradygmat** | Infrastructure as Code (IaC) | Contract as Code (CaC) — Markdown jest kontraktem |

### Ansible vs marksync

| Cecha | Ansible | marksync |
|-------|---------|----------|
| **Model** | Push-based, agentless (SSH) | WebSocket + CRDT, agent-based (AI workers) |
| **Język konfiguracji** | YAML Playbooks + Jinja2 | YAML (`agents.yml`) + własny DSL (msDSL) |
| **Idempotentność** | Tak — moduły deklaratywne | Nie dotyczy — CRDT zapewnia spójność bez konfliktów |
| **Cel automacji** | Konfiguracja serwerów, deployment | Orkiestracja agentów AI edytujących kod |
| **Rola AI** | Brak (czysta automatyzacja) | Centralna — agenci LLM edytują i recenzują kod |
| **Kolaboracja** | Jednokierunkowa (playbook → serwery) | Wielokierunkowa (ludzie ↔ AI ↔ algorytmy w real-time) |
| **Stan** | Stateless (brak state file) | CRDT document — stan synchronizowany w czasie rzeczywistym |
| **Human-in-the-loop** | Brak (lub ręczna pauza) | Wbudowane — pipeline blokuje i czeka na decyzję człowieka |

### Terraform vs marksync

| Cecha | Terraform | marksync |
|-------|-----------|----------|
| **Model** | Plan → Apply, deklaratywny | Event-driven, real-time sync |
| **Język** | HCL (HashiCorp Configuration Language) | msDSL + YAML (`agents.yml`) |
| **State management** | `.tfstate` — pełny stan infrastruktury | CRDT document (pycrdt/Yjs) — stan dokumentu |
| **Provider model** | Pluginy dla AWS, GCP, Azure, etc. | Pluginy aktorów: LLM, Script, Human |
| **Plan/Preview** | `terraform plan` — podgląd zmian | `--dry-run` — podgląd planu orkiestracji |
| **Drift detection** | Porównanie state vs reality | SHA-256 manifest — detekcja zmian w blokach |
| **Cel** | Tworzenie/niszczenie zasobów chmurowych | Tworzenie/edycja bloków kodu w kontrakcie |
| **Współbieżność** | Lock state file (jeden operator) | CRDT — wielu jednoczesnych edytorów bez locków |

### Chef vs marksync

| Cecha | Chef | marksync |
|-------|------|----------|
| **Model** | Client-server, pull-based | Client-server, event-driven (WebSocket push) |
| **Język** | Ruby DSL (recipes/cookbooks) | Python + msDSL (AGENT, PIPE, ROUTE, ...) |
| **Konwergencja** | Chef client konwerguje node do pożądanego stanu | CRDT konwerguje dokument do spójnego stanu |
| **Abstrakcja** | Resources (package, service, file, ...) | Blocks (markpact:file, markpact:deps, markpact:run) |
| **Testowanie** | ChefSpec, InSpec, Test Kitchen | pytest (157 testów), pipeline scenarios |
| **Agent** | Chef Client (deterministyczny) | AgentWorker (AI-driven, niedeterministyczny) |
| **Rola serwera** | Chef Server — przechowuje cookbooks | SyncServer — przechowuje CRDT document, broadcast |

### Puppet vs marksync

| Cecha | Puppet | marksync |
|-------|--------|----------|
| **Model** | Deklaratywny, pull-based, catalog compilation | Imperatywny DSL + deklaratywny YAML, event-driven |
| **Język** | Puppet DSL (manifesty .pp) | msDSL + YAML + Python API |
| **Catalog** | Skompilowany graf zasobów | OrchestrationPlan (agents + pipelines + routes) |
| **Agent** | Puppet Agent — wymusza stan | AgentWorker — AI/skrypt przetwarzający bloki |
| **Facter** | Zbiera fakty o nodzie | BlockParser — parsuje bloki z Markdown |
| **Raportowanie** | PuppetDB | Event system + snapshot API |
| **Modularność** | Forge modules | Pipeline definitions, Script registry |

---

## Tabela porównawcza

### Główna tabela porównawcza

| Cecha | Ansible | Terraform | Chef | Puppet | **marksync** |
|-------|---------|-----------|------|--------|-------------|
| **Domena** | Infrastruktura | Infrastruktura | Infrastruktura | Infrastruktura | **Kontrakt aplikacji** |
| **Paradygmat** | IaC (procedural) | IaC (deklaratywny) | IaC (konwergentny) | IaC (deklaratywny) | **CaC (kolaboratywny)** |
| **Język** | YAML + Jinja2 | HCL | Ruby DSL | Puppet DSL | **msDSL + YAML + Python** |
| **Model wykonania** | Push (SSH) | Plan → Apply | Pull (client) | Pull (agent) | **Event-driven (WebSocket)** |
| **Stan** | Stateless | .tfstate | Chef Server | PuppetDB | **CRDT Document** |
| **Agenci** | Brak (agentless) | Brak | Chef Client | Puppet Agent | **AI Workers (LLM)** |
| **Rola AI/LLM** | ❌ Brak | ❌ Brak | ❌ Brak | ❌ Brak | **✅ Centralna** |
| **Human-in-the-loop** | ❌ Brak | ❌ Brak | ❌ Brak | ❌ Brak | **✅ Wbudowane** |
| **Kolaboracja real-time** | ❌ | ❌ | ❌ | ❌ | **✅ CRDT delta sync** |
| **Bezkonfliktowa edycja** | N/A | Lock file | N/A | N/A | **✅ CRDT (Yjs)** |
| **DSL** | YAML tasks | HCL | Ruby recipes | Puppet manifesty | **msDSL (16 komend)** |
| **REST API** | Tower/AWX | Cloud/Enterprise | Chef Server API | Puppet API | **✅ FastAPI + WebSocket** |
| **Pipeline/Workflow** | Playbook tasks | N/A | Recipes | Manifesty | **✅ LLM→Human→Script** |
| **Idempotentność** | ✅ Tak | ✅ Tak | ✅ Tak | ✅ Tak | **N/A (CRDT convergence)** |
| **Dry-run** | `--check` | `plan` | `--why-run` | `--noop` | **`--dry-run`** |
| **Licencja** | GPL-3.0 | BSL 1.1 | Apache-2.0 | Apache-2.0 | **Apache-2.0** |
| **Język impl.** | Python | Go | Ruby/Erlang | Ruby/Clojure | **Python** |

### Porównanie modeli orkiestracji

| Aspekt | IaC Tools (Ansible/TF/Chef/Puppet) | **marksync** |
|--------|-------------------------------------|-------------|
| **Co orkiestrują** | Zasoby infrastrukturalne (VM, sieci, pakiety) | Agentów AI, ludzi i algorytmy pracujące nad dokumentem |
| **Obiekt konfiguracji** | Serwer / usługa chmurowa | Blok kodu w README.md (markpact block) |
| **Źródło prawdy** | Playbook/Manifest/HCL + State | `agents.yml` + `README.md` (CRDT) |
| **Kto wykonuje** | Deterministyczne moduły/providery | Niedeterministyczni agenci AI + deterministyczne skrypty |
| **Feedback loop** | Brak lub ręczny | Real-time: agent edytuje → reviewer recenzuje → deployer wdraża |
| **Współbieżność** | Sequential lub limited parallel | Pełna współbieżność (CRDT, zero conflicts) |
| **Interaktywność** | Batch mode | Interaktywny shell REPL + Web sandbox |

---

## Podobieństwa

Mimo fundamentalnych różnic w domenie, marksync podziela pewne wzorce architektoniczne:

### 1. Deklaratywna konfiguracja
- **Ansible**: `playbook.yml` definiuje żądany stan
- **marksync**: `agents.yml` definiuje agentów, pipeline'y i routing

### 2. DSL do orkiestracji
- **Puppet**: `.pp` manifesty z deklaratywnym DSL
- **Terraform**: HCL — deklaratywny język konfiguracji
- **marksync**: msDSL — 16 komend imperatywnych (AGENT, PIPE, ROUTE, SET, DEPLOY, ...)

### 3. Agent-based architecture
- **Puppet**: Puppet Agent na każdym node
- **Chef**: Chef Client na każdym node
- **marksync**: AgentWorker — AI agent per rola (editor, reviewer, deployer, monitor)

### 4. Orkiestracja z jednego punktu
- **Ansible**: Control node → managed nodes
- **Terraform**: Operator → providers
- **marksync**: Orchestrator → AgentWorkers (1 proces, wiele agentów z `agents.yml`)

### 5. State management
- **Terraform**: `.tfstate` — śledzenie stanu zasobów
- **marksync**: CRDT Document — śledzenie stanu bloków w dokumencie

### 6. Event-driven workflow
- **Ansible (AWX)**: Webhooks, scheduling
- **marksync**: Event system (`on("agent.created", ...)`, `on("pipeline.completed", ...)`)

### 7. Pipeline / multi-step workflow
- **Ansible**: Playbook tasks w sekwencji
- **Chef**: Recipe convergence
- **marksync**: Pipeline steps: LLM → Human → Script z approval gates

---

## Unikalne cechy marksync

Cechy, których **nie ma** żadne z narzędzi IaC:

### 1. Kolaboracja ludzie ↔ AI ↔ algorytmy
Pipeline engine obsługuje trzy typy aktorów (`ActorType`): `LLM`, `SCRIPT`, `HUMAN` — w dowolnej kombinacji i kolejności. Człowiek może zatwierdzić/odrzucić wynik pracy AI.

### 2. CRDT-based real-time sync
Edycje różnych bloków przez różnych agentów **nigdy nie powodują konfliktów** dzięki pycrdt (implementacja Yjs). Każdy blok to niezależny `Y.Text` w `Y.Map`.

### 3. Markdown jako kontrakt (Markpact)
Plik `README.md` zawiera bloki `markpact:file`, `markpact:deps`, `markpact:run` — pełna definicja aplikacji w jednym dokumencie. marksync orkiestruje edycję tych bloków.

### 4. Human-in-the-loop pipelines
Pipeline blokuje na krokach `HUMAN`, tworzy `HumanTask`, czeka na rozwiązanie przez API. Umożliwia approval gates, input od człowieka, odrzucenie zmian AI.

### 5. AI-native agent roles
Wbudowane role agentów wykorzystujących LLM (Ollama):
- **Editor** — ulepszanie kodu (error handling, type hints, docstrings)
- **Reviewer** — analiza jakości, bezpieczeństwa, best practices
- **Deployer** — automatyczny rebuild przy zmianach
- **Monitor** — audit trail (SHA-256 hash, rozmiar bloków)

### 6. Interaktywny DSL Shell
REPL z rich formatting, autocompletion — zarządzanie agentami, pipeline'ami, routingiem w czasie rzeczywistym.

---

## Ograniczenia marksync

### Ograniczenia techniczne

| Ograniczenie | Opis |
|-------------|------|
| **Tylko Markpact format** | Działa wyłącznie z plikami README.md w konwencji Markpact (bloki `markpact:*`) |
| **Zależność od Ollama** | Agenci AI wymagają lokalnie uruchomionego Ollama — brak wsparcia dla OpenAI API, Anthropic, etc. |
| **Brak persystencji stanów pipeline** | Pipeline runs są in-memory; restart serwera traci historię |
| **Brak autentykacji/autoryzacji** | API i WebSocket nie mają mechanizmów auth — nieprzygotowane do produkcji |
| **Brak rozproszonego CRDT** | SyncServer jest single-node; brak replikacji CRDT między serwerami |
| **Ograniczony transport** | Tylko WebSocket; MQTT/gRPC to placeholder (`transport/__init__.py` jest pusty) |
| **Brak rollback** | Nie ma mechanizmu cofania zmian w CRDT document (brak undo/history) |
| **Skalowalność** | Wszystkie agenci w jednym procesie Python — ograniczone GIL-em dla CPU-bound |

### Ograniczenia koncepcyjne vs IaC

| Aspekt | Ograniczenie marksync | IaC Tools mają to |
|--------|----------------------|-------------------|
| **Idempotentność** | Brak — agenci AI są niedeterministyczni | Ansible/TF/Chef/Puppet — deterministyczne |
| **Drift detection** | Tylko SHA-256 manifest | Terraform state, Puppet catalog diff |
| **Rollback** | Brak | Terraform: `terraform state`, Ansible: idempotent re-run |
| **Secrets management** | Brak | Ansible Vault, TF vars, Chef encrypted data bags |
| **Multi-environment** | Brak (single README) | TF workspaces, Ansible inventories |
| **Dojrzałość ekosystemu** | v0.2.9, wczesny rozwój | Lata rozwoju, tysiące modułów/providerów |
| **Audyt/compliance** | Podstawowy (monitor agent) | InSpec, Sentinel, OPA |

### Ograniczenia w porównaniu do platform kolaboracyjnych

| Aspekt | Ograniczenie marksync | Alternatywy |
|--------|----------------------|-------------|
| **UI** | Web sandbox (basic) | Google Docs, Notion — zaawansowane UI |
| **Wersjonowanie** | CRDT state (brak Git integracji) | GitHub/GitLab — pełna historia |
| **Uprawnienia** | Brak ról/permissions | GitHub — CODEOWNERS, branch protection |
| **Notyfikacje** | Tylko eventy w logach | Slack, email, webhooks |

---

## Przypadki użycia

### Gdzie marksync ma sens

1. **Prototypowanie aplikacji z AI** — szybka iteracja: AI edytuje kod → człowiek recenzuje → auto-deploy
2. **Code review z asystentem AI** — reviewer agent analizuje jakość, human zatwierdza
3. **Multi-agent document editing** — wielu agentów AI pracuje równolegle nad różnymi blokami
4. **Approval workflows** — pipeline z bramkami zatwierdzenia (np. payment authorization, content moderation)
5. **Edukacja** — interaktywny sandbox do nauki: edytuj Markdown → zobacz wynik w przeglądarce

### Gdzie lepiej użyć IaC tools

| Potrzeba | Narzędzie |
|----------|-----------|
| Provisioning serwerów/VM | **Terraform** |
| Konfiguracja systemu operacyjnego | **Ansible** lub **Puppet** |
| Zarządzanie pakietami/usługami | **Chef** lub **Ansible** |
| Multi-cloud infrastructure | **Terraform** |
| Compliance/audyt infrastruktury | **Puppet** + InSpec |
| CI/CD pipeline | GitHub Actions, GitLab CI, Jenkins |

### Potencjalna synergia

marksync i narzędzia IaC **nie konkurują** — mogą współpracować:

```
README.md (Markpact kontrakt)
    │
    ├── marksync edytuje kod aplikacji (ludzie + AI)
    │
    ├── markpact buduje artefakt (Docker image)
    │
    └── Terraform/Ansible wdraża artefakt na infrastrukturę
```

---

## Podsumowanie

### marksync to **nie** narzędzie IaC

marksync nie zarządza infrastrukturą. Nie jest alternatywą dla Ansible, Terraform, Chef ani Puppet. Działa na zupełnie innym poziomie abstrakcji.

### marksync to **platforma kolaboracji dla kontraktów aplikacji**

| | IaC Tools | marksync |
|-|-----------|----------|
| **Metafora** | Zarządca budynku (konfiguruje infrastrukturę) | Zespół architektów (ludzie + AI projektują budynek) |
| **Input** | Playbook/HCL/Manifest | README.md z blokami Markpact |
| **Output** | Skonfigurowana infrastruktura | Wyedytowany kontrakt aplikacji (gotowy do markpact build) |
| **Uczestnicy** | Operator + deterministyczne moduły | Ludzie + agenci AI + algorytmy (pipeline) |
| **Komunikacja** | Jednokierunkowa (push/pull) | Wielokierunkowa (CRDT real-time sync) |

### Klasyfikacja marksync

Marksync najlepiej klasyfikować jako:

> **Multi-agent collaborative contract editing platform with human-in-the-loop pipelines and CRDT-based real-time synchronization**

Kategoria: **AI-augmented collaborative development tool**, nie Infrastructure as Code.

---

*Wygenerowano na podstawie analizy kodu źródłowego marksync v0.2.9 (`project.functions.toon`: 28 modułów, 397 funkcji, 157 testów)*
