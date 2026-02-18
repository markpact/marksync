#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# DEMO: Contract Builder — Budowanie kontraktu z promptu
# ═══════════════════════════════════════════════════════════════════════════════
#
# Ten skrypt buduje REALNY kontrakt (README.md z blokami markpact:*)
# z jednozdaniowego promptu i pokazuje jak walidować proces
# niezależnie od aktora: human, llm, script (robot).
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Kolory
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
DELAY=${DEMO_DELAY:-1}

# Aktywuj venv
if [ -f ".venv/bin/activate" ]; then source .venv/bin/activate 2>/dev/null; fi

step() { echo -e "\n${BOLD}${CYAN}[$1]${NC} $2"; sleep "$DELAY"; }
info() { echo -e "  ${YELLOW}→${NC} $1"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║  DEMO: Contract Builder — Od Promptu do Walidowalnego Kontraktu             ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ═══════════════════════════════════════════════════════════════════════════════
step "1/6" "Prompt → Contract README.md"
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_DIR="$PROJECT_DIR/generated/demo-order-api"
mkdir -p "$DEMO_DIR"

info "Jednozdaniowy prompt:"
echo -e "  ${GREEN}'Build an order management REST API with human approval before payment'${NC}"
echo ""

info "System generuje README.md z blokami markpact:*"
cat > "$DEMO_DIR/README.md" << 'CONTRACT'
# Order Management API

REST API do zarządzania zamówieniami z human approval przed płatnością.

## Pipeline

```yaml markpact:orchestration
pipeline:
  name: order-api
  description: "Order management with human-in-the-loop payment approval"
  steps:
    - name: parse_order
      actor: script
      config:
        function: validate_order_schema
        description: "Validate order JSON against schema"

    - name: check_inventory
      actor: llm
      config:
        role: reviewer
        description: "AI checks inventory availability"

    - name: fraud_detection
      actor: script
      config:
        function: run_fraud_check
        description: "Automated fraud detection algorithm"

    - name: human_payment_approval
      actor: human
      config:
        description: "Manager approves payment > $1000"
        channel: web
        timeout: 7200
        condition: "order.total > 1000"

    - name: process_payment
      actor: script
      config:
        function: charge_payment
        description: "Process payment via Stripe"

    - name: notify_customer
      actor: llm
      config:
        role: editor
        description: "Generate personalized confirmation email"

    - name: deploy_update
      actor: llm
      config:
        role: deployer
        description: "Update order status in production DB"
```

## Dependencies

```json markpact:deps
{
  "runtime": "python:3.12",
  "packages": ["fastapi", "uvicorn", "pydantic", "stripe", "sqlalchemy"],
  "services": ["postgres:15", "redis:7"]
}
```

## Application Code

```python markpact:file=app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import time

app = FastAPI(title="Order Management API", version="1.0.0")

class OrderCreate(BaseModel):
    customer_id: str
    items: list[dict]
    total: float
    currency: str = "USD"

class Order(BaseModel):
    id: str
    customer_id: str
    items: list[dict]
    total: float
    status: str = "pending"
    requires_approval: bool = False
    approved_by: Optional[str] = None

orders_db: dict[str, Order] = {}

@app.post("/orders", response_model=Order)
def create_order(body: OrderCreate):
    order_id = f"ORD-{int(time.time())}"
    order = Order(
        id=order_id,
        customer_id=body.customer_id,
        items=body.items,
        total=body.total,
        requires_approval=body.total > 1000,
        status="pending_approval" if body.total > 1000 else "confirmed",
    )
    orders_db[order_id] = order
    return order

@app.post("/orders/{order_id}/approve")
def approve_order(order_id: str, by: str = "human"):
    if order_id not in orders_db:
        raise HTTPException(404, "Order not found")
    order = orders_db[order_id]
    order.status = "confirmed"
    order.approved_by = by
    return {"ok": True, "order": order}

@app.post("/orders/{order_id}/reject")
def reject_order(order_id: str, reason: str = ""):
    if order_id not in orders_db:
        raise HTTPException(404, "Order not found")
    order = orders_db[order_id]
    order.status = "rejected"
    return {"ok": True, "order": order, "reason": reason}

@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    if order_id not in orders_db:
        raise HTTPException(404, "Order not found")
    return orders_db[order_id]

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0", "orders_count": len(orders_db)}
```

## Run Command

```bash markpact:run
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Deploy Configuration

```yaml markpact:deploy
target: docker
pactown:
  name: order-api-ecosystem
  services:
    order-api:
      readme: ./README.md
      port: 8000
      health_check: /health
```

## State

```json markpact:state
{
  "phase": "init",
  "deploy_target": null,
  "health": null,
  "last_deploy": null,
  "success_count": 0,
  "error_count": 0,
  "pattern_id": null
}
```

## Log

```text markpact:log
[2025-02-18T23:45:00Z] CONTRACT_CREATED: prompt=Build an order management REST API with human approval
```
CONTRACT

ok "README.md wygenerowany: $DEMO_DIR/README.md"
ok "Bloki: orchestration, deps, file, run, deploy, state, log"
sleep "$DELAY"

# ═══════════════════════════════════════════════════════════════════════════════
step "2/6" "Walidacja kontraktu — Niezależna od aktora"
# ═══════════════════════════════════════════════════════════════════════════════

info "System parsuje README.md i waliduje każdy blok:"
echo ""

python3 << 'VALIDATE_PY'
import sys, os
sys.path.insert(0, os.getcwd())
from marksync.sync import BlockParser
from pathlib import Path

readme = Path("generated/demo-order-api/README.md")
if not readme.exists():
    print("  ✗ README.md nie znaleziony")
    sys.exit(1)

blocks = BlockParser.parse(readme.read_text("utf-8"))
print(f"  Znaleziono {len(blocks)} bloków markpact:")
print()

required = {"orchestration", "deps", "run", "deploy", "state", "log"}
found = set()

for b in blocks:
    kind = b.kind
    found.add(kind)
    status = "\033[0;32m✓\033[0m" if kind in required else "\033[0;36m·\033[0m"
    extra = f" path={b.path}" if b.path else ""
    print(f"  {status} markpact:{kind}{extra}  ({len(b.content)} bytes, sha256={b.sha256[:12]}...)")

print()
missing = required - found
if missing:
    print(f"  \033[0;31m✗ Brakuje bloków: {', '.join(missing)}\033[0m")
else:
    print(f"  \033[0;32m✓ Wszystkie wymagane bloki obecne!\033[0m")

# Waliduj pipeline steps
import yaml
for b in blocks:
    if b.kind == "orchestration":
        data = yaml.safe_load(b.content)
        steps = data.get("pipeline", {}).get("steps", [])
        print(f"\n  Pipeline: {len(steps)} kroków")
        for s in steps:
            actor = s.get("actor", "?")
            icon = {"human": "👤", "llm": "🤖", "script": "⚙️"}.get(actor, "?")
            name = s.get("name", "?")
            print(f"    {icon} {name} (actor: {actor})")
VALIDATE_PY

sleep "$DELAY"

# ═══════════════════════════════════════════════════════════════════════════════
step "3/6" "Actor Types — Human / LLM / Script"
# ═══════════════════════════════════════════════════════════════════════════════

info "Każdy krok w pipeline ma actor type:"
echo ""
echo -e "  ${BOLD}actor: script${NC}  ⚙️  — Deterministyczny kod (walidacja, algorytm)"
echo "    • Nie wymaga interakcji"
echo "    • Wynik: PASS/FAIL natychmiast"
echo "    • Przykład: validate_order_schema, run_fraud_check"
echo ""
echo -e "  ${BOLD}actor: llm${NC}     🤖 — AI processing (Ollama/OpenRouter)"
echo "    • Automatyczny, ale niedeterministyczny"
echo "    • Wynik: wygenerowany tekst/kod"
echo "    • Przykład: check_inventory, generate email"
echo ""
echo -e "  ${BOLD}actor: human${NC}   👤 — Czeka na ludzką decyzję"
echo "    • Pipeline BLOKUJE się (status: blocked)"
echo "    • Kanały: web, email, chat, webhook"
echo "    • Timeout → automatyczny reject"
echo "    • Przykład: approve payment > \$1000"
echo ""

info "Walidacja jest TAKA SAMA niezależnie od aktora:"
echo "    Każdy step → StepResult { status, input_data, output_data, error }"
echo "    Kontrakt nie rozróżnia KTO wykonał — tylko CZY spełnione"

sleep "$DELAY"

# ═══════════════════════════════════════════════════════════════════════════════
step "4/6" "Symulacja pipeline — Krok po kroku"
# ═══════════════════════════════════════════════════════════════════════════════

info "Symulacja wykonania pipeline (bez LLM):"
echo ""

python3 << 'SIMULATE_PY'
import time, json

steps = [
    {"name": "parse_order",           "actor": "script", "result": "pass"},
    {"name": "check_inventory",       "actor": "llm",    "result": "pass"},
    {"name": "fraud_detection",       "actor": "script", "result": "pass"},
    {"name": "human_payment_approval","actor": "human",  "result": "blocked"},
    {"name": "process_payment",       "actor": "script", "result": "pending"},
    {"name": "notify_customer",       "actor": "llm",    "result": "pending"},
    {"name": "deploy_update",         "actor": "llm",    "result": "pending"},
]

icons = {"script": "⚙️", "llm": "🤖", "human": "👤"}
colors = {"pass": "\033[0;32m", "blocked": "\033[1;33m", "pending": "\033[0;36m", "fail": "\033[0;31m"}
nc = "\033[0m"

for i, s in enumerate(steps):
    icon = icons[s["actor"]]
    color = colors[s["result"]]
    status = s["result"].upper()
    
    if s["result"] == "blocked":
        print(f"  {icon} Step {i+1}: {s['name']}")
        print(f"     {color}⏸ BLOCKED — Czeka na human approval{nc}")
        print(f"     Kanał: web | Timeout: 7200s")
        print(f"     → POST /api/pipeline/tasks/{{task_id}} {{\"action\": \"approve\"}}")
        print()
        
        time.sleep(0.5)
        print(f"     \033[0;32m✓ APPROVED by manager@company.com (po 45s){nc}")
        s["result"] = "pass"
        status = "APPROVED"
    
    if s["result"] == "pending":
        time.sleep(0.3)
        s["result"] = "pass"
        status = "PASS"
    
    color_final = "\033[0;32m" if s["result"] == "pass" else colors.get(s["result"], nc)
    if s["actor"] != "human":
        print(f"  {icon} Step {i+1}: {s['name']} — {color_final}{status}{nc}")
    
    time.sleep(0.2)

print()
print(f"  \033[0;32m═══ Pipeline COMPLETED ═══\033[0m")
print(f"  7/7 steps passed | 1 human approval | 0 errors")
SIMULATE_PY

sleep "$DELAY"

# ═══════════════════════════════════════════════════════════════════════════════
step "5/6" "Contract State — Aktualizacja po wykonaniu"
# ═══════════════════════════════════════════════════════════════════════════════

info "Po zakończeniu pipeline, markpact:state zostaje zaktualizowany:"
echo ""

python3 << 'UPDATE_STATE'
import json, time

state = {
    "phase": "deployed",
    "deploy_target": "docker",
    "health": "ok",
    "last_deploy": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "success_count": 1,
    "error_count": 0,
    "pattern_id": "api-rest-orders",
    "pipeline_run": {
        "id": "run-001",
        "steps_total": 7,
        "steps_passed": 7,
        "human_approvals": 1,
        "duration_ms": 12450,
        "actors": {"script": 3, "llm": 3, "human": 1}
    }
}

print(json.dumps(state, indent=2))
UPDATE_STATE

sleep "$DELAY"

# ═══════════════════════════════════════════════════════════════════════════════
step "6/6" "Wygenerowane pliki"
# ═══════════════════════════════════════════════════════════════════════════════

info "Kontrakt i wszystkie dane zapisane w:"
echo ""
echo "  $DEMO_DIR/"
echo "  └── README.md  (kontrakt z blokami markpact:*)"
echo ""
info "Bloki w kontrakcie:"
echo "  • markpact:orchestration — pipeline z krokami (human/llm/script)"
echo "  • markpact:deps          — zależności runtime"
echo "  • markpact:file=app/main.py — kod aplikacji"
echo "  • markpact:run           — komenda uruchomienia"
echo "  • markpact:deploy        — konfiguracja deployu"
echo "  • markpact:state         — aktualny stan procesu"
echo "  • markpact:log           — historia zdarzeń"
echo ""
info "Aby zobaczyć w przeglądarce:"
echo -e "  ${CYAN}./demos/demo_browser.sh${NC}"

echo -e "\n${GREEN}${BOLD}Demo zakończone!${NC}\n"
