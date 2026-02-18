#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# DEMO: Browser View — Pokaż README i dane w przeglądarce
# ═══════════════════════════════════════════════════════════════════════════════
#
# Generuje kontrakt z promptu, renderuje HTML i otwiera w przeglądarce.
# Wszystkie bloki markpact:* widoczne bezpośrednio.
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
DELAY=${DEMO_DELAY:-1}

if [ -f ".venv/bin/activate" ]; then source .venv/bin/activate 2>/dev/null; fi

step() { echo -e "\n${BOLD}${CYAN}[$1]${NC} $2"; sleep "$DELAY"; }
info() { echo -e "  ${YELLOW}→${NC} $1"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }

BROWSER_PORT=${BROWSER_PORT:-9090}

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║  DEMO: Browser View — Kontrakt i Dane w Przeglądarce                        ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ═══════════════════════════════════════════════════════════════════════════════
step "1/4" "Generowanie kontraktu z promptu"
# ═══════════════════════════════════════════════════════════════════════════════

# Upewnij się że demo_contract wygenerował README
DEMO_DIR="$PROJECT_DIR/generated/demo-order-api"
if [ ! -f "$DEMO_DIR/README.md" ]; then
    info "Kontrakt nie istnieje, generuję..."
    bash "$SCRIPT_DIR/demo_contract.sh"
fi
ok "Kontrakt: $DEMO_DIR/README.md"

# ═══════════════════════════════════════════════════════════════════════════════
step "2/4" "Parsowanie bloków markpact i renderowanie HTML"
# ═══════════════════════════════════════════════════════════════════════════════

BROWSER_DIR="$PROJECT_DIR/generated/browser-view"
mkdir -p "$BROWSER_DIR"

info "Generuję HTML z blokami markpact..."

python3 << RENDER_PY
import sys, os, json, html, time
sys.path.insert(0, os.getcwd())
from marksync.sync import BlockParser
from pathlib import Path

readme_path = Path("generated/demo-order-api/README.md")
md_raw = readme_path.read_text("utf-8")
blocks = BlockParser.parse(md_raw)

# Generuj dane JSON
blocks_json = []
for b in blocks:
    blocks_json.append({
        "block_id": b.block_id,
        "kind": b.kind,
        "lang": b.lang,
        "path": b.path,
        "content": b.content,
        "sha256": b.sha256,
        "line_start": b.line_start,
        "line_end": b.line_end,
        "size": len(b.content),
    })

# Zapisz JSON
Path("generated/browser-view/blocks.json").write_text(
    json.dumps(blocks_json, indent=2, ensure_ascii=False), encoding="utf-8"
)

# Pipeline steps JSON
import yaml
pipeline_steps = []
for b in blocks:
    if b.kind == "orchestration":
        data = yaml.safe_load(b.content)
        pipeline_steps = data.get("pipeline", {}).get("steps", [])

Path("generated/browser-view/pipeline.json").write_text(
    json.dumps(pipeline_steps, indent=2, ensure_ascii=False), encoding="utf-8"
)

# Generuj index.html
actor_colors = {"human": "#f59e0b", "llm": "#3b82f6", "script": "#10b981"}
actor_icons = {"human": "👤", "llm": "🤖", "script": "⚙️"}

blocks_html = ""
for b in blocks_json:
    kind_color = {"orchestration": "#8b5cf6", "deps": "#06b6d4", "run": "#ef4444",
                  "deploy": "#f97316", "state": "#10b981", "log": "#6b7280",
                  "file": "#3b82f6"}.get(b["kind"], "#9ca3af")
    escaped = html.escape(b["content"])
    blocks_html += f'''
    <div class="block" style="border-left: 4px solid {kind_color}">
        <div class="block-header">
            <span class="block-kind" style="background:{kind_color}">markpact:{b["kind"]}</span>
            {f'<span class="block-path">{b["path"]}</span>' if b["path"] else ""}
            <span class="block-meta">{b["size"]} bytes | sha256:{b["sha256"][:12]}...</span>
        </div>
        <pre class="block-content"><code>{escaped}</code></pre>
    </div>'''

pipeline_html = ""
for i, s in enumerate(pipeline_steps):
    actor = s.get("actor", "?")
    color = actor_colors.get(actor, "#9ca3af")
    icon = actor_icons.get(actor, "?")
    name = s.get("name", "?")
    desc = s.get("config", {}).get("description", "")
    channel = s.get("config", {}).get("channel", "")
    ch_badge = f'<span class="channel-badge">{channel}</span>' if channel else ""
    pipeline_html += f'''
    <div class="step" style="border-left: 4px solid {color}">
        <div class="step-header">
            <span class="step-icon">{icon}</span>
            <span class="step-name">{name}</span>
            <span class="step-actor" style="background:{color}">actor: {actor}</span>
            {ch_badge}
        </div>
        <div class="step-desc">{desc}</div>
    </div>'''

now = time.strftime("%Y-%m-%d %H:%M:%S")

index_html = f'''<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>marksync — Contract Browser View</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
         background: #0f172a; color: #e2e8f0; padding: 20px; }}
  h1 {{ color: #38bdf8; margin-bottom: 8px; font-size: 28px; }}
  h2 {{ color: #94a3b8; margin: 24px 0 12px; font-size: 20px; border-bottom: 1px solid #334155; padding-bottom: 8px; }}
  .header {{ background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid #334155;
             border-radius: 12px; padding: 24px; margin-bottom: 24px; }}
  .header p {{ color: #94a3b8; }}
  .meta {{ display: flex; gap: 16px; margin-top: 12px; flex-wrap: wrap; }}
  .meta span {{ background: #1e293b; border: 1px solid #334155; padding: 4px 12px;
                border-radius: 6px; font-size: 13px; color: #94a3b8; }}
  .tabs {{ display: flex; gap: 4px; margin-bottom: 16px; }}
  .tab {{ padding: 8px 20px; background: #1e293b; border: 1px solid #334155; border-radius: 8px 8px 0 0;
          cursor: pointer; color: #94a3b8; font-size: 14px; }}
  .tab.active {{ background: #334155; color: #f1f5f9; border-bottom-color: #334155; }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}
  .block {{ background: #1e293b; border-radius: 8px; margin-bottom: 12px; overflow: hidden; }}
  .block-header {{ padding: 10px 16px; display: flex; align-items: center; gap: 10px;
                   background: rgba(0,0,0,0.2); flex-wrap: wrap; }}
  .block-kind {{ padding: 2px 10px; border-radius: 4px; color: white; font-size: 12px; font-weight: 600; }}
  .block-path {{ color: #fbbf24; font-size: 13px; }}
  .block-meta {{ color: #64748b; font-size: 12px; margin-left: auto; }}
  .block-content {{ padding: 12px 16px; overflow-x: auto; font-size: 13px; line-height: 1.5; }}
  .block-content code {{ color: #e2e8f0; }}
  .step {{ background: #1e293b; border-radius: 8px; margin-bottom: 8px; padding: 12px 16px; }}
  .step-header {{ display: flex; align-items: center; gap: 10px; }}
  .step-icon {{ font-size: 20px; }}
  .step-name {{ font-weight: 600; color: #f1f5f9; }}
  .step-actor {{ padding: 2px 10px; border-radius: 4px; color: white; font-size: 11px; }}
  .step-desc {{ color: #94a3b8; font-size: 13px; margin-top: 6px; margin-left: 36px; }}
  .channel-badge {{ background: #7c3aed; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .stat {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; text-align: center; }}
  .stat-value {{ font-size: 28px; font-weight: 700; color: #38bdf8; }}
  .stat-label {{ font-size: 13px; color: #94a3b8; margin-top: 4px; }}
  .md-raw {{ background: #1e293b; padding: 16px; border-radius: 8px; white-space: pre-wrap;
             font-size: 13px; line-height: 1.6; max-height: 600px; overflow-y: auto; }}
</style>
</head>
<body>

<div class="header">
  <h1>📋 marksync — Contract Browser View</h1>
  <p>Order Management API — kontrakt wygenerowany z promptu</p>
  <div class="meta">
    <span>📁 generated/demo-order-api/README.md</span>
    <span>🧱 {len(blocks_json)} bloków markpact</span>
    <span>📊 {len(pipeline_steps)} kroków pipeline</span>
    <span>🕐 {now}</span>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="stat-value">{len(blocks_json)}</div><div class="stat-label">Bloki markpact</div></div>
  <div class="stat"><div class="stat-value">{len(pipeline_steps)}</div><div class="stat-label">Pipeline Steps</div></div>
  <div class="stat"><div class="stat-value">{sum(1 for s in pipeline_steps if s.get('actor')=='human')}</div><div class="stat-label">Human Approvals</div></div>
  <div class="stat"><div class="stat-value">{sum(1 for s in pipeline_steps if s.get('actor')=='llm')}</div><div class="stat-label">LLM Steps</div></div>
  <div class="stat"><div class="stat-value">{sum(1 for s in pipeline_steps if s.get('actor')=='script')}</div><div class="stat-label">Script Steps</div></div>
</div>

<div class="tabs">
  <div class="tab active" onclick="showTab('pipeline')">Pipeline</div>
  <div class="tab" onclick="showTab('blocks')">Bloki markpact</div>
  <div class="tab" onclick="showTab('raw')">README.md (raw)</div>
  <div class="tab" onclick="showTab('json')">JSON Data</div>
</div>

<div id="pipeline" class="panel active">
  <h2>Pipeline Steps ({len(pipeline_steps)} kroków)</h2>
  {pipeline_html}
</div>

<div id="blocks" class="panel">
  <h2>Bloki markpact ({len(blocks_json)})</h2>
  {blocks_html}
</div>

<div id="raw" class="panel">
  <h2>README.md (raw markdown)</h2>
  <div class="md-raw">{html.escape(md_raw)}</div>
</div>

<div id="json" class="panel">
  <h2>JSON Data</h2>
  <div class="block">
    <div class="block-header"><span class="block-kind" style="background:#3b82f6">blocks.json</span></div>
    <pre class="block-content"><code>{html.escape(json.dumps(blocks_json, indent=2, ensure_ascii=False)[:3000])}</code></pre>
  </div>
  <div class="block">
    <div class="block-header"><span class="block-kind" style="background:#8b5cf6">pipeline.json</span></div>
    <pre class="block-content"><code>{html.escape(json.dumps(pipeline_steps, indent=2, ensure_ascii=False))}</code></pre>
  </div>
</div>

<script>
function showTab(name) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(name).classList.add('active');
  event.target.classList.add('active');
}}
</script>

</body>
</html>'''

Path("generated/browser-view/index.html").write_text(index_html, encoding="utf-8")
print(f"  Wygenerowano {len(blocks_json)} bloków, {len(pipeline_steps)} pipeline steps")
RENDER_PY

ok "HTML wygenerowany: $BROWSER_DIR/index.html"
ok "JSON dane: $BROWSER_DIR/blocks.json, $BROWSER_DIR/pipeline.json"

sleep "$DELAY"

# ═══════════════════════════════════════════════════════════════════════════════
step "3/4" "Uruchamiam serwer HTTP na porcie $BROWSER_PORT"
# ═══════════════════════════════════════════════════════════════════════════════

# Zabij stary serwer jeśli działa
fuser -k "$BROWSER_PORT/tcp" 2>/dev/null || true

info "Startuję Python HTTP server..."

cd "$BROWSER_DIR"
python3 -m http.server "$BROWSER_PORT" --bind 0.0.0.0 &
SERVER_PID=$!
cd "$PROJECT_DIR"

sleep 1

if kill -0 "$SERVER_PID" 2>/dev/null; then
    ok "Serwer działa na http://localhost:$BROWSER_PORT"
else
    echo -e "  ${RED}✗ Nie udało się uruchomić serwera${NC}"
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════════
step "4/4" "Otwieram przeglądarkę"
# ═══════════════════════════════════════════════════════════════════════════════

URL="http://localhost:$BROWSER_PORT"
info "URL: $URL"

# Próbuj otworzyć przeglądarkę
if command -v xdg-open &>/dev/null; then
    xdg-open "$URL" 2>/dev/null &
elif command -v open &>/dev/null; then
    open "$URL" 2>/dev/null &
else
    info "Otwórz ręcznie: $URL"
fi

echo ""
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Przeglądarka otwarta na: ${BOLD}$URL${NC}"
echo -e "${GREEN}  Naciśnij Ctrl+C aby zatrzymać serwer${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""

# Cleanup na exit
trap "kill $SERVER_PID 2>/dev/null; echo -e '\n${YELLOW}Serwer zatrzymany.${NC}'" EXIT

# Czekaj na Ctrl+C
wait "$SERVER_PID"
