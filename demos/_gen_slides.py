#!/usr/bin/env python3
"""Generate split-screen HTML slideshow for marksync demo.

LEFT panel  = Live README.md (actual block state at each step)
RIGHT panel = Expectations + validation checks (pass/fail/wait)
"""
import json
import sys
from pathlib import Path

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("generated/slides")
out.mkdir(parents=True, exist_ok=True)

# ---- README block fragments ------------------------------------------------

HEADER = "# Order Management API\n\nREST API z human approval przed platnoscia."

ORCH = (
    "```yaml markpact:orchestration\n"
    "pipeline:\n"
    "  name: order-api\n"
    "  steps:\n"
    "    - name: parse_order\n"
    "      actor: script\n"
    "    - name: check_inventory\n"
    "      actor: llm\n"
    "    - name: fraud_detection\n"
    "      actor: script\n"
    "    - name: human_payment_approval\n"
    "      actor: human\n"
    "      config: {channel: web, timeout: 7200}\n"
    "    - name: process_payment\n"
    "      actor: script\n"
    "    - name: deploy_update\n"
    "      actor: llm\n"
    "```"
)

DEPS = '```json markpact:deps\n{"runtime":"python:3.12","packages":["fastapi","uvicorn","pydantic"]}\n```'

FILE = (
    '```python markpact:file=app/main.py\n'
    'from fastapi import FastAPI\n'
    'app = FastAPI(title="Order API")\n'
    '\n'
    '@app.post("/orders")\n'
    'def create_order(body: dict):\n'
    '    return {"id": "ORD-001", "status": "pending"}\n'
    '\n'
    '@app.get("/health")\n'
    'def health():\n'
    '    return {"status": "ok"}\n'
    '```'
)

RUN = "```bash markpact:run\nuvicorn app.main:app --host 0.0.0.0 --port 8000\n```"

DEPLOY = (
    "```yaml markpact:deploy\n"
    "target: docker\n"
    "pactown:\n"
    "  name: order-api\n"
    "  services:\n"
    "    api: {port: 8000, health_check: /health}\n"
    "```"
)

CORE = [HEADER, ORCH, DEPS, FILE, RUN, DEPLOY]


def state_block(phase, health="null", sc=0, ec=0):
    h = f'"{health}"' if health != "null" else "null"
    return f'{{"phase":"{phase}","health":{h},"success_count":{sc},"error_count":{ec}}}'


def st(phase, health="null", sc=0, ec=0):
    return "```json markpact:state\n" + state_block(phase, health, sc, ec) + "\n```"


def lg(entries):
    return "```text markpact:log\n" + "\n".join(entries) + "\n```"


LOG = {
    "init": ["[T+0s] CONTRACT_CREATED"],
    "running": ["[T+0s] CONTRACT_CREATED", "[T+1s] PIPELINE_STARTED"],
    "s1": ["[T+0s] CONTRACT_CREATED", "[T+1s] PIPELINE_STARTED", "[T+1s] STEP_OK: parse_order (12ms)"],
    "s2": ["[T+0s] CONTRACT_CREATED", "[T+1s] PIPELINE_STARTED", "[T+1s] STEP_OK: parse_order", "[T+2s] STEP_OK: check_inventory (850ms)"],
    "s3": ["[T+0s] CONTRACT_CREATED", "[T+1s] PIPELINE_STARTED", "[T+1s] STEP_OK: parse_order", "[T+2s] STEP_OK: check_inventory", "[T+2s] STEP_OK: fraud_detection (45ms)"],
    "blocked": ["[T+0s] CONTRACT_CREATED", "[T+1s] PIPELINE_STARTED", "[T+1s] STEP_OK: parse_order", "[T+2s] STEP_OK: check_inventory", "[T+2s] STEP_OK: fraud_detection", "[T+3s] STEP_BLOCKED: human_payment_approval"],
    "approved": ["[T+0s] CONTRACT_CREATED", "[T+1s] PIPELINE_STARTED", "[T+1s] STEP_OK: parse_order", "[T+2s] STEP_OK: check_inventory", "[T+2s] STEP_OK: fraud_detection", "[T+3s] STEP_BLOCKED: human_payment_approval", "[T+48s] STEP_OK: human_payment_approval (APPROVED)"],
    "deployed": ["[T+0s] CONTRACT_CREATED", "[T+1s] PIPELINE_STARTED", "[T+1s] STEP_OK: parse_order", "[T+2s] STEP_OK: check_inventory", "[T+2s] STEP_OK: fraud_detection", "[T+3s] STEP_BLOCKED: human_payment_approval", "[T+48s] STEP_OK: human_payment_approval", "[T+49s] STEP_OK: process_payment", "[T+50s] STEP_OK: deploy_update", "[T+50s] PIPELINE_COMPLETED: 6/6"],
}

RS = {
    "readme_initial":  "\n\n".join(CORE + [st("init"), lg(LOG["init"])]),
    "readme_running":  "\n\n".join(CORE + [st("running"), lg(LOG["running"])]),
    "readme_step1":    "\n\n".join(CORE + [st("running"), lg(LOG["s1"])]),
    "readme_step2":    "\n\n".join(CORE + [st("running"), lg(LOG["s2"])]),
    "readme_step3":    "\n\n".join(CORE + [st("running"), lg(LOG["s3"])]),
    "readme_blocked":  "\n\n".join(CORE + [st("blocked", "waiting_human"), lg(LOG["blocked"])]),
    "readme_approved": "\n\n".join(CORE + [st("running"), lg(LOG["approved"])]),
    "readme_deployed": "\n\n".join(CORE + [st("deployed", "ok", 1, 0), lg(LOG["deployed"])]),
}

# ---- Slide definitions -----------------------------------------------------

def chk(label, status="pass", detail=""):
    return {"label": label, "status": status, "detail": detail}


slides = [
    # 0: Title
    {"title": "marksync", "subtitle": "Contract-Based AI-Human-Algorithm Conversation<br>for Live Process Deployment &amp; Control with Self-Learning",
     "layout": "title", "idx": 0, "left": "", "right": "", "checks": []},

    # 1: Prompt
    {"title": "1. Prompt", "subtitle": "Jedno zdanie uruchamia caly proces", "layout": "split",
     "left_label": "INPUT: Prompt uzytkownika", "left": "prompt",
     "right_label": "OCZEKIWANIE: Co system powinien zrobic",
     "right": "<div class='expect'><h3>System powinien:</h3><ol>"
              "<li>Sparsowac intencje z promptu</li>"
              "<li>Zidentyfikowac typ uslugi: <code>REST API</code></li>"
              "<li>Wykryc wymaganie: <code>human approval</code></li>"
              "<li>Wygenerowac README.md z blokami markpact:*</li>"
              "<li>Ustawic pipeline: script + llm + human</li></ol></div>",
     "checks": [
         chk("Prompt sparsowany", detail="IntentParser.parse() -> service_type=api"),
         chk("Human-in-the-loop wykryty", detail="'human approval' -> actor: human"),
         chk("Kontrakt wygenerowany", detail="README.md z 7 blokami markpact:*"),
     ]},

    # 2: Contract
    {"title": "2. Kontrakt README.md", "subtitle": "Markdown = zrodlo prawdy", "layout": "split",
     "left_label": "README.md -- aktualny stan", "left": "readme_initial", "left_highlight": "all",
     "right_label": "OCZEKIWANIE: Wymagane bloki",
     "right": "<div class='expect'><h3>README.md musi zawierac:</h3><div class='block-checklist'>"
              "<div class='bc-item pass'><span class='bc-icon'>V</span> <code>markpact:orchestration</code></div>"
              "<div class='bc-item pass'><span class='bc-icon'>V</span> <code>markpact:deps</code></div>"
              "<div class='bc-item pass'><span class='bc-icon'>V</span> <code>markpact:file=app/main.py</code></div>"
              "<div class='bc-item pass'><span class='bc-icon'>V</span> <code>markpact:run</code></div>"
              "<div class='bc-item pass'><span class='bc-icon'>V</span> <code>markpact:deploy</code></div>"
              "<div class='bc-item pass'><span class='bc-icon'>V</span> <code>markpact:state</code></div>"
              "<div class='bc-item pass'><span class='bc-icon'>V</span> <code>markpact:log</code></div>"
              "</div><div class='validation-box pass'>Walidacja: 7/7 blokow V</div></div>",
     "checks": [
         chk("BlockParser.parse() -> 7 blokow", detail="orchestration, deps, file, run, deploy, state, log"),
         chk("SHA-256 hash kazdego bloku", detail="Integralnosc zweryfikowana"),
         chk("Pipeline ma 6 krokow", detail="3x script + 2x llm + 1x human"),
         chk("markpact:state.phase == init", detail="Stan poczatkowy OK"),
     ]},

    # 3: Pipeline Start
    {"title": "3. Pipeline Start", "subtitle": "PipelineEngine czyta markpact:orchestration", "layout": "split",
     "left_label": "README.md -- markpact:state zmieniony", "left": "readme_running", "left_highlight": "state",
     "right_label": "OCZEKIWANIE: Engine uruchomiony",
     "right": "<div class='expect'><h3>Co sie dzieje:</h3><ol>"
              "<li>PipelineEngine parsuje <code>markpact:orchestration</code></li>"
              "<li>Tworzy <code>PipelineRun</code> z 6 krokami</li>"
              "<li><code>markpact:state</code>: init -> running</li>"
              "<li><code>markpact:log</code> otrzymuje wpis</li></ol>"
              "<div class='state-change'><div class='state-old'>phase: init</div>"
              "<div class='state-arrow'>-></div><div class='state-new'>phase: running</div></div></div>",
     "checks": [
         chk("PipelineRun utworzony", detail="run_id=run-001, 6 steps"),
         chk("markpact:state zaktualizowany", detail="phase: init -> running"),
         chk("markpact:log wpis dodany", detail="PIPELINE_STARTED: order-api"),
     ]},

    # 4: script step
    {"title": "4. parse_order", "subtitle": "actor: script -- Walidacja schematu", "layout": "split",
     "left_label": "README.md -- markpact:log +1", "left": "readme_step1", "left_highlight": "log",
     "right_label": "OCZEKIWANIE: Skrypt walidacyjny",
     "right": "<div class='expect'><h3>actor: script</h3>"
              "<p>Deterministyczny kod -- ten sam input = ten sam output.</p>"
              "<div class='step-detail'>"
              "<div class='sd-row'><span class='sd-label'>Funkcja:</span> <code>validate_order_schema()</code></div>"
              "<div class='sd-row'><span class='sd-label'>Input:</span> Order JSON</div>"
              "<div class='sd-row'><span class='sd-label'>Output:</span> PASS / FAIL</div>"
              "<div class='sd-row'><span class='sd-label'>Czas:</span> 12ms</div></div>"
              "<h3 style='margin-top:16px'>Czy skrypt dziala poprawnie?</h3>"
              "<p>Sprawdzamy: schema valid, required fields, types correct</p></div>",
     "checks": [
         chk("validate_order_schema() wykonany", detail="12ms, exit code 0"),
         chk("Schema poprawna", detail="customer_id, items, total -- present"),
         chk("Typy danych prawidlowe", detail="total: float, items: list"),
         chk("markpact:log zaktualizowany", detail="STEP_COMPLETED: parse_order"),
     ]},

    # 5: llm step
    {"title": "5. check_inventory", "subtitle": "actor: llm -- AI sprawdza magazyn", "layout": "split",
     "left_label": "README.md -- markpact:log +1", "left": "readme_step2", "left_highlight": "log",
     "right_label": "OCZEKIWANIE: LLM poprawnie generuje",
     "right": "<div class='expect'><h3>actor: llm</h3>"
              "<p>AI (Ollama/OpenRouter) analizuje zamowienie.</p>"
              "<div class='step-detail'>"
              "<div class='sd-row'><span class='sd-label'>Model:</span> <code>qwen2.5-coder:7b</code></div>"
              "<div class='sd-row'><span class='sd-label'>Input:</span> Order items + inventory</div>"
              "<div class='sd-row'><span class='sd-label'>Output:</span> Availability check</div>"
              "<div class='sd-row'><span class='sd-label'>Czas:</span> 850ms</div></div>"
              "<h3 style='margin-top:16px'>Czy LLM poprawnie generuje?</h3>"
              "<p>Sprawdzamy: valid JSON, items checked, no hallucinations</p></div>",
     "checks": [
         chk("LLM odpowiedzial", detail="850ms, model=qwen2.5-coder:7b"),
         chk("Response: valid JSON", detail="{all_available: true, items_checked: 3}"),
         chk("Wszystkie produkty sprawdzone", detail="3/3 items verified"),
         chk("Brak hallucinations", detail="Output matches inventory DB"),
     ]},

    # 6: script fraud
    {"title": "6. fraud_detection", "subtitle": "actor: script -- Algorytm fraud", "layout": "split",
     "left_label": "README.md -- markpact:log +1", "left": "readme_step3", "left_highlight": "log",
     "right_label": "OCZEKIWANIE: Fraud check",
     "right": "<div class='expect'><h3>actor: script</h3>"
              "<p>Deterministyczny algorytm -- wzorce oszustw.</p>"
              "<div class='step-detail'>"
              "<div class='sd-row'><span class='sd-label'>Funkcja:</span> <code>run_fraud_check()</code></div>"
              "<div class='sd-row'><span class='sd-label'>Sprawdza:</span> IP, historia, kwota</div>"
              "<div class='sd-row'><span class='sd-label'>Risk score:</span> 0.12 (low)</div>"
              "<div class='sd-row'><span class='sd-label'>Czas:</span> 45ms</div></div></div>",
     "checks": [
         chk("run_fraud_check() wykonany", detail="45ms, risk_score=0.12"),
         chk("Risk score < threshold (0.7)", detail="0.12 < 0.70 -> SAFE"),
         chk("Klient nie na blacklist", detail="customer_id not in blacklist"),
     ]},

    # 7: human BLOCKED
    {"title": "7. human_payment_approval", "subtitle": "actor: human -- PIPELINE ZABLOKOWANY", "layout": "split",
     "left_label": "README.md -- markpact:state = blocked", "left": "readme_blocked", "left_highlight": "state",
     "right_label": "OCZEKIWANIE: Decyzja czlowieka",
     "right": "<div class='expect blocked-expect'><h3>actor: human -- BLOCKED</h3>"
              "<p>Pipeline <strong>CZEKA</strong>. Zamowienie $2,500 > limit $1,000.</p>"
              "<div class='step-detail'>"
              "<div class='sd-row'><span class='sd-label'>HumanTask:</span> <code>task-abc123</code></div>"
              "<div class='sd-row'><span class='sd-label'>Kanal:</span> web (dashboard)</div>"
              "<div class='sd-row'><span class='sd-label'>Timeout:</span> 7200s (2h)</div>"
              "<div class='sd-row'><span class='sd-label'>Powiadomienie:</span> webhook -> Slack</div></div>"
              "<h3 style='margin-top:16px'>Kanaly komunikacji:</h3>"
              "<div class='channels-grid'>"
              "<div class='ch'>Dashboard</div><div class='ch'>Email</div>"
              "<div class='ch'>Webhook</div><div class='ch'>Shell</div></div>"
              "<div class='api-box'>POST /api/pipeline/tasks/task-abc123<br>{action: approve, by: manager@co.com}</div></div>",
     "checks": [
         chk("HumanTask utworzony", detail="task-abc123, channel=web"),
         chk("Webhook wyslany", detail="POST slack -> 200 OK"),
         chk("markpact:state = blocked", detail="phase: running -> blocked"),
         chk("Oczekiwanie na human...", "wait", detail="timeout za 7155s"),
     ]},

    # 8: Human approves
    {"title": "8. Human -> Approve", "subtitle": "Manager zatwierdza -- pipeline kontynuuje", "layout": "split",
     "left_label": "README.md -- markpact:state = running", "left": "readme_approved", "left_highlight": "state",
     "right_label": "Czlowiek podjal decyzje",
     "right": "<div class='expect'><h3>Approval received</h3>"
              "<div class='approval-card'>"
              "<div class='ac-row'><span class='ac-label'>Decyzja:</span> <span class='ac-val approve'>APPROVED</span></div>"
              "<div class='ac-row'><span class='ac-label'>Przez:</span> manager@company.com</div>"
              "<div class='ac-row'><span class='ac-label'>Czas:</span> 45 sekund</div>"
              "<div class='ac-row'><span class='ac-label'>Kanal:</span> Dashboard (web)</div></div>"
              "<h3 style='margin-top:16px'>Zmiana w README.md:</h3>"
              "<div class='state-change'><div class='state-old'>phase: blocked</div>"
              "<div class='state-arrow'>-></div><div class='state-new'>phase: running</div></div>"
              "<p style='margin-top:12px'>Pipeline kontynuuje automatycznie.</p></div>",
     "checks": [
         chk("Human approval received", detail="APPROVED by manager@company.com (45s)"),
         chk("HumanTask resolved", detail="task-abc123 status=resolved"),
         chk("Pipeline wznowiony", detail="status: blocked -> running"),
         chk("markpact:state zaktualizowany", detail="phase: blocked -> running"),
     ]},

    # 9: Deploy
    {"title": "9. Deploy -> Production", "subtitle": "Ostatnie kroki + deployment", "layout": "split",
     "left_label": "README.md -- markpact:state = deployed", "left": "readme_deployed", "left_highlight": "state",
     "right_label": "OCZEKIWANIE: Deploy poprawny",
     "right": "<div class='expect'><h3>Pozostale kroki:</h3>"
              "<div class='mini-steps'>"
              "<div class='ms pass'>process_payment -- <strong>PASS</strong> (320ms)</div>"
              "<div class='ms pass'>deploy_update -- <strong>PASS</strong> (1200ms)</div></div>"
              "<div class='validation-box pass' style='margin-top:16px'>Pipeline COMPLETED -- 6/6 steps passed</div>"
              "<h3 style='margin-top:16px'>Finalny stan README.md:</h3>"
              "<div class='state-change'><div class='state-old'>phase: running</div>"
              "<div class='state-arrow'>-></div><div class='state-new'>phase: deployed</div></div></div>",
     "checks": [
         chk("process_payment -> PASS", detail="320ms, transaction_id=TXN-001"),
         chk("deploy_update -> PASS", detail="1200ms, container started"),
         chk("Healthcheck /health -> 200 OK", detail="{status:ok}"),
         chk("markpact:state.phase = deployed", detail="success_count: 0 -> 1"),
         chk("markpact:log -- 10 wpisow", detail="Pelna historia pipeline"),
     ]},

    # 10: Learning
    {"title": "10. Self-Learning", "subtitle": "Pattern zapisany -> kolejny projekt lepszy", "layout": "split",
     "left_label": "README.md -- finalny stan", "left": "readme_deployed",
     "right_label": "Ewolucja na bazie danych",
     "right": "<div class='expect'><h3>Pattern Library -- wzorzec:</h3>"
              "<div class='pattern-card'>"
              "<div class='pf'><span>id:</span> <strong>api-rest-orders</strong></div>"
              "<div class='pf'><span>keywords:</span> rest, api, orders, payment</div>"
              "<div class='pf'><span>success_rate:</span> <strong class='rate-good'>1.00</strong></div>"
              "<div class='pf'><span>usage_count:</span> 1</div></div>"
              "<h3 style='margin-top:16px'>Nastepny prompt:</h3>"
              "<p>System znajdzie ten pattern i uzyje jako template. Rate rosnie z kazdym sukcesem.</p></div>",
     "checks": [
         chk("PatternLibrary.save_from_contract()", detail="Pattern api-rest-orders zapisany"),
         chk("success_rate = 1.00", detail="Pierwszy run -> 100%"),
         chk("Pattern reusable", detail="Kolejny 'REST API + orders' -> match"),
     ]},

    # 11: Summary
    {"title": "Podsumowanie", "subtitle": "Caly przeplyw w jednym README.md",
     "layout": "title", "idx": 11, "left": "", "right": "", "checks": []},
]

# ---- CSS --------------------------------------------------------------------

CSS = (Path(__file__).parent / "_slides.css").read_text("utf-8") if (Path(__file__).parent / "_slides.css").exists() else """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#0a0a1a;color:#e2e8f0;overflow:hidden;height:100vh}
.slide{display:none;height:100vh;flex-direction:column;padding:12px 20px}.slide.active{display:flex}
.slide-header{display:flex;align-items:baseline;gap:12px;margin-bottom:8px;flex-shrink:0}
.slide-header h2{font-size:24px;color:#f1f5f9}.slide-header .sub{font-size:14px;color:#94a3b8}
.slide-header .sub code{background:rgba(59,130,246,.15);padding:1px 6px;border-radius:3px;color:#93c5fd;font-size:13px}
.split{display:grid;grid-template-columns:1fr 1fr;gap:12px;flex:1;min-height:0}
.panel{display:flex;flex-direction:column;min-height:0;border:1px solid #1f2937;border-radius:8px;overflow:hidden}
.panel-label{padding:8px 12px;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;flex-shrink:0;border-bottom:1px solid #1f2937}
.panel-left .panel-label{background:#0c1425;color:#60a5fa}
.panel-right .panel-label{background:#1a0f25;color:#a78bfa}
.panel-body{flex:1;overflow-y:auto;padding:12px;font-size:13px;line-height:1.6}
.panel-left .panel-body{background:#0f172a;font-family:'JetBrains Mono',Consolas,monospace;white-space:pre-wrap;font-size:12px;line-height:1.5}
.panel-right .panel-body{background:#111827}
.md-h{color:#38bdf8;font-weight:700}.md-fence{color:#475569}.md-kind{color:#c084fc;font-weight:600}
.md-human{color:#fbbf24;font-weight:600}.md-llm{color:#60a5fa}.md-script{color:#34d399}
.hl{background:rgba(59,130,246,.12);border-left:3px solid #3b82f6;margin:0 -12px;padding:2px 12px;animation:pulse 2s ease-in-out}
@keyframes pulse{0%,100%{background:rgba(59,130,246,.12)}50%{background:rgba(59,130,246,.25)}}
.hl-warn{border-left-color:#f59e0b;background:rgba(245,158,11,.1)}
.hl-ok{border-left-color:#10b981;background:rgba(16,185,129,.1)}
.expect h3{color:#c4b5fd;font-size:15px;margin:0 0 8px}.expect p,.expect li{color:#cbd5e1;font-size:14px;line-height:1.6}
.expect ol{padding-left:20px;margin-bottom:12px}.expect code{background:rgba(59,130,246,.12);padding:1px 5px;border-radius:3px;color:#93c5fd;font-size:12px}
.checks{flex-shrink:0;border-top:1px solid #1f2937;padding:8px 12px;background:#0a0f1a}
.checks-title{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#64748b;margin-bottom:6px}
.chk{display:flex;align-items:flex-start;gap:8px;padding:3px 0;font-size:13px}
.chk-icon{width:18px;text-align:center;flex-shrink:0;font-weight:700}
.chk-icon.pass{color:#34d399}.chk-icon.fail{color:#ef4444}.chk-icon.wait{color:#fbbf24}
.chk-label{color:#e2e8f0}.chk-detail{color:#64748b;font-size:11px;margin-left:26px}
.state-change{display:flex;align-items:center;gap:10px;margin:10px 0;padding:10px;background:rgba(0,0,0,.2);border-radius:8px}
.state-old{background:#1e293b;padding:4px 10px;border-radius:4px;color:#f87171;font-family:monospace;font-size:13px;text-decoration:line-through}
.state-arrow{color:#64748b;font-size:20px}.state-new{background:#064e3b;padding:4px 10px;border-radius:4px;color:#34d399;font-family:monospace;font-size:13px;font-weight:600}
.block-checklist{margin:8px 0}.bc-item{padding:4px 0;font-size:13px;display:flex;align-items:center;gap:6px}
.bc-item.pass .bc-icon{color:#34d399}.bc-item code{font-size:12px}
.validation-box{padding:10px;border-radius:8px;font-weight:600;text-align:center;font-size:14px;margin-top:8px}
.validation-box.pass{background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.3);color:#34d399}
.step-detail{background:rgba(0,0,0,.2);border-radius:8px;padding:10px;margin:8px 0}
.sd-row{display:flex;gap:8px;padding:2px 0;font-size:13px}.sd-label{color:#94a3b8;min-width:80px}
.channels-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:8px 0}
.ch{background:#1e293b;border:1px solid #334155;border-radius:6px;padding:8px;text-align:center;font-size:13px}
.api-box{background:#0f172a;border:1px solid #1e3a5f;border-radius:6px;padding:10px;font-family:monospace;font-size:12px;color:#93c5fd;margin-top:10px}
.blocked-expect{border:1px solid rgba(245,158,11,.3);border-radius:8px;padding:12px;background:rgba(245,158,11,.03)}
.approval-card{background:rgba(16,185,129,.05);border:1px solid rgba(16,185,129,.2);border-radius:8px;padding:12px;margin:8px 0}
.ac-row{display:flex;gap:8px;padding:2px 0;font-size:14px}.ac-label{color:#94a3b8;min-width:100px}
.ac-val{color:#e2e8f0}.ac-val.approve{color:#34d399;font-weight:700}
.mini-steps{display:flex;flex-direction:column;gap:6px}.ms{padding:8px 12px;border-radius:6px;font-size:14px}
.ms.pass{background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);color:#34d399}
.pattern-card{background:rgba(99,102,241,.05);border:1px solid rgba(99,102,241,.2);border-radius:8px;padding:12px;margin:8px 0}
.pf{display:flex;gap:8px;padding:3px 0;font-size:13px}.pf span{color:#94a3b8;min-width:100px}.rate-good{color:#34d399}
.prompt-input{font-size:22px;color:#f1f5f9;font-style:italic;padding:30px;text-align:center;background:linear-gradient(135deg,#1e293b,#0f172a);border:2px solid #334155;border-radius:12px;margin:16px 0}
.progress{position:fixed;top:0;left:0;height:3px;background:#3b82f6;transition:width .4s;z-index:100}
.nav{position:fixed;bottom:12px;left:50%;transform:translateX(-50%);display:flex;gap:8px;z-index:100;align-items:center}
.nav button{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);color:#e2e8f0;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px}
.nav button:hover{background:rgba(59,130,246,.25);border-color:#3b82f6}
.nav .ctr{color:#64748b;font-size:13px;min-width:50px;text-align:center}
.nav .auto.on{background:rgba(59,130,246,.3);border-color:#3b82f6}
.dots{position:fixed;bottom:48px;left:50%;transform:translateX(-50%);display:flex;gap:5px;z-index:100}
.dot{width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,.12);cursor:pointer;transition:.3s}
.dot.a{background:#3b82f6;transform:scale(1.4)}.dot.v{background:rgba(59,130,246,.4)}
.title-slide{display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;flex:1}
.title-slide h1{font-size:48px;background:linear-gradient(135deg,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.title-slide .ts{font-size:18px;color:#94a3b8;max-width:700px;margin:12px 0 24px;line-height:1.6}
.summary-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:20px;max-width:800px}
.sg-item{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:16px;text-align:center}
.sg-item .ic{font-size:30px;margin-bottom:4px}.sg-item .vl{font-size:18px;font-weight:600;color:#f1f5f9}
.sg-item .lb{font-size:12px;color:#94a3b8;margin-top:2px}
.final-msg{font-size:22px;font-weight:700;margin-top:20px;background:linear-gradient(135deg,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
"""

# ---- JavaScript -------------------------------------------------------------

JS_TEMPLATE = r"""
const S=%SLIDES%;
const RS=%RS%;
let cur=0,auto=false,timer=null;const vis=new Set([0]);
function render(){const r=document.getElementById('root'),d=document.getElementById('dots');r.innerHTML='';d.innerHTML='';
S.forEach((s,i)=>{const dot=document.createElement('div');dot.className='dot'+(i===0?' a':'');dot.onclick=()=>go(i);d.appendChild(dot);
const sl=document.createElement('div');sl.className='slide'+(i===0?' active':'');sl.id='s'+i;sl.innerHTML=bld(s,i);r.appendChild(sl);});upd();}
function bld(s,i){
if(s.layout==='title'){
if(i===0) return '<div class="title-slide"><h1>'+s.title+'</h1><div class="ts">'+s.subtitle+'</div><div style="color:#64748b;font-size:13px">Arrow keys to navigate | Space = auto-play</div></div>';
return '<div class="title-slide"><h2 style="font-size:32px;color:#f1f5f9">'+s.title+'</h2><div class="ts">'+s.subtitle+'</div><div class="summary-grid"><div class="sg-item"><div class="ic">1</div><div class="vl">prompt</div><div class="lb">Wejscie</div></div><div class="sg-item"><div class="ic">1</div><div class="vl">README.md</div><div class="lb">Kontrakt</div></div><div class="sg-item"><div class="ic">7</div><div class="vl">blokow</div><div class="lb">markpact:*</div></div><div class="sg-item"><div class="ic">3</div><div class="vl">script</div><div class="lb">Deterministyczne</div></div><div class="sg-item"><div class="ic">2</div><div class="vl">llm</div><div class="lb">AI processing</div></div><div class="sg-item"><div class="ic">1</div><div class="vl">human</div><div class="lb">Approval</div></div></div><div class="final-msg">Jeden plik. Jeden kontrakt. Wszystko walidowalne.</div></div>';}
let h='<div class="slide-header"><h2>'+s.title+'</h2><span class="sub">'+(s.subtitle||'')+'</span></div><div class="split">';
h+='<div class="panel panel-left"><div class="panel-label">'+(s.left_label||'README.md')+'</div><div class="panel-body">'+fmtL(s.left,s.left_highlight)+'</div></div>';
h+='<div class="panel panel-right"><div class="panel-label">'+(s.right_label||'OCZEKIWANIA')+'</div><div class="panel-body">'+(s.right||'')+'</div>';
if(s.checks&&s.checks.length){h+='<div class="checks"><div class="checks-title">WALIDACJA</div>';
s.checks.forEach(c=>{const ic=c.status==='pass'?'V':c.status==='fail'?'X':'...';
h+='<div class="chk"><span class="chk-icon '+c.status+'">'+ic+'</span><span class="chk-label">'+c.label+'</span></div>';
if(c.detail)h+='<div class="chk-detail">'+c.detail+'</div>';});h+='</div>';}
h+='</div></div>';return h;}
function fmtL(key,hl){
if(key==='prompt')return '<div class="prompt-input">Build an order management REST API with human approval before payment</div>';
const raw=RS[key];if(!raw)return '<div style="color:#64748b;text-align:center;padding:40px">---</div>';
let lines=raw.split('\n'),o='',inH=false;
for(let ln of lines){let t=ln.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
if(/^#{1,3} /.test(ln))t='<span class="md-h">'+t+'</span>';
else if(/^```.*markpact:/.test(ln)){const k=(ln.match(/markpact:(\w+)/)||[])[1]||'';
t=t.replace(/markpact:\S+/,'<span class="md-kind">$&</span>');t='<span class="md-fence">'+t+'</span>';
if(hl&&(hl==='all'||hl===k)){inH=true;const c=k==='state'?(ln.includes('blocked')?'hl hl-warn':'hl hl-ok'):'hl';t='<div class="'+c+'">'+t;}}
else if(/^```\s*$/.test(ln)){t='<span class="md-fence">'+t+'</span>';if(inH){t+='</div>';inH=false;}}
else if(/^```/.test(ln))t='<span class="md-fence">'+t+'</span>';
if(/actor: human/.test(ln))t=t.replace(/actor: human/,'<span class="md-human">actor: human</span>');
else if(/actor: llm/.test(ln))t=t.replace(/actor: llm/,'<span class="md-llm">actor: llm</span>');
else if(/actor: script/.test(ln))t=t.replace(/actor: script/,'<span class="md-script">actor: script</span>');
o+=t+'\n';}return o;}
function go(i){if(i<0||i>=S.length)return;document.querySelectorAll('.slide').forEach(s=>s.classList.remove('active'));document.getElementById('s'+i).classList.add('active');vis.add(i);cur=i;upd();}
function toggleAuto(){auto=!auto;document.getElementById('abtn').classList.toggle('on',auto);document.getElementById('abtn').textContent=auto?'|| Pause':'> Auto';if(auto)timer=setInterval(()=>{if(cur<S.length-1)go(cur+1);else toggleAuto();},5000);else clearInterval(timer);}
function upd(){document.getElementById('ctr').textContent=(cur+1)+'/'+S.length;document.getElementById('prog').style.width=((cur+1)/S.length*100)+'%';document.querySelectorAll('.dot').forEach((d,i)=>{d.className='dot'+(i===cur?' a':vis.has(i)?' v':'');});}
document.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key===' '){e.preventDefault();go(cur+1);}if(e.key==='ArrowLeft'){e.preventDefault();go(cur-1);}if(e.key==='a')toggleAuto();});
render();
"""

# ---- Assemble ---------------------------------------------------------------

js = JS_TEMPLATE.replace("%SLIDES%", json.dumps(slides, ensure_ascii=True))
js = js.replace("%RS%", json.dumps(RS, ensure_ascii=True))

html = f"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>marksync - Live Contract Flow</title>
<style>{CSS}</style></head><body>
<div class="progress" id="prog"></div>
<div id="root"></div>
<div class="dots" id="dots"></div>
<div class="nav">
<button onclick="go(cur-1)">&lt;</button>
<button class="auto" id="abtn" onclick="toggleAuto()">&gt; Auto</button>
<span class="ctr" id="ctr"></span>
<button onclick="go(cur+1)">&gt;</button>
</div>
<script>{js}</script>
</body></html>"""

(out / "index.html").write_text(html, encoding="utf-8")
print(f"  Wygenerowano {len(slides)} slajdow (split-screen: LEFT=README / RIGHT=walidacja)")
