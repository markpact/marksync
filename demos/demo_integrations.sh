#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# DEMO: Integrations — Komunikacja z procesem przez API/Shell/Email/Webhook
# ═══════════════════════════════════════════════════════════════════════════════
#
# Ten skrypt pokazuje jak komunikować się z uruchomionym pipeline:
#   - REST API (approve/reject/status)
#   - Shell (DSL commands)
#   - Webhook (external notification)
#   - Email (simulated)
#
# System zakłada human-in-the-loop na początku każdego procesu.
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
DELAY=${DEMO_DELAY:-1}

if [ -f ".venv/bin/activate" ]; then source .venv/bin/activate 2>/dev/null; fi

step() { echo -e "\n${BOLD}${CYAN}[$1]${NC} $2"; sleep "$DELAY"; }
info() { echo -e "  ${YELLOW}→${NC} $1"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
cmd()  { echo -e "  ${DIM}\$${NC} ${CYAN}$1${NC}"; }

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║  DEMO: Integrations — Komunikacja z Procesem                                ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ═══════════════════════════════════════════════════════════════════════════════
step "1/7" "Pipeline z Human-in-the-Loop (domyślny model)"
# ═══════════════════════════════════════════════════════════════════════════════

info "Marksync ZAWSZE zakłada human-in-the-loop na początku:"
echo ""
cat << 'HITL'
  ┌──────────────────────────────────────────────────────────────────┐
  │  DOMYŚLNY MODEL: Human → LLM → Script → Human → Deploy          │
  ├──────────────────────────────────────────────────────────────────┤
  │                                                                  │
  │  👤 HUMAN: initial_approval     ← ZAWSZE na początku             │
  │     │                                                            │
  │  🤖 LLM: generate_code          (auto)                          │
  │     │                                                            │
  │  ⚙️ SCRIPT: run_tests            (auto)                          │
  │     │                                                            │
  │  👤 HUMAN: deploy_approval      ← ZAWSZE przed deploy            │
  │     │                                                            │
  │  🤖 LLM: deploy                  (auto)                          │
  │                                                                  │
  └──────────────────────────────────────────────────────────────────┘
HITL

sleep "$DELAY"

# ═══════════════════════════════════════════════════════════════════════════════
step "2/7" "Kanał 1: REST API — Approve/Reject przez HTTP"
# ═══════════════════════════════════════════════════════════════════════════════

info "Dashboard API udostępnia endpointy do human approval:"
echo ""

echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat << 'API_DEMO'
# Uruchom dashboard (jeśli nie działa)
$ marksync dashboard --port 8888

# Sprawdź oczekujące zadania human
$ curl http://localhost:8888/api/pipeline/tasks
{
  "tasks": [
    {
      "id": "task-abc123",
      "run_id": "run-001",
      "step_name": "human_payment_approval",
      "prompt": "Order ORD-1234 ($2,500) requires approval",
      "task_type": "approval",
      "channel": "web",
      "status": "pending",
      "created_at": 1708300000
    }
  ]
}

# Approve
$ curl -X POST http://localhost:8888/api/pipeline/tasks/task-abc123 \
    -H 'Content-Type: application/json' \
    -d '{"action": "approve", "by": "manager@company.com"}'

# Reject z powodem
$ curl -X POST http://localhost:8888/api/pipeline/tasks/task-abc123 \
    -H 'Content-Type: application/json' \
    -d '{"action": "reject", "by": "cfo@company.com", "reason": "Budget exceeded"}'

# Status pipeline
$ curl http://localhost:8888/api/pipeline/runs/run-001
API_DEMO
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

sleep "$DELAY"

# ═══════════════════════════════════════════════════════════════════════════════
step "3/7" "Kanał 2: DSL Shell — Approve/Reject interaktywnie"
# ═══════════════════════════════════════════════════════════════════════════════

info "Z poziomu DSL shell można zarządzać human tasks:"
echo ""

echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat << 'SHELL_DEMO'
$ marksync shell

marksync> TASKS
  PENDING HUMAN TASKS:
  ┌──────────────────────────────────────────────────────────────┐
  │ ID          │ Step                    │ Age    │ Channel     │
  ├──────────────────────────────────────────────────────────────┤
  │ task-abc123 │ human_payment_approval  │ 2m 15s │ web         │
  │ task-def456 │ human_deploy_approval   │ 45s    │ web         │
  └──────────────────────────────────────────────────────────────┘

marksync> APPROVE task-abc123 --by admin
  ✓ Task task-abc123 approved by admin
  ✓ Pipeline run-001 continues → process_payment

marksync> REJECT task-def456 --reason "Not ready for prod"
  ✗ Task task-def456 rejected
  ✗ Pipeline run-002 stopped at deploy_approval

marksync> RUNS
  PIPELINE RUNS:
  ┌──────────────────────────────────────────────────────────────┐
  │ Run ID  │ Pipeline    │ Status    │ Step 4/7     │ Duration  │
  ├──────────────────────────────────────────────────────────────┤
  │ run-001 │ order-api   │ running   │ 5/7          │ 12.4s     │
  │ run-002 │ order-api   │ failed    │ 4/7 (reject) │ 8.1s      │
  └──────────────────────────────────────────────────────────────┘
SHELL_DEMO
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

sleep "$DELAY"

# ═══════════════════════════════════════════════════════════════════════════════
step "4/7" "Kanał 3: Webhook — External system notification"
# ═══════════════════════════════════════════════════════════════════════════════

info "Webhook pozwala na integrację z zewnętrznymi systemami:"
echo ""

echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat << 'WEBHOOK_DEMO'
# Konfiguracja webhook w DSL
marksync> WEBHOOK add https://slack.com/api/webhook --events human_task_created,pipeline_completed

# Albo w pipeline.yaml
pipeline:
  webhooks:
    - url: https://hooks.slack.com/services/T.../B.../xxx
      events: [human_task_created, pipeline_completed, pipeline_failed]
    - url: https://api.pagerduty.com/incidents
      events: [pipeline_failed]
      headers:
        Authorization: "Token token=xxx"

# Kiedy pipeline czeka na human:
# → POST https://slack.com/api/webhook
# {
#   "event": "human_task_created",
#   "task_id": "task-abc123",
#   "step": "human_payment_approval",
#   "prompt": "Order $2,500 requires approval",
#   "approve_url": "http://localhost:8888/api/pipeline/tasks/task-abc123",
#   "pipeline": "order-api",
#   "run_id": "run-001"
# }

# Slack/Teams/PagerDuty widzi przycisk "Approve" / "Reject"
# → User klika → POST do approve_url → pipeline kontynuuje
WEBHOOK_DEMO
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

sleep "$DELAY"

# ═══════════════════════════════════════════════════════════════════════════════
step "5/7" "Kanał 4: Email — Approval link w mailu"
# ═══════════════════════════════════════════════════════════════════════════════

info "Email channel — system wysyła mail z linkami approve/reject:"
echo ""

echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat << 'EMAIL_DEMO'
# W pipeline.yaml, step z channel: email
- name: human_payment_approval
  actor: human
  config:
    channel: email
    recipients:
      - manager@company.com
      - cfo@company.com
    timeout: 86400  # 24h
    subject: "[marksync] Order ORD-1234 ($2,500) requires approval"

# System wysyła email:
# ┌────────────────────────────────────────────────────────┐
# │ Subject: [marksync] Order ORD-1234 requires approval   │
# │ To: manager@company.com, cfo@company.com               │
# │                                                        │
# │ Pipeline: order-api (run-001)                          │
# │ Step: human_payment_approval                           │
# │ Order: ORD-1234, Total: $2,500.00                      │
# │                                                        │
# │ [✓ APPROVE]  [✗ REJECT]                               │
# │                                                        │
# │ Links:                                                 │
# │ Approve: http://dashboard:8888/approve/task-abc123     │
# │ Reject:  http://dashboard:8888/reject/task-abc123      │
# │                                                        │
# │ This link expires in 24 hours.                         │
# └────────────────────────────────────────────────────────┘
EMAIL_DEMO
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

sleep "$DELAY"

# ═══════════════════════════════════════════════════════════════════════════════
step "6/7" "Kanał 5: SSE (Server-Sent Events) — Live updates w przeglądarce"
# ═══════════════════════════════════════════════════════════════════════════════

info "Dashboard wysyła live updates przez SSE:"
echo ""

echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"
cat << 'SSE_DEMO'
# Subskrybuj SSE stream
$ curl -N http://localhost:8888/api/events

data: {"type": "connected", "ts": 1708300000}

data: {"type": "step_started", "step": "parse_order", "actor": "script"}
data: {"type": "step_completed", "step": "parse_order", "status": "pass", "ms": 12}

data: {"type": "step_started", "step": "check_inventory", "actor": "llm"}
data: {"type": "step_completed", "step": "check_inventory", "status": "pass", "ms": 850}

data: {"type": "step_started", "step": "fraud_detection", "actor": "script"}
data: {"type": "step_completed", "step": "fraud_detection", "status": "pass", "ms": 45}

data: {"type": "human_task_created", "task_id": "task-abc123", "step": "human_payment_approval"}
data: {"type": "step_blocked", "step": "human_payment_approval", "waiting_for": "human"}

  ... (pipeline czeka na human) ...

data: {"type": "human_task_resolved", "task_id": "task-abc123", "action": "approve", "by": "manager"}
data: {"type": "step_completed", "step": "human_payment_approval", "status": "pass"}

data: {"type": "step_started", "step": "process_payment", "actor": "script"}
data: {"type": "pipeline_completed", "run_id": "run-001", "status": "completed"}
SSE_DEMO
echo -e "${CYAN}──────────────────────────────────────────────────────────────────────────────${NC}"

sleep "$DELAY"

# ═══════════════════════════════════════════════════════════════════════════════
step "7/7" "Podsumowanie kanałów komunikacji"
# ═══════════════════════════════════════════════════════════════════════════════

cat << 'SUMMARY'

  ╔══════════════════════════════════════════════════════════════════════════╗
  ║  KANAŁ       │ KOMENDA                               │ KIEDY             ║
  ╠══════════════════════════════════════════════════════════════════════════╣
  ║  REST API    │ curl POST /api/pipeline/tasks/{id}    │ Automatyzacja     ║
  ║  DSL Shell   │ marksync> APPROVE task-id             │ Interaktywnie     ║
  ║  Webhook     │ Slack/Teams/PagerDuty callback        │ Powiadomienia     ║
  ║  Email       │ Link approve/reject w mailu           │ Async approval    ║
  ║  SSE         │ curl /api/events (live stream)        │ Monitoring        ║
  ║  Dashboard   │ http://localhost:8888 (klik)          │ Przeglądarka      ║
  ╚══════════════════════════════════════════════════════════════════════════╝

  Human-in-the-loop jest DOMYŚLNY:
  • Każdy nowy pipeline zaczyna od human: initial_approval
  • Deploy ZAWSZE wymaga human: deploy_approval
  • Możesz dodać actor: human na dowolnym kroku
  • Kanał komunikacji jest konfigurowalny per-step

SUMMARY

echo -e "${GREEN}${BOLD}Demo zakończone!${NC}\n"
