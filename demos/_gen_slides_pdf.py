#!/usr/bin/env python3
"""Generate PDF version of marksync split-screen slideshow.

Each page = one slide:
  LEFT half  = Live README.md state (markpact blocks)
  RIGHT half = Expectations + validation checks
"""
import sys
from pathlib import Path
from fpdf import FPDF, XPos, YPos

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("generated/slides")

if __name__ == "__main__":
    out.mkdir(parents=True, exist_ok=True)

# ---- Colors ----------------------------------------------------------------

C_BG      = (10, 10, 26)      # dark background
C_HEADER  = (241, 245, 249)   # white-ish
C_SUB     = (148, 163, 184)   # gray
C_TEXT    = (203, 213, 225)    # light gray
C_LEFT_BG = (15, 23, 42)      # dark blue
C_RIGHT_BG= (17, 24, 39)      # dark blue-gray
C_BLUE    = (56, 189, 248)    # heading blue
C_PURPLE  = (192, 132, 252)   # markpact kind
C_GREEN   = (52, 211, 153)    # pass
C_RED     = (239, 68, 68)     # fail
C_YELLOW  = (251, 191, 36)    # wait / human
C_MONO    = (147, 197, 253)   # code
C_DIM     = (100, 116, 139)   # detail text
C_PANEL_BORDER = (31, 41, 55)
C_ACCENT  = (129, 140, 248)   # accent purple

# ---- README block fragments (same as HTML version) -------------------------

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

FILE_BLOCK = (
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

CORE = [HEADER, ORCH, DEPS, FILE_BLOCK, RUN, DEPLOY]


def st(phase, health="null", sc=0, ec=0):
    h = f'"{health}"' if health != "null" else "null"
    return f'{{"phase":"{phase}","health":{h},"success_count":{sc},"error_count":{ec}}}'


def state_block(phase, health="null", sc=0, ec=0):
    return "```json markpact:state\n" + st(phase, health, sc, ec) + "\n```"


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
    "readme_initial":  "\n\n".join(CORE + [state_block("init"), lg(LOG["init"])]),
    "readme_running":  "\n\n".join(CORE + [state_block("running"), lg(LOG["running"])]),
    "readme_step1":    "\n\n".join(CORE + [state_block("running"), lg(LOG["s1"])]),
    "readme_step2":    "\n\n".join(CORE + [state_block("running"), lg(LOG["s2"])]),
    "readme_step3":    "\n\n".join(CORE + [state_block("running"), lg(LOG["s3"])]),
    "readme_blocked":  "\n\n".join(CORE + [state_block("blocked", "waiting_human"), lg(LOG["blocked"])]),
    "readme_approved": "\n\n".join(CORE + [state_block("running"), lg(LOG["approved"])]),
    "readme_deployed": "\n\n".join(CORE + [state_block("deployed", "ok", 1, 0), lg(LOG["deployed"])]),
}

# ---- Slide definitions (text-only, no HTML) ---------------------------------

def chk(label, status="pass", detail=""):
    return {"label": label, "status": status, "detail": detail}


slides = [
    # 0: Title
    {"title": "marksync",
     "subtitle": "Contract-Based AI-Human-Algorithm Conversation\nfor Live Process Deployment & Control\nwith Self-Learning",
     "layout": "title", "left": "", "right_lines": [], "checks": []},

    # 1: Prompt
    {"title": "1. Prompt -> System",
     "subtitle": "Jedno zdanie uruchamia caly proces",
     "layout": "split",
     "left_label": "INPUT: Prompt uzytkownika",
     "left": "prompt",
     "right_label": "OCZEKIWANIE: Co system powinien zrobic",
     "right_lines": [
         "System powinien:",
         "  1. Sparsowac intencje z promptu",
         "  2. Zidentyfikowac typ uslugi: REST API",
         "  3. Wykryc wymaganie: human approval",
         "  4. Wygenerowac README.md z blokami markpact:*",
         "  5. Ustawic pipeline: script + llm + human",
     ],
     "checks": [
         chk("Prompt sparsowany", detail="IntentParser.parse() -> service_type=api"),
         chk("Human-in-the-loop wykryty", detail="'human approval' -> actor: human"),
         chk("Kontrakt wygenerowany", detail="README.md z 7 blokami markpact:*"),
     ]},

    # 2: Contract
    {"title": "2. Kontrakt README.md -- utworzony",
     "subtitle": "Markdown = zrodlo prawdy dla calego procesu",
     "layout": "split",
     "left_label": "README.md -- aktualny stan",
     "left": "readme_initial",
     "left_highlight": "all",
     "right_label": "OCZEKIWANIE: Wymagane bloki",
     "right_lines": [
         "README.md musi zawierac:",
         "  [V] markpact:orchestration -- pipeline z krokami",
         "  [V] markpact:deps -- zaleznosci runtime",
         "  [V] markpact:file=app/main.py -- kod aplikacji",
         "  [V] markpact:run -- komenda uruchomienia",
         "  [V] markpact:deploy -- konfiguracja deployu",
         "  [V] markpact:state -- stan procesu (phase: init)",
         "  [V] markpact:log -- historia zdarzen",
         "",
         "Walidacja: 7/7 blokow obecnych [V]",
     ],
     "checks": [
         chk("BlockParser.parse() -> 7 blokow", detail="orchestration, deps, file, run, deploy, state, log"),
         chk("SHA-256 hash kazdego bloku", detail="Integralnosc zweryfikowana"),
         chk("Pipeline ma 6 krokow", detail="3x script + 2x llm + 1x human"),
         chk("markpact:state.phase == init", detail="Stan poczatkowy OK"),
     ]},

    # 3: Pipeline Start
    {"title": "3. Pipeline Start",
     "subtitle": "PipelineEngine czyta markpact:orchestration",
     "layout": "split",
     "left_label": "README.md -- markpact:state zmieniony",
     "left": "readme_running",
     "left_highlight": "state",
     "right_label": "OCZEKIWANIE: Engine uruchomiony",
     "right_lines": [
         "Co sie dzieje:",
         "  1. PipelineEngine parsuje markpact:orchestration",
         "  2. Tworzy PipelineRun z 6 krokami",
         "  3. markpact:state: init -> running",
         "  4. markpact:log otrzymuje wpis",
         "",
         "  [phase: init] --> [phase: running]",
     ],
     "checks": [
         chk("PipelineRun utworzony", detail="run_id=run-001, 6 steps"),
         chk("markpact:state zaktualizowany", detail="phase: init -> running"),
         chk("markpact:log wpis dodany", detail="PIPELINE_STARTED: order-api"),
     ]},

    # 4: script step
    {"title": "4. Step: parse_order",
     "subtitle": "actor: script -- Walidacja schematu",
     "layout": "split",
     "left_label": "README.md -- markpact:log +1",
     "left": "readme_step1",
     "left_highlight": "log",
     "right_label": "OCZEKIWANIE: Skrypt walidacyjny",
     "right_lines": [
         "[ACTOR: script] Deterministyczny kod",
         "  ten sam input = ten sam output",
         "",
         "  Funkcja:  validate_order_schema()",
         "  Input:    Order JSON",
         "  Output:   PASS / FAIL",
         "  Czas:     12ms",
         "",
         "Czy skrypt dziala poprawnie?",
         "  schema valid, required fields, types correct",
     ],
     "checks": [
         chk("validate_order_schema() wykonany", detail="12ms, exit code 0"),
         chk("Schema poprawna", detail="customer_id, items, total -- present"),
         chk("Typy danych prawidlowe", detail="total: float, items: list"),
         chk("markpact:log zaktualizowany", detail="STEP_COMPLETED: parse_order"),
     ]},

    # 5: llm step
    {"title": "5. Step: check_inventory",
     "subtitle": "actor: llm -- AI sprawdza magazyn",
     "layout": "split",
     "left_label": "README.md -- markpact:log +1",
     "left": "readme_step2",
     "left_highlight": "log",
     "right_label": "OCZEKIWANIE: LLM poprawnie generuje",
     "right_lines": [
         "[ACTOR: llm] AI (Ollama/OpenRouter)",
         "",
         "  Model:   qwen2.5-coder:7b",
         "  Input:   Order items + inventory",
         "  Output:  Availability check",
         "  Czas:    850ms",
         "",
         "Czy LLM poprawnie generuje?",
         "  valid JSON, items checked, no hallucinations",
     ],
     "checks": [
         chk("LLM odpowiedzial", detail="850ms, model=qwen2.5-coder:7b"),
         chk("Response: valid JSON", detail="{all_available: true, items_checked: 3}"),
         chk("Wszystkie produkty sprawdzone", detail="3/3 items verified"),
         chk("Brak hallucinations", detail="Output matches inventory DB"),
     ]},

    # 6: script fraud
    {"title": "6. Step: fraud_detection",
     "subtitle": "actor: script -- Algorytm fraud",
     "layout": "split",
     "left_label": "README.md -- markpact:log +1",
     "left": "readme_step3",
     "left_highlight": "log",
     "right_label": "OCZEKIWANIE: Fraud check",
     "right_lines": [
         "[ACTOR: script] Deterministyczny algorytm",
         "",
         "  Funkcja:    run_fraud_check()",
         "  Sprawdza:   IP, historia klienta, kwota",
         "  Risk score:  0.12 (low)",
         "  Czas:       45ms",
     ],
     "checks": [
         chk("run_fraud_check() wykonany", detail="45ms, risk_score=0.12"),
         chk("Risk score < threshold (0.7)", detail="0.12 < 0.70 -> SAFE"),
         chk("Klient nie na blacklist", detail="customer_id not in blacklist"),
     ]},

    # 7: human BLOCKED
    {"title": "7. Step: human_payment_approval",
     "subtitle": "actor: human -- PIPELINE ZABLOKOWANY",
     "layout": "split",
     "left_label": "README.md -- markpact:state = blocked",
     "left": "readme_blocked",
     "left_highlight": "state",
     "right_label": "OCZEKIWANIE: Decyzja czlowieka",
     "right_lines": [
         "[ACTOR: human] -- BLOCKED",
         "Pipeline CZEKA na ludzka decyzje.",
         "Zamowienie $2,500 > limit $1,000.",
         "",
         "  HumanTask:       task-abc123",
         "  Kanal:           web (dashboard)",
         "  Timeout:         7200s (2h)",
         "  Powiadomienie:   webhook -> Slack",
         "",
         "Kanaly komunikacji:",
         "  [Dashboard] [Email] [Webhook] [Shell]",
         "",
         "POST /api/pipeline/tasks/task-abc123",
         '  {action: "approve", by: "manager@co.com"}',
     ],
     "checks": [
         chk("HumanTask utworzony", detail="task-abc123, channel=web"),
         chk("Webhook wyslany", detail="POST slack -> 200 OK"),
         chk("markpact:state = blocked", detail="phase: running -> blocked"),
         chk("Oczekiwanie na human...", "wait", detail="timeout za 7155s"),
     ]},

    # 8: Human approves
    {"title": "8. Human -> Approve",
     "subtitle": "Manager zatwierdza -- pipeline kontynuuje",
     "layout": "split",
     "left_label": "README.md -- markpact:state = running",
     "left": "readme_approved",
     "left_highlight": "state",
     "right_label": "Czlowiek podjal decyzje",
     "right_lines": [
         "APPROVAL RECEIVED",
         "",
         "  Decyzja:        APPROVED",
         "  Przez:          manager@company.com",
         "  Czas decyzji:   45 sekund",
         "  Kanal:          Dashboard (web)",
         "",
         "Zmiana w README.md:",
         "  [phase: blocked] --> [phase: running]",
         "",
         "Pipeline kontynuuje automatycznie.",
     ],
     "checks": [
         chk("Human approval received", detail="APPROVED by manager@company.com (45s)"),
         chk("HumanTask resolved", detail="task-abc123 status=resolved"),
         chk("Pipeline wznowiony", detail="status: blocked -> running"),
         chk("markpact:state zaktualizowany", detail="phase: blocked -> running"),
     ]},

    # 9: Deploy
    {"title": "9. Deploy -> Production",
     "subtitle": "Ostatnie kroki + deployment",
     "layout": "split",
     "left_label": "README.md -- markpact:state = deployed",
     "left": "readme_deployed",
     "left_highlight": "state",
     "right_label": "OCZEKIWANIE: Deploy poprawny",
     "right_lines": [
         "Pozostale kroki:",
         "  [V] process_payment -- PASS (320ms)",
         "  [V] deploy_update   -- PASS (1200ms)",
         "",
         "Pipeline COMPLETED -- 6/6 steps passed",
         "",
         "Finalny stan README.md:",
         "  [phase: running] --> [phase: deployed]",
     ],
     "checks": [
         chk("process_payment -> PASS", detail="320ms, transaction_id=TXN-001"),
         chk("deploy_update -> PASS", detail="1200ms, container started"),
         chk("Healthcheck /health -> 200 OK", detail="{status:ok}"),
         chk("markpact:state.phase = deployed", detail="success_count: 0 -> 1"),
         chk("markpact:log -- 10 wpisow", detail="Pelna historia pipeline"),
     ]},

    # 10: Learning
    {"title": "10. Self-Learning",
     "subtitle": "Pattern zapisany -> kolejny projekt lepszy",
     "layout": "split",
     "left_label": "README.md -- finalny stan",
     "left": "readme_deployed",
     "right_label": "Ewolucja na bazie danych",
     "right_lines": [
         "Pattern Library -- zapisany wzorzec:",
         "",
         "  id:            api-rest-orders",
         "  keywords:      rest, api, orders, payment",
         "  success_rate:  1.00",
         "  usage_count:   1",
         "  service_type:  api",
         "",
         "Nastepny podobny prompt:",
         "  System znajdzie ten pattern i uzyje go",
         "  jako template. Success rate rosnie",
         "  z kazdym sukcesem.",
     ],
     "checks": [
         chk("PatternLibrary.save_from_contract()", detail="Pattern api-rest-orders zapisany"),
         chk("success_rate = 1.00", detail="Pierwszy run -> 100%"),
         chk("Pattern reusable", detail="Kolejny 'REST API + orders' -> match"),
     ]},

    # 11: Summary
    {"title": "Podsumowanie",
     "subtitle": "Caly przeplyw w jednym pliku README.md",
     "layout": "title",
     "left": "",
     "right_lines": [],
     "checks": [],
     "summary": True},
]

# ---- PDF Generation ---------------------------------------------------------


class SlidesPDF(FPDF):
    """Landscape A4 PDF with dark theme mimicking the HTML slideshow."""

    def __init__(self):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.set_auto_page_break(auto=False)
        # Use built-in fonts only (Helvetica, Courier)
        self.W = 297  # A4 landscape width
        self.H = 210  # A4 landscape height
        self.M = 8    # margin
        self.HALF = (self.W - 3 * self.M) / 2  # half panel width

    def _bg(self):
        self.set_fill_color(*C_BG)
        self.rect(0, 0, self.W, self.H, "F")

    def _header_bar(self, title, subtitle, y=6):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*C_HEADER)
        self.set_xy(self.M, y)
        self.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if subtitle:
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*C_SUB)
            self.set_xy(self.M, y + 8)
            self.cell(0, 5, subtitle, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return y + 15

    def _panel_box(self, x, y, w, h, label, bg_color, label_color):
        # border
        self.set_draw_color(*C_PANEL_BORDER)
        self.set_fill_color(*bg_color)
        self.rect(x, y, w, h, "DF")
        # label bar
        self.set_fill_color(bg_color[0] - 3, bg_color[1] - 3, bg_color[2] - 3)
        self.rect(x, y, w, 7, "F")
        self.set_draw_color(*C_PANEL_BORDER)
        self.line(x, y + 7, x + w, y + 7)
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(*label_color)
        self.set_xy(x + 3, y + 1)
        self.cell(w - 6, 5, label.upper()[:60], new_x=XPos.RIGHT, new_y=YPos.TOP)
        return y + 9  # content start y

    def _readme_text(self, x, y, w, max_y, readme_key, highlight=None):
        """Render README.md content as monospaced text with syntax coloring."""
        raw = RS.get(readme_key, "")
        if not raw:
            return y
        self.set_font("Courier", "", 6)
        lh = 2.8  # line height
        in_fence = False
        fence_kind = None
        for line in raw.split("\n"):
            if y + lh > max_y:
                self.set_text_color(*C_DIM)
                self.set_xy(x + 2, y)
                self.cell(w - 4, lh, "  ... (kontynuacja)", new_x=XPos.RIGHT, new_y=YPos.TOP)
                break
            # Determine color
            if line.startswith("# "):
                self.set_text_color(*C_BLUE)
                self.set_font("Courier", "B", 7)
            elif line.startswith("```") and "markpact:" in line:
                self.set_text_color(*C_PURPLE)
                self.set_font("Courier", "B", 6)
                in_fence = True
                m = line.split("markpact:")
                fence_kind = m[1].split()[0] if len(m) > 1 else ""
                # highlight bar
                if highlight and (highlight == "all" or highlight == fence_kind.split("=")[0]):
                    self.set_fill_color(30, 40, 70)
                    self.rect(x, y, w, lh, "F")
            elif line.startswith("```"):
                self.set_text_color(*C_DIM)
                self.set_font("Courier", "", 6)
                in_fence = False
                fence_kind = None
            elif in_fence:
                # highlight continued
                if highlight and (highlight == "all" or highlight == (fence_kind or "").split("=")[0]):
                    self.set_fill_color(20, 30, 55)
                    self.rect(x, y, w, lh, "F")
                if "actor: human" in line:
                    self.set_text_color(*C_YELLOW)
                elif "actor: llm" in line:
                    self.set_text_color(*C_BLUE)
                elif "actor: script" in line:
                    self.set_text_color(*C_GREEN)
                else:
                    self.set_text_color(*C_MONO)
                self.set_font("Courier", "", 6)
            else:
                self.set_text_color(*C_TEXT)
                self.set_font("Courier", "", 6)

            self.set_xy(x + 2, y)
            # Truncate long lines
            display = line[:80]
            self.cell(w - 4, lh, display, new_x=XPos.RIGHT, new_y=YPos.TOP)
            y += lh
            # Reset after heading
            if line.startswith("# "):
                self.set_font("Courier", "", 6)
        return y

    def _right_text(self, x, y, w, max_y, lines):
        """Render right-panel explanation text."""
        self.set_font("Helvetica", "", 8)
        lh = 4
        for line in lines:
            if y + lh > max_y:
                break
            if line.startswith("[ACTOR:") or line.startswith("APPROVAL") or line == "":
                if line.startswith("[ACTOR: script"):
                    self.set_text_color(*C_GREEN)
                    self.set_font("Helvetica", "B", 9)
                elif line.startswith("[ACTOR: llm"):
                    self.set_text_color(*C_BLUE)
                    self.set_font("Helvetica", "B", 9)
                elif line.startswith("[ACTOR: human"):
                    self.set_text_color(*C_YELLOW)
                    self.set_font("Helvetica", "B", 9)
                elif line.startswith("APPROVAL"):
                    self.set_text_color(*C_GREEN)
                    self.set_font("Helvetica", "B", 10)
                else:
                    y += 1
                    continue
            elif line.startswith("  ") and not line.startswith("  ["):
                self.set_text_color(*C_TEXT)
                self.set_font("Courier", "", 7)
            elif "[V]" in line:
                self.set_text_color(*C_GREEN)
                self.set_font("Helvetica", "", 8)
            elif "[X]" in line:
                self.set_text_color(*C_RED)
                self.set_font("Helvetica", "", 8)
            elif "-->" in line or "->" in line:
                self.set_text_color(*C_ACCENT)
                self.set_font("Courier", "B", 8)
            elif line.startswith("Pipeline") or line.startswith("Walidacja"):
                self.set_text_color(*C_GREEN)
                self.set_font("Helvetica", "B", 9)
            else:
                self.set_text_color(*C_TEXT)
                self.set_font("Helvetica", "", 8)

            self.set_xy(x + 3, y)
            self.cell(w - 6, lh, line[:70], new_x=XPos.RIGHT, new_y=YPos.TOP)
            y += lh
            self.set_font("Helvetica", "", 8)
        return y

    def _checks(self, x, y, w, checks):
        """Render validation checks section."""
        if not checks:
            return y
        # separator
        self.set_draw_color(*C_PANEL_BORDER)
        self.line(x, y, x + w, y)
        y += 2
        self.set_font("Helvetica", "B", 6)
        self.set_text_color(*C_DIM)
        self.set_xy(x + 3, y)
        self.cell(w - 6, 3, "WALIDACJA", new_x=XPos.RIGHT, new_y=YPos.TOP)
        y += 4

        for c in checks:
            icon = "[V]" if c["status"] == "pass" else ("[X]" if c["status"] == "fail" else "[?]")
            color = C_GREEN if c["status"] == "pass" else (C_RED if c["status"] == "fail" else C_YELLOW)
            self.set_font("Courier", "B", 7)
            self.set_text_color(*color)
            self.set_xy(x + 3, y)
            self.cell(8, 3, icon, new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*C_HEADER)
            self.set_xy(x + 11, y)
            self.cell(w - 14, 3, c["label"][:55], new_x=XPos.RIGHT, new_y=YPos.TOP)
            y += 3.2
            if c.get("detail"):
                self.set_font("Helvetica", "", 5.5)
                self.set_text_color(*C_DIM)
                self.set_xy(x + 11, y)
                self.cell(w - 14, 2.5, c["detail"][:70], new_x=XPos.RIGHT, new_y=YPos.TOP)
                y += 3
        return y

    def add_title_slide(self, slide):
        self.add_page()
        self._bg()
        # centered title
        self.set_font("Helvetica", "B", 36)
        self.set_text_color(*C_BLUE)
        title = slide["title"]
        tw = self.get_string_width(title)
        self.set_xy((self.W - tw) / 2, 60)
        self.cell(tw, 15, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # subtitle
        if slide.get("subtitle"):
            self.set_font("Helvetica", "", 13)
            self.set_text_color(*C_SUB)
            for i, line in enumerate(slide["subtitle"].split("\n")):
                sw = self.get_string_width(line)
                self.set_xy((self.W - sw) / 2, 80 + i * 7)
                self.cell(sw, 6, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Summary grid for last slide
        if slide.get("summary"):
            items = [
                ("1", "prompt", "Wejscie"),
                ("1", "README.md", "Kontrakt"),
                ("7", "blokow", "markpact:*"),
                ("3", "script", "Deterministyczne"),
                ("2", "llm", "AI processing"),
                ("1", "human", "Approval"),
            ]
            bw = 40
            total = len(items) * bw + (len(items) - 1) * 5
            sx = (self.W - total) / 2
            by = 115
            for i, (val, label, sub) in enumerate(items):
                bx = sx + i * (bw + 5)
                self.set_fill_color(17, 24, 39)
                self.set_draw_color(*C_PANEL_BORDER)
                self.rect(bx, by, bw, 30, "DF")
                self.set_font("Helvetica", "B", 18)
                self.set_text_color(*C_HEADER)
                vw = self.get_string_width(val)
                self.set_xy(bx + (bw - vw) / 2, by + 3)
                self.cell(vw, 8, val)
                self.set_font("Helvetica", "B", 9)
                self.set_text_color(*C_ACCENT)
                lw = self.get_string_width(label)
                self.set_xy(bx + (bw - lw) / 2, by + 12)
                self.cell(lw, 5, label)
                self.set_font("Helvetica", "", 7)
                self.set_text_color(*C_DIM)
                sw2 = self.get_string_width(sub)
                self.set_xy(bx + (bw - sw2) / 2, by + 19)
                self.cell(sw2, 4, sub)

            # Final message
            self.set_font("Helvetica", "B", 16)
            self.set_text_color(*C_ACCENT)
            msg = "Jeden plik. Jeden kontrakt. Wszystko walidowalne."
            mw = self.get_string_width(msg)
            self.set_xy((self.W - mw) / 2, by + 40)
            self.cell(mw, 8, msg)

        # Page number
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*C_DIM)
        self.set_xy(self.W - 25, self.H - 8)
        pn = f"{self.page_no()}/{len(slides)}"
        self.cell(20, 4, pn, align="R")

    def add_split_slide(self, slide):
        self.add_page()
        self._bg()

        # Header
        y_start = self._header_bar(slide["title"], slide.get("subtitle", ""))

        panel_h = self.H - y_start - self.M - 2
        left_x = self.M
        right_x = self.M + self.HALF + self.M

        # LEFT panel
        cy = self._panel_box(left_x, y_start, self.HALF, panel_h,
                              slide.get("left_label", "README.md"),
                              C_LEFT_BG, C_BLUE)
        if slide["left"] == "prompt":
            self.set_font("Helvetica", "BI", 14)
            self.set_text_color(*C_HEADER)
            self.set_xy(left_x + 8, cy + 15)
            self.multi_cell(self.HALF - 16, 8,
                           "Build an order management\nREST API with human approval\nbefore payment")
        else:
            hl = slide.get("left_highlight")
            self._readme_text(left_x, cy, self.HALF, y_start + panel_h - 2,
                             slide["left"], hl)

        # RIGHT panel — estimate space for checks
        checks = slide.get("checks", [])
        checks_h = 6 + len(checks) * 6.5 if checks else 0
        right_body_h = panel_h - checks_h

        cy = self._panel_box(right_x, y_start, self.HALF, panel_h,
                              slide.get("right_label", "OCZEKIWANIA"),
                              C_RIGHT_BG, C_PURPLE)
        right_lines = slide.get("right_lines", [])
        ey = self._right_text(right_x, cy, self.HALF,
                              y_start + right_body_h, right_lines)

        # Checks at bottom of right panel
        checks_y = y_start + panel_h - checks_h
        if checks_y < ey:
            checks_y = ey + 2
        self._checks(right_x, checks_y, self.HALF, checks)

        # Page number
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*C_DIM)
        self.set_xy(self.W - 25, self.H - 8)
        pn = f"{self.page_no()}/{len(slides)}"
        self.cell(20, 4, pn, align="R")


# ---- Generate ---------------------------------------------------------------

pdf = SlidesPDF()
    pdf.set_title("marksync - Contract Flow Presentation")
    pdf.set_author("marksync")

for slide in slides:
    if slide["layout"] == "title":
        pdf.add_title_slide(slide)
    else:
        pdf.add_split_slide(slide)

pdf_path = out / "marksync_flow.pdf"
    pdf.output(str(pdf_path))
    print(f"  PDF: {pdf_path} ({pdf_path.stat().st_size // 1024} KB, {len(slides)} stron)")
