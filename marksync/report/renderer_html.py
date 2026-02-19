"""
marksync.report.renderer_html — Render ReportData to an interactive HTML slideshow.

Generates a single self-contained HTML file with Preact-free vanilla JS,
split-screen layout (59% left / 41% right), keyboard navigation, auto-play.
All data comes from ReportData — zero hardcoded content.
"""

from __future__ import annotations

import json
from pathlib import Path

from marksync.report.collector import ReportData


def _build_slides(report: ReportData) -> list[dict]:
    """Convert ReportData steps into slide definitions for the JS engine."""
    slides = []

    # Title slide
    slides.append({
        "title": report.project_name,
        "subtitle": report.prompt,
        "layout": "title",
        "meta": {
            "service_type": report.service_type,
            "actors": report.actors,
            "stack": report.suggested_stack,
            "endpoints": len(report.endpoints),
            "steps": len(report.steps),
        },
    })

    # One slide per step
    for step in report.steps:
        slides.append({
            "title": step.title,
            "subtitle": step.subtitle,
            "layout": "split",
            "left_label": "README.md" if step.readme_content else "INPUT",
            "left_content": step.readme_content,
            "left_highlight": step.highlight,
            "right_label": "VALIDATION",
            "right_lines": step.right_lines,
            "checks": step.checks,
            "phase": step.phase,
            "is_prompt": step.name == "prompt",
        })

    # Summary slide
    slides.append({
        "title": "Summary",
        "subtitle": f"{report.project_name} — fully generated, fully controllable",
        "layout": "summary",
        "endpoints": report.endpoints,
        "project_name": report.project_name,
        "actors": report.actors,
        "service_type": report.service_type,
    })

    return slides


# ── CSS ──────────────────────────────────────────────────────────────────

CSS = """\
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#0a0a1a;color:#e2e8f0;overflow:hidden;height:100vh}
.slide{display:none;height:100vh;flex-direction:column;padding:12px 20px}.slide.active{display:flex}
.slide-header{display:flex;align-items:baseline;gap:12px;margin-bottom:8px;flex-shrink:0}
.slide-header h2{font-size:26px;color:#f1f5f9}.slide-header .sub{font-size:15px;color:#94a3b8}
.split{display:grid;grid-template-columns:59fr 41fr;gap:12px;flex:1;min-height:0}
.panel{display:flex;flex-direction:column;min-height:0;border:1px solid #1f2937;border-radius:8px;overflow:hidden}
.panel-label{padding:8px 14px;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:1px;flex-shrink:0;border-bottom:1px solid #1f2937}
.panel-left .panel-label{background:#0c1425;color:#60a5fa}
.panel-right .panel-label{background:#1a0f25;color:#a78bfa}
.panel-body{flex:1;overflow-y:auto;padding:14px;font-size:14px;line-height:1.7}
.panel-left .panel-body{background:#0f172a;font-family:'JetBrains Mono',Consolas,monospace;white-space:pre-wrap;font-size:13px;line-height:1.6}
.panel-right .panel-body{background:#111827}
.md-h{color:#38bdf8;font-weight:700;font-size:15px}.md-fence{color:#475569}.md-kind{color:#c084fc;font-weight:600}
.md-human{color:#fbbf24;font-weight:600}.md-llm{color:#60a5fa}.md-script{color:#34d399}
.hl{background:rgba(59,130,246,.12);border-left:3px solid #3b82f6;margin:0 -14px;padding:2px 14px;animation:pulse 2s ease-in-out}
@keyframes pulse{0%,100%{background:rgba(59,130,246,.12)}50%{background:rgba(59,130,246,.25)}}
.checks{flex-shrink:0;border-top:1px solid #1f2937;padding:10px 14px;background:#0a0f1a}
.checks-title{font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#64748b;margin-bottom:8px}
.chk{display:flex;align-items:flex-start;gap:8px;padding:3px 0;font-size:14px}
.chk-icon{width:20px;text-align:center;flex-shrink:0;font-weight:700}
.chk-icon.pass{color:#34d399}.chk-icon.fail{color:#ef4444}.chk-icon.wait{color:#fbbf24}
.chk-label{color:#e2e8f0}.chk-detail{color:#64748b;font-size:12px;margin-left:28px}
.prompt-input{font-size:24px;color:#f1f5f9;font-style:italic;padding:40px;text-align:center;background:linear-gradient(135deg,#1e293b,#0f172a);border:2px solid #334155;border-radius:12px;margin:20px}
.progress{position:fixed;top:0;left:0;height:3px;background:#3b82f6;transition:width .4s;z-index:100}
.nav{position:fixed;bottom:12px;left:50%;transform:translateX(-50%);display:flex;gap:8px;z-index:100;align-items:center}
.nav button{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);color:#e2e8f0;padding:8px 18px;border-radius:6px;cursor:pointer;font-size:14px}
.nav button:hover{background:rgba(59,130,246,.25);border-color:#3b82f6}
.nav .ctr{color:#64748b;font-size:14px;min-width:50px;text-align:center}
.nav .auto.on{background:rgba(59,130,246,.3);border-color:#3b82f6}
.dots{position:fixed;bottom:48px;left:50%;transform:translateX(-50%);display:flex;gap:5px;z-index:100}
.dot{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.12);cursor:pointer;transition:.3s}
.dot.a{background:#3b82f6;transform:scale(1.4)}.dot.v{background:rgba(59,130,246,.4)}
.title-slide{display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;flex:1}
.title-slide h1{font-size:52px;background:linear-gradient(135deg,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.title-slide .ts{font-size:18px;color:#94a3b8;max-width:750px;margin:12px 0 28px;line-height:1.6}
.summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:24px;max-width:850px}
.sg-item{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:18px;text-align:center}
.sg-item .ic{font-size:28px;margin-bottom:4px;font-weight:700;color:#f1f5f9}.sg-item .vl{font-size:14px;font-weight:600;color:#818cf8}
.sg-item .lb{font-size:12px;color:#94a3b8;margin-top:2px}
.ep-table{margin:16px auto;text-align:left;max-width:700px}
.ep-table td{padding:3px 12px;font-size:14px;font-family:monospace}
.ep-method{color:#60a5fa;font-weight:600}.ep-path{color:#e2e8f0}.ep-file{color:#64748b}
.ctrl-section{margin-top:20px;max-width:700px;text-align:left}
.ctrl-section h3{color:#818cf8;font-size:15px;margin-bottom:8px}
.ctrl-row{display:flex;gap:10px;padding:2px 0;font-size:13px;font-family:monospace}
.ctrl-label{color:#34d399;min-width:120px}.ctrl-val{color:#93c5fd}
"""

# ── JS ───────────────────────────────────────────────────────────────────

JS = r"""
const S=__SLIDES__;
let cur=0,auto=false,timer=null;const vis=new Set([0]);
function render(){
  const r=document.getElementById('root'),d=document.getElementById('dots');
  r.innerHTML='';d.innerHTML='';
  S.forEach((s,i)=>{
    const dot=document.createElement('div');dot.className='dot'+(i===0?' a':'');
    dot.onclick=()=>go(i);d.appendChild(dot);
    const sl=document.createElement('div');sl.className='slide'+(i===0?' active':'');
    sl.id='s'+i;sl.innerHTML=bld(s,i);r.appendChild(sl);
  });
  upd();
}

function bld(s,i){
  if(s.layout==='title') return buildTitle(s);
  if(s.layout==='summary') return buildSummary(s);
  return buildSplit(s);
}

function buildTitle(s){
  let h='<div class="title-slide"><h1>'+esc(s.title)+'</h1>';
  h+='<div class="ts">'+esc(s.subtitle)+'</div>';
  if(s.meta){
    const m=s.meta;
    h+='<div class="summary-grid">';
    h+='<div class="sg-item"><div class="ic">'+m.steps+'</div><div class="vl">steps</div><div class="lb">Pipeline</div></div>';
    h+='<div class="sg-item"><div class="ic">'+m.actors.length+'</div><div class="vl">actors</div><div class="lb">'+esc(m.actors.join(', '))+'</div></div>';
    h+='<div class="sg-item"><div class="ic">'+esc(m.service_type)+'</div><div class="vl">service</div><div class="lb">'+esc(m.stack.join(', '))+'</div></div>';
    h+='<div class="sg-item"><div class="ic">'+m.endpoints+'</div><div class="vl">endpoints</div><div class="lb">API</div></div>';
    h+='</div>';
  }
  h+='<div style="color:#64748b;font-size:13px;margin-top:20px">Arrow keys / Space = navigate | A = auto-play</div>';
  h+='</div>';
  return h;
}

function buildSummary(s){
  let h='<div class="title-slide"><h2 style="font-size:32px;color:#f1f5f9">'+esc(s.title)+'</h2>';
  h+='<div class="ts">'+esc(s.subtitle)+'</div>';
  if(s.endpoints&&s.endpoints.length){
    h+='<table class="ep-table">';
    s.endpoints.forEach(e=>{
      h+='<tr><td class="ep-method">'+esc(e.method)+'</td><td class="ep-path">'+esc(e.path)+'</td><td class="ep-file">'+esc(e.file||'')+'</td></tr>';
    });
    h+='</table>';
  }
  h+='<div class="ctrl-section"><h3>Client Infrastructure Control</h3>';
  const ctrls=[["Dashboard","marksync dashboard"],["API Docs","http://localhost:8888/docs"],["Live Events","GET /api/events (SSE)"],["Snapshots","GET /api/snapshots"],["Rollback","POST /api/rollback"],["Diff","GET /api/contract/diff"]];
  ctrls.forEach(c=>{h+='<div class="ctrl-row"><span class="ctrl-label">'+c[0]+'</span><span class="ctrl-val">'+c[1]+'</span></div>';});
  h+='</div></div>';
  return h;
}

function buildSplit(s){
  let h='<div class="slide-header"><h2>'+esc(s.title)+'</h2><span class="sub">'+esc(s.subtitle||'')+'</span></div>';
  h+='<div class="split">';
  // LEFT
  h+='<div class="panel panel-left"><div class="panel-label">'+esc(s.left_label||'README.md')+'</div><div class="panel-body">';
  if(s.is_prompt) h+='<div class="prompt-input">'+esc(s.left_content||s.subtitle)+'</div>';
  else h+=fmtReadme(s.left_content||'',s.left_highlight||'');
  h+='</div></div>';
  // RIGHT
  h+='<div class="panel panel-right"><div class="panel-label">'+esc(s.right_label||'VALIDATION')+'</div><div class="panel-body">';
  if(s.right_lines)(s.right_lines).forEach(l=>{
    let cls='';
    if(l.startsWith('[ACTOR: script'))cls='style="color:#34d399;font-weight:700"';
    else if(l.startsWith('[ACTOR: llm'))cls='style="color:#60a5fa;font-weight:700"';
    else if(l.startsWith('[ACTOR: human'))cls='style="color:#fbbf24;font-weight:700"';
    else if(l.startsWith('APPROV'))cls='style="color:#34d399;font-weight:700;font-size:16px"';
    else if(l.includes('-->'))cls='style="color:#818cf8;font-family:monospace"';
    else if(l.startsWith('  '))cls='style="font-family:monospace;font-size:13px;color:#cbd5e1"';
    else if(l.includes('[V]'))cls='style="color:#34d399"';
    h+='<div '+cls+'>'+esc(l)+'</div>';
  });
  // CHECKS
  if(s.checks&&s.checks.length){
    h+='</div><div class="checks"><div class="checks-title">VALIDATION</div>';
    s.checks.forEach(c=>{
      const ic=c.status==='pass'?'V':c.status==='fail'?'X':'?';
      h+='<div class="chk"><span class="chk-icon '+c.status+'">'+ic+'</span><span class="chk-label">'+esc(c.label)+'</span></div>';
      if(c.detail)h+='<div class="chk-detail">'+esc(c.detail)+'</div>';
    });
  }
  h+='</div></div></div>';
  return h;
}

function fmtReadme(raw,hl){
  if(!raw)return '<div style="color:#64748b;text-align:center;padding:40px">---</div>';
  let lines=raw.split('\n'),o='',inH=false;
  for(let ln of lines){
    let t=esc(ln);
    if(/^#{1,3} /.test(ln))t='<span class="md-h">'+t+'</span>';
    else if(/^```.*markpact:/.test(ln)){
      const k=(ln.match(/markpact:(\w+)/)||[])[1]||'';
      t=t.replace(/markpact:\S+/,'<span class="md-kind">$&</span>');
      t='<span class="md-fence">'+t+'</span>';
      if(hl&&(hl==='all'||hl===k)){inH=true;t='<div class="hl">'+t;}
    }
    else if(/^```\s*$/.test(ln)){t='<span class="md-fence">'+t+'</span>';if(inH){t+='</div>';inH=false;}}
    else if(/^```/.test(ln))t='<span class="md-fence">'+t+'</span>';
    if(/actor: human/.test(ln))t=t.replace(/actor: human/,'<span class="md-human">actor: human</span>');
    else if(/actor: llm/.test(ln))t=t.replace(/actor: llm/,'<span class="md-llm">actor: llm</span>');
    else if(/actor: script/.test(ln))t=t.replace(/actor: script/,'<span class="md-script">actor: script</span>');
    o+=t+'\n';
  }
  return o;
}

function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function go(i){if(i<0||i>=S.length)return;document.querySelectorAll('.slide').forEach(s=>s.classList.remove('active'));document.getElementById('s'+i).classList.add('active');vis.add(i);cur=i;upd();}
function toggleAuto(){auto=!auto;document.getElementById('abtn').classList.toggle('on',auto);document.getElementById('abtn').textContent=auto?'|| Pause':'> Auto';if(auto)timer=setInterval(()=>{if(cur<S.length-1)go(cur+1);else toggleAuto();},5000);else clearInterval(timer);}
function upd(){document.getElementById('ctr').textContent=(cur+1)+'/'+S.length;document.getElementById('prog').style.width=((cur+1)/S.length*100)+'%';document.querySelectorAll('.dot').forEach((d,i)=>{d.className='dot'+(i===cur?' a':vis.has(i)?' v':'');});}
document.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key===' '){e.preventDefault();go(cur+1);}if(e.key==='ArrowLeft'){e.preventDefault();go(cur-1);}if(e.key==='a')toggleAuto();});
render();
"""


# ── Public API ───────────────────────────────────────────────────────────


def render_html(report: ReportData, path: Path, **kwargs) -> Path:
    """Render a ReportData object to an HTML slideshow file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    slides = _build_slides(report)
    js = JS.replace("__SLIDES__", json.dumps(slides, ensure_ascii=False))

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>marksync — {report.project_name}</title>
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

    path.write_text(html, encoding="utf-8")
    return path
