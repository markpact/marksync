#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# marksync DEMO SCENARIO — Kompletny przepływ od promptu do działającej usługi
# ═══════════════════════════════════════════════════════════════════════════════
#
# Ten skrypt demonstruje pełny workflow marksync:
#
#   1. INIT      — Konfiguracja LLM provider (Ollama/OpenRouter/etc)
#   2. GENERATE  — Prompt → LLM → Generowanie kodu + Docker
#   3. SHELL     — DSL shell do zarządzania agentami
#   4. SYNC      — CRDT sync server dla współpracy agentów
#   5. LEARN     — Pattern library + feedback dla ewolucji
#
# Uruchomienie:
#   chmod +x demo_scenario.sh
#   ./demo_scenario.sh
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# Kolory dla czytelności
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                    MARKSYNC DEMO SCENARIO                                   ║"
echo "║              Od Promptu do Działającej Usługi + Ewolucja                     ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 0: SPRAWDZENIE WYMAGAŃ
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "\n${BOLD}[FASE 0] Sprawdzanie wymagań...${NC}\n"

# Sprawdź czy marksync jest zainstalowany (w venv lub globalnie)
MARKSYNC_PATH=""
if [ -f "./.venv/bin/marksync" ]; then
    MARKSYNC_PATH="./.venv/bin/marksync"
    source .venv/bin/activate 2>/dev/null || true
    echo -e "${GREEN}✓ marksync zainstalowany w .venv${NC}"
elif command -v marksync &> /dev/null; then
    MARKSYNC_PATH="marksync"
    echo -e "${GREEN}✓ marksync zainstalowany globalnie${NC}"
else
    echo -e "${YELLOW}marksync nie jest zainstalowany. Instaluję w venv...${NC}"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e . 2>/dev/null || pip install marksync[all]
    MARKSYNC_PATH="./.venv/bin/marksync"
fi

# Sprawdź ponownie
if [ ! -f "$MARKSYNC_PATH" ] && ! command -v marksync &> /dev/null; then
    echo -e "${RED}Nie udało się zainstalować marksync.${NC}"
    exit 1
fi

# Sprawdź .env
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Tworzę .env z .env.example...${NC}"
    cp .env.example .env 2>/dev/null || echo "OLLAMA_URL=http://localhost:11434" > .env
fi
echo -e "${GREEN}✓ .env skonfigurowany${NC}"

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 1: INIT — Konfiguracja LLM Provider
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}[FASE 1] INIT — Konfiguracja LLM Provider${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Co się dzieje:${NC}"
echo "  1. marksync init wykrywa hardware (GPU, RAM, Ollama)"
echo "  2. Użytkownik wybiera provider: Ollama (lokalny) lub OpenRouter (cloud)"
echo "  3. Klucz API jest zapisywany do .env"
echo "  4. Test połączenia z LLM"
echo ""

# Sprawdź czy Ollama działa
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ollama działa na localhost:11434${NC}"
    OLLAMA_MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print(' '.join([m['name'] for m in d.get('models',[])]))" 2>/dev/null || echo "")
    if [ -n "$OLLAMA_MODELS" ]; then
        echo -e "  Dostępne modele: ${CYAN}$OLLAMA_MODELS${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Ollama nie działa. Uruchom: ollama serve${NC}"
    echo -e "  Alternatywnie użyj OpenRouter (wymaga klucza API)"
fi

echo ""
echo -e "${BOLD}Komenda:${NC} marksync init"
echo -e "${YELLOW}──────────────────────────────────────────────────────────────────────────────${NC}"
echo "To uruchomi interaktywny wizard do konfiguracji LLM."
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 2: GENERATE — Prompt → LLM → Kod + Docker
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}[FASE 2] GENERATE — Prompt → LLM → Generowanie Usługi${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Co się dzieje:${NC}"
echo "  1. Użytkownik tworzy pipeline.yaml z opisem co chce zbudować"
echo "  2. marksync generate czyta YAML i buduje prompt dla LLM"
echo "  3. LLM (OpenRouter/Ollama) generuje:"
echo "     - Kompletny kod aplikacji (FastAPI/Flask/etc)"
echo "     - Dockerfile"
echo "     - docker-compose.yml"
echo "     - README.md"
echo "  4. Pliki są zapisywane do ./generated/<service-name>/"
echo ""

# Tworzymy przykładowy prompt YAML dla demo
cat > /tmp/demo_prompt.yaml << 'EOF'
name: hello-api
description: Prosty REST API z endpointem /hello

prompt: |
  Build a minimal FastAPI REST API with:
  1. GET /hello?name=X → {"message": "Hello, X!"}
  2. GET /health → {"status": "ok"}
  3. Include CORS middleware
  4. Use Pydantic for response models

agents:
  - role: editor
    description: Generates the main application code
  - role: reviewer
    description: Reviews code quality

services:
  - name: api
    port: 8000
    framework: fastapi
    healthcheck: /health

output_dir: ./generated/hello-api
EOF

echo -e "${BOLD}Przykładowy pipeline.yaml:${NC}"
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat /tmp/demo_prompt.yaml
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

echo ""
echo -e "${BOLD}Komenda:${NC} marksync generate --prompt /tmp/demo_prompt.yaml"
echo ""
echo -e "${YELLOW}Co LLM generuje (przykładowy output):${NC}"
echo "  app/main.py        — Kod FastAPI aplikacji"
echo "  app/requirements.txt — Zależności (fastapi, uvicorn, pydantic)"
echo "  api/Dockerfile     — Kontener Docker"
echo "  docker-compose.yml — Definicja serwisu"
echo "  README.md          — Dokumentacja"

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 3: DSL SHELL — Zarządzanie Agentami
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}[FASE 3] DSL SHELL — Interaktywne Zarządzanie Agentami${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Co się dzieje:${NC}"
echo "  1. marksync shell uruchamia REPL dla DSL"
echo "  2. DSL pozwala tworzyć agentów, pipeline'y, routes"
echo "  3. Agenty komunikują się przez CRDT sync server"
echo ""

echo -e "${BOLD}Komenda:${NC} marksync shell"
echo ""
echo -e "${BOLD}Przykładowa sesja DSL:${NC}"
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat << 'DSL_EXAMPLE'
marksync> AGENT coder editor --model qwen2.5-coder:7b --auto-edit
marksync> AGENT reviewer-1 reviewer
marksync> AGENT deployer-1 deployer
marksync> AGENT monitor-1 monitor

marksync> PIPE review-flow coder -> reviewer-1 -> deployer-1
marksync> ROUTE markpact:run -> deployer-1

marksync> LIST agents
marksync> STATUS

marksync> SEND coder "Add error handling to /hello endpoint"

marksync> DEPLOY --force
DSL_EXAMPLE
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

echo ""
echo -e "${YELLOW}Wyjaśnienie komend:${NC}"
echo "  AGENT <name> <role> [--options]  — Tworzy agenta o danej roli"
echo "  PIPE <name> <a> -> <b> -> <c>    — Definiuje pipeline przetwarzania"
echo "  ROUTE <pattern> -> <agent>       — Kieruje bloki do agentów"
echo "  LIST agents                      — Lista aktywnych agentów"
echo "  STATUS                           — Stan systemu"
echo "  SEND <agent> <msg>               — Wysyła wiadomość do agenta"
echo "  DEPLOY [--force]                 — Triggeruje deployment"

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 4: SYNC SERVER — CRDT Współpraca Agentów
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}[FASE 4] SYNC SERVER — CRDT Delta Sync między Agentami${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Co się dzieje:${NC}"
echo "  1. SyncServer zarządza README.md z blokami markpact:*"
echo "  2. Agenty łączą się przez WebSocket"
echo "  3. Zmiany są propagowane jako delta patches (CRDT)"
echo "  4. SHA-256 weryfikacja każdej zmiany"
echo ""

echo -e "${BOLD}Terminal 1 — Sync Server:${NC}"
echo -e "  ${CYAN}marksync server examples/1/README.md${NC}"
echo ""
echo -e "${BOLD}Terminal 2 — Orchestrator (wszystkie agenty):${NC}"
echo -e "  ${CYAN}marksync orchestrate -c agents.yml${NC}"
echo ""
echo -e "${BOLD}Terminal 3 — Pojedynczy agent:${NC}"
echo -e "  ${CYAN}marksync agent --role editor --name coder-1 --auto-edit${NC}"
echo ""

echo -e "${YELLOW}Architektura CRDT Sync:${NC}"
cat << 'ARCH'
┌─────────────────────────────────────────────────────────────────────┐
│                         SyncServer (WS:8765)                         │
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                    CRDTDocument                              │   │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │   │
│   │  │markpact:run │  │markpact:deps│  │markpact:log │  ...     │   │
│   │  └─────────────┘  └─────────────┘  └─────────────┘          │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│              ┌───────────────┼───────────────┐                      │
│              ▼               ▼               ▼                      │
│        ┌──────────┐    ┌──────────┐    ┌──────────┐                 │
│        │  editor  │    │ reviewer │    │ deployer │                 │
│        │  agent   │    │  agent   │    │  agent   │                 │
│        └──────────┘    └──────────┘    └──────────┘                 │
│                                                                      │
│   Protocol: manifest → patch/full → ack/nack → broadcast            │
└─────────────────────────────────────────────────────────────────────┘
ARCH

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 5: LEARNING — Pattern Library + Ewolucja
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}[FASE 5] LEARNING — Pattern Library + Ewolucja na Bazie Danych${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Co się dzieje:${NC}"
echo "  1. Po udanym deployment, LEARN zapisuje kontrakt jako pattern"
echo "  2. Pattern zawiera keywords, success_rate, usage_count"
echo "  3. Przy kolejnym GENERATE, system szuka podobnych patterns"
echo "  4. Patterns z wyższym success_rate są preferowane"
echo "  5. Feedback loop: sukces → +rate, porażka → -rate"
echo ""

echo -e "${BOLD}DSL Commands dla Learning:${NC}"
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat << 'LEARN_DSL'
# Zapisz udany kontrakt jako pattern
marksync> LEARN ./generated/hello-api/README.md --success true

# Pokaż wszystkie patterns
marksync> PATTERNS

# Wynik:
# {
#   "id": "api-rest-fastapi",
#   "keywords": ["rest", "api", "fastapi", "cors", "pydantic"],
#   "success_rate": 0.95,
#   "usage_count": 12,
#   "service_type": "api"
# }
LEARN_DSL
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

echo ""
echo -e "${YELLOW}Struktura Pattern Library:${NC}"
echo "  ~/.marksync/patterns/"
echo "  ├── api-rest-fastapi/"
echo "  │   └── README.md    (kontrakt + markpact:pattern block)"
echo "  ├── websocket-chat/"
echo "  │   └── README.md"
echo "  └── pipeline-etl/"
echo "      └── README.md"

echo ""
echo -e "${YELLOW}Ewolucja w praktyce:${NC}"
echo "  1. Pierwszy projekt: REST API → sukces → pattern z rate=1.0"
echo "  2. Drugi projekt: podobny REST API → system używa pattern jako template"
echo "  3. Trzeci projekt: próba WebSocket → porażka → rate spada"
echo "  4. Czwarty projekt: system preferuje REST patterns nad WebSocket"
echo "  5. Z czasem: patterns z wysokim rate dominują (naturalna selekcja)"

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 6: PEŁNY WORKFLOW — Od Promptu do Deploymentu
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}[FASE 6] PEŁNY WORKFLOW — Kompletny Przepływ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Krok po kroku co się dzieje po wpisaniu promptu:${NC}\n"

echo -e "${BOLD}1. Użytkownik wpisuje prompt w pipeline.yaml:${NC}"
echo "   name: my-service"
echo "   prompt: |"
echo "     Build a REST API that does X, Y, Z..."
echo ""

echo -e "${BOLD}2. marksync generate uruchamia LLM:${NC}"
echo "   → PromptSpec.from_yaml() parsuje YAML"
echo "   → PromptGenerator buduje system prompt z kontekstem marksync"
echo "   → LLMClient.complete() wysyła do OpenRouter/Ollama"
echo "   → LLM generuje YAML z pipeline + files + services"
echo ""

echo -e "${BOLD}3. Parser przetwarza output LLM:${NC}"
echo "   → _parse_response() wyciąga YAML block"
echo "   → files dict zawiera: app/main.py, Dockerfile, docker-compose.yml"
echo "   → write_generated() zapisuje do ./generated/<name>/"
echo ""

echo -e "${BOLD}4. Docker build (opcjonalnie):${NC}"
echo "   → docker compose build"
echo "   → docker compose up -d"
echo "   → Usługa działa na porcie z healthcheck"
echo ""

echo -e "${BOLD}5. Sync Server startuje (dla agentów):${NC}"
echo "   → SyncServer ładuje README.md"
echo "   → CRDTDocument parsuje bloki markpact:*"
echo "   → WebSocket nasłuchuje na porcie 8765"
echo ""

echo -e "${BOLD}6. Agenty łączą się i współpracują:${NC}"
echo "   → editor: analizuje kod, proponuje ulepszenia"
echo "   → reviewer: sprawdza security, best practices"
echo "   → deployer: triggeruje rebuild na zmiany"
echo "   → monitor: loguje wszystkie zmiany"
echo ""

echo -e "${BOLD}7. Feedback i Learning:${NC}"
echo "   → FeedbackCollector.approve() po udanym deploy"
echo "   → PatternLibrary.save_from_contract() zapisuje pattern"
echo "   → success_rate rośnie przy każdym sukcesie"
echo ""

echo -e "${BOLD}8. Ewolucja przy kolejnym projekcie:${NC}"
echo "   → PatternLibrary.find_pattern() szuka podobnych"
echo "   → Najlepsze patterns są używane jako template"
echo "   → System 'uczy się' co działa najlepiej"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 7: INTERAKTYWNE DEMO
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}[FASE 7] INTERAKTYWNE DEMO — Uruchomienie${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Tryb automatyczny: wszystkie fazy kaskadowo z 1s odstępem${NC}"
echo -e "${YELLOW}(Naciśnij Ctrl+C aby przerwać)${NC}
"
sleep 1

echo -e "\n${BOLD}${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}Demo zakończone!${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}\n"
