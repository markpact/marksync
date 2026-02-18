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
sleep 1

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
sleep 1

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
sleep 1

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
│                              │                                      │
│              ┌───────────────┼───────────────┐                      │
│              ▼               ▼               ▼                      │
│        ┌──────────┐    ┌──────────┐    ┌──────────┐                 │
│        │  editor  │    │ reviewer │    │ deployer │                 │
│        │  agent   │    │  agent   │    │  agent   │                 │
│        └──────────┘    └──────────┘    └──────────┘                 │
│                                                                     │
│   Protocol: manifest → patch/full → ack/nack → broadcast            │
└─────────────────────────────────────────────────────────────────────┘
ARCH
sleep 1

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
echo -e "${YELLOW}Ewolucja w praktyce (10 ITERACJI):${NC}"
cat << 'EVOLUTION'
  ╔══════════════════════════════════════════════════════════════════════════╗
  ║  ITER  │ PROJEKT           │ RESULT  │ RATE   │ ACTION                    ║
  ╠══════════════════════════════════════════════════════════════════════════╣
  ║  1     │ REST API basic    │ ✓ OK    │ 1.00   │ Nowy pattern              ║
  ║  2     │ REST API + auth   │ ✓ OK    │ 1.00   │ Reuse pattern + extend    ║
  ║  3     │ REST API + WS     │ ✗ FAIL  │ 0.67   │ WebSocket nie działa      ║
  ║  4     │ REST API + CRUD   │ ✓ OK    │ 0.75   │ Powrót do sprawdzonego    ║
  ║  5     │ GraphQL API       │ ✗ FAIL  │ 0.60   │ Nowy paradygmat - błąd    ║
  ║  6     │ REST API + cache  │ ✓ OK    │ 0.67   │ Redis dodany do pattern   ║
  ║  7     │ REST API + queue  │ ✓ OK    │ 0.71   │ Celery rozszerzenie       ║
  ║  8     │ gRPC service      │ ✗ FAIL  │ 0.63   │ Protobuf issues           ║
  ║  9     │ REST API + JWT    │ ✓ OK    │ 0.67   │ Auth pattern wygrywa      ║
  ║  10    │ REST API full     │ ✓ OK    │ 0.70   │ Best pattern dominuje     ║
  ╚══════════════════════════════════════════════════════════════════════════╝
EVOLUTION

echo ""
echo -e "${YELLOW}Mechanizm ewolucji:${NC}"
echo "  • Patterns z rate > 0.7 są preferowane przy generate"
echo "  • Patterns z rate < 0.5 są automatycznie archiwizowane"
echo "  • Nowe projekty używają best-matching pattern jako template"
echo "  • Sukcesy wzmacniają pattern, porażki osłabiają"
echo ""
sleep 1

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 5b: MAN-IN-THE-LOOP — Human Approval w Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}[FASE 5b] MAN-IN-THE-LOOP — Human Approval w Pipeline${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}\n"
# Build a payment API that requires human approval before deployment
echo -e "${YELLOW}Jak wymusić actor: human w wygenerowanym YAML?${NC}"
echo ""
echo -e "${BOLD}OPCJA 1: Jednozdaniowy prompt (NAJPROSTSZE):${NC}"
echo ""
echo -e "${GREEN}  'Build a payment API that requires human approval before deployment'${NC}"
echo ""
echo -e "${YELLOW}To wystarczy! LLM zrozumie i wygeneruje actor: human.${NC}"
echo ""
echo -e "${BOLD}OPCJA 2: Pełniejszy prompt z wymaganiami:${NC}"
echo ""
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat << 'HUMAN_PROMPT'
prompt: |
  Build a payment service with CRITICAL REQUIREMENTS:
  
  - Generate a pipeline with HUMAN APPROVAL steps
  - Before deployment, a human must review and approve:
    * Security audit
    * Compliance check (PCI-DSS)
    * Final deployment approval
  - Use actor: human for approval steps
  - Use actor: llm for code generation steps
HUMAN_PROMPT
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

echo ""
echo -e "${BOLD}LLM wygeneruje pipeline z actor: human:${NC}"
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat << 'PIPELINE_YAML'
pipeline:
  name: payment-service
  steps:
    - name: generate_code
      actor: llm
      config:
        role: editor
        description: "Generate payment code"
    
    - name: security_review
      actor: llm
      config:
        role: reviewer
        description: "Automated security scan"
    
    - name: human_security_approval    # ← HUMAN!
      actor: human
      config:
        description: "CRITICAL: Human must approve security"
        timeout: 3600  # 1 hour to respond
    
    - name: compliance_check
      actor: llm
      config:
        role: reviewer
        description: "PCI-DSS compliance scan"
    
    - name: human_compliance_approval  # ← HUMAN!
      actor: human
      config:
        description: "CRITICAL: Human must approve compliance"
        timeout: 3600
    
    - name: deploy_staging
      actor: llm
      config:
        role: deployer
        description: "Deploy to staging environment"
    
    - name: human_deployment_approval  # ← HUMAN!
      actor: human
      config:
        description: "CRITICAL: Final approval before production"
        timeout: 7200  # 2 hours
    
    - name: deploy_production
      actor: llm
      config:
        role: deployer
        description: "Deploy to production"
PIPELINE_YAML
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

echo ""
echo -e "${YELLOW}Jak działa actor: human w praktyce:${NC}"
echo "  1. Pipeline zatrzymuje się na kroku z actor: human"
echo "  2. System wysyła powiadomienie (webhook/email/slack)"
echo "  3. Czeka na response z approve/reject"
echo "  4. Jeśli timeout → automatyczny reject"
echo "  5. Jeśli approve → pipeline kontynuuje"
echo "  6. Jeśli reject → pipeline zatrzymuje się z błędem"
echo ""
sleep 1

echo -e "${BOLD}Przykładowy plik prompt:${NC}"
echo -e "  ${CYAN}examples/pipeline_human_approval.yaml${NC}"
echo ""
echo -e "${BOLD}Uruchomienie:${NC}"
echo -e "  ${CYAN}marksync generate --prompt examples/pipeline_human_approval.yaml${NC}"
sleep 1

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 5c: EWOLUCJA NA BAZIE METRYK — Optymalizacja przez Dane
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}[FASE 5c] EWOLUCJA NA BAZIE METRYK — Optymalizacja Parametrów${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}System zbiera metryki i automatycznie optymalizuje parametry:${NC}"
echo ""

cat << 'METRICS_TABLE'
╔═══════════════════════════════════════════════════════════════════════════════╗
║  METRYKA              │ PRÓG      │ AKCJA PRZY PRZEKROCZENIU                  ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  error_rate > 5%      │ CRITICAL  │ Rollback + zwiększ retry_count            ║
║  latency_p95 > 500ms  │ WARNING   │ Dodaj cache layer                         ║
║  memory > 80%         │ WARNING   │ Zwiększ workers, zmniejsz batch_size      ║
║  timeout_rate > 2%    │ WARNING   │ Zwiększ timeout z 30s → 60s               ║
║  success_rate < 95%   │ CRITICAL  │ Archiwizuj pattern, użyj backup           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
METRICS_TABLE

echo ""
echo -e "${BOLD}Przykład ewolucji na bazie błędów:${NC}"
echo ""
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat << 'EVOLUTION_EXAMPLE'
ITERACJA 1: REST API v1.0
  ├─ Deploy: ✓ OK
  ├─ Metryki po 1h:
  │  ├─ error_rate: 8.2% (❌ > 5%)
  │  ├─ latency_p95: 650ms (❌ > 500ms)
  │  └─ timeout_rate: 3.5% (❌ > 2%)
  └─ AKCJA: System generuje patch

ITERACJA 2: REST API v1.1 (auto-patch)
  ├─ Zmiany:
  │  ├─ retry_count: 3 → 5
  │  ├─ timeout: 30s → 60s
  │  ├─ cache: None → Redis (TTL=300s)
  │  └─ workers: 4 → 8
  ├─ Deploy: ✓ OK
  ├─ Metryki po 1h:
  │  ├─ error_rate: 2.1% (✓ < 5%)
  │  ├─ latency_p95: 180ms (✓ < 500ms)
  │  └─ timeout_rate: 0.3% (✓ < 2%)
  └─ AKCJA: Pattern zapisany jako "api-rest-optimized"

ITERACJA 3: REST API v1.2 (fine-tuning)
  ├─ Zmiany:
  │  ├─ cache TTL: 300s → 600s (więcej cache hits)
  │  └─ batch_size: 100 → 50 (mniejsze memory)
  ├─ Deploy: ✓ OK
  ├─ Metryki po 1h:
  │  ├─ error_rate: 0.8% (✓✓ excellent)
  │  ├─ latency_p95: 95ms (✓✓ excellent)
  │  └─ success_rate: 99.2%
  └─ AKCJA: Pattern promowany do "best-practice"
EVOLUTION_EXAMPLE
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

echo ""
echo -e "${BOLD}Jak to działa w kodzie:${NC}"
echo ""
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat << 'CODE_EXAMPLE'
# marksync/learning/optimizer.py

class MetricsOptimizer:
    def analyze_and_patch(self, contract_path: str, metrics: dict):
        """Analizuje metryki i generuje patch do parametrów."""
        
        # Zbierz metryki z Prometheus/dashboard
        error_rate = metrics.get("error_rate", 0)
        latency_p95 = metrics.get("latency_p95", 0)
        timeout_rate = metrics.get("timeout_rate", 0)
        
        patches = []
        
        # Reguła 1: Wysokie błędy → zwiększ retry
        if error_rate > 0.05:  # > 5%
            patches.append({
                "path": "pipeline.retry_policy.max_attempts",
                "old": 3,
                "new": 5,
                "reason": f"error_rate={error_rate:.1%} > 5%"
            })
        
        # Reguła 2: Wolne requesty → dodaj cache
        if latency_p95 > 500:  # > 500ms
            patches.append({
                "path": "services.api.cache",
                "old": None,
                "new": {"type": "redis", "ttl": 300},
                "reason": f"latency_p95={latency_p95}ms > 500ms"
            })
        
        # Reguła 3: Timeouty → zwiększ timeout
        if timeout_rate > 0.02:  # > 2%
            patches.append({
                "path": "services.api.timeout",
                "old": 30,
                "new": 60,
                "reason": f"timeout_rate={timeout_rate:.1%} > 2%"
            })
        
        # Zastosuj patches do README.md
        if patches:
            self.apply_patches(contract_path, patches)
            return True
        return False
CODE_EXAMPLE
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

echo ""
echo -e "${BOLD}DSL Commands dla optymalizacji:${NC}"
echo ""
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat << 'DSL_OPTIMIZE'
# Zbierz metryki z ostatniej godziny
marksync> METRICS ./generated/my-api/README.md --last 1h

# Wynik:
# {
#   "error_rate": 0.082,
#   "latency_p95": 650,
#   "timeout_rate": 0.035,
#   "success_rate": 0.918
# }

# Automatyczna optymalizacja
marksync> OPTIMIZE ./generated/my-api/README.md --auto

# System:
# ✓ Patch 1: retry_count 3 → 5 (error_rate=8.2% > 5%)
# ✓ Patch 2: timeout 30s → 60s (timeout_rate=3.5% > 2%)
# ✓ Patch 3: cache added (latency_p95=650ms > 500ms)
# ✓ Redeploy triggered
# ⏳ Waiting for new metrics...

# Po 1h sprawdź ponownie
marksync> METRICS ./generated/my-api/README.md --last 1h

# Wynik po optymalizacji:
# {
#   "error_rate": 0.021,      # ✓ 8.2% → 2.1%
#   "latency_p95": 180,       # ✓ 650ms → 180ms
#   "timeout_rate": 0.003,    # ✓ 3.5% → 0.3%
#   "success_rate": 0.979     # ✓ 91.8% → 97.9%
# }

# Zapisz jako best-practice pattern
marksync> LEARN ./generated/my-api/README.md --success true --tag optimized
DSL_OPTIMIZE
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

echo ""
echo -e "${YELLOW}Feedback loop w praktyce:${NC}"
echo ""
cat << 'FEEDBACK_LOOP'
  ┌──────────────────────────────────────────────────────────────┐
  │                    CONTINUOUS EVOLUTION                       │
  └──────────────────────────────────────────────────────────────┘
  
  1. DEPLOY → Production
     │
  2. MONITOR → Zbierz metryki (error_rate, latency, timeouts)
     │
  3. ANALYZE → Porównaj z progami (5%, 500ms, 2%)
     │
  4. DECIDE → Jeśli przekroczone:
     │         ├─ Generuj patches (retry, timeout, cache)
     │         └─ Trigger redeploy
     │
  5. VERIFY → Sprawdź nowe metryki po 1h
     │
  6. LEARN → Jeśli lepsze:
     │        ├─ Zapisz pattern z wyższym success_rate
     │        └─ Użyj w kolejnych projektach
     │
  └─→ REPEAT (ciągła optymalizacja)
FEEDBACK_LOOP

echo ""
echo -e "${YELLOW}Przykłady automatycznych optymalizacji:${NC}"
echo "  • Błędy 8% → 2%: retry_count 3→5, circuit_breaker dodany"
echo "  • Latencja 650ms → 180ms: Redis cache, connection pooling"
echo "  • Timeouty 3.5% → 0.3%: timeout 30s→60s, async workers"
echo "  • Memory 85% → 45%: batch_size 100→50, garbage collection"
echo ""
sleep 1

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
sleep 1

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 7: PODSUMOWANIE I NASTĘPNE KROKI
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}[FASE 7] PODSUMOWANIE I NASTĘPNE KROKI${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Teraz możesz uruchomić poszczególne komendy:${NC}\n"
echo "  marksync init           — konfiguracja LLM"
echo "  marksync generate       — generowanie usługi"
echo "  marksync shell          — DSL shell"
echo "  marksync server         — sync server"
echo "  marksync orchestrate    — uruchom agenty"
echo ""
sleep 1

echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}Demo zakończone!${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}\n"
