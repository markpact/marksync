"""Dashboard HTML — inline Preact SPA, no build step required."""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>marksync Dashboard</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:#0d1117; --bg2:#161b22; --bg3:#21262d; --border:#30363d;
    --text:#e6edf3; --muted:#8b949e; --green:#3fb950; --blue:#58a6ff;
    --yellow:#d29922; --red:#f85149; --purple:#bc8cff; --orange:#ffa657;
    --radius:8px; --mono:'JetBrains Mono','Fira Code',monospace;
  }
  body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px;height:100vh;overflow:hidden;}
  #root{display:flex;flex-direction:column;height:100vh;}
  .topbar{background:var(--bg2);border-bottom:1px solid var(--border);padding:0 16px;height:48px;display:flex;align-items:center;gap:12px;flex-shrink:0;}
  .topbar .logo{font-weight:700;color:var(--blue);}
  .badge{font-size:11px;padding:2px 8px;border-radius:10px;background:var(--bg3);color:var(--muted);}
  .live-badge{background:rgba(63,185,80,.15);color:var(--green);}
  .spacer{flex:1;}
  .tabs{display:flex;gap:2px;border-bottom:1px solid var(--border);background:var(--bg2);padding:0 16px;flex-shrink:0;}
  .tab{padding:10px 16px;cursor:pointer;border-bottom:2px solid transparent;color:var(--muted);font-size:13px;}
  .tab:hover{color:var(--text);}
  .tab.active{color:var(--blue);border-bottom-color:var(--blue);}
  .panel{flex:1;overflow-y:auto;padding:16px;}
  .card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:12px;overflow:hidden;}
  .card-header{padding:10px 14px;display:flex;align-items:center;gap:8px;cursor:pointer;border-bottom:1px solid var(--border);background:var(--bg3);}
  .card-body{padding:12px 14px;}
  pre{font-family:var(--mono);font-size:12px;white-space:pre-wrap;word-break:break-word;line-height:1.6;}
  .btn{padding:8px 16px;border-radius:var(--radius);border:none;cursor:pointer;font-size:13px;font-weight:500;}
  .btn:hover{opacity:.85;} .btn-primary{background:var(--blue);color:#fff;} .btn-success{background:var(--green);color:#000;}
  .btn-danger{background:var(--red);color:#fff;} .btn-muted{background:var(--bg3);color:var(--text);border:1px solid var(--border);}
  .chat-history{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px;}
  .chat-msg{max-width:80%;} .chat-msg.human{align-self:flex-end;} .chat-msg.llm,.chat-msg.system,.chat-msg.script{align-self:flex-start;}
  .chat-bubble{padding:10px 14px;border-radius:var(--radius);font-size:13px;line-height:1.5;}
  .human .chat-bubble{background:var(--blue);color:#fff;}
  .llm .chat-bubble{background:var(--bg3);border:1px solid var(--border);}
  .script .chat-bubble,.system .chat-bubble{background:var(--bg2);border:1px solid var(--border);color:var(--muted);font-family:var(--mono);font-size:12px;}
  .chat-actor{font-size:11px;color:var(--muted);margin-bottom:3px;}
  .chat-input-row{display:flex;gap:8px;padding:12px;border-top:1px solid var(--border);flex-shrink:0;}
  .chat-input{flex:1;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:10px 14px;color:var(--text);font-size:13px;outline:none;}
  .chat-input:focus{border-color:var(--blue);}
  .step-row{display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);}
  .step-row:last-child{border-bottom:none;} .step-icon{font-size:18px;width:28px;text-align:center;flex-shrink:0;}
  .step-info{flex:1;} .step-name{font-weight:600;font-size:13px;} .step-actor{font-size:11px;color:var(--muted);}
  table{width:100%;border-collapse:collapse;} th{text-align:left;padding:8px 12px;font-size:11px;color:var(--muted);text-transform:uppercase;border-bottom:1px solid var(--border);}
  td{padding:10px 12px;border-bottom:1px solid var(--border);font-size:13px;}
  .form-group{margin-bottom:16px;} label{display:block;font-size:12px;color:var(--muted);margin-bottom:6px;text-transform:uppercase;}
  textarea,input[type=text]{width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:10px 14px;color:var(--text);font-size:13px;outline:none;resize:vertical;}
  textarea:focus,input[type=text]:focus{border-color:var(--blue);}
  .two-col{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
  @media(max-width:900px){.two-col{grid-template-columns:1fr;}}
  ::-webkit-scrollbar{width:6px;} ::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px;}
  .progress-steps{list-style:none;} .progress-steps li{padding:8px 0;display:flex;gap:10px;align-items:flex-start;font-size:13px;}
  .progress-steps li .sn{color:var(--muted);font-family:var(--mono);width:24px;} .progress-steps li.done .sn{color:var(--green);} .progress-steps li.active .sn{color:var(--blue);}
</style>
</head>
<body>
<div id="root"></div>
<script type="module">
import { h, render } from 'https://esm.sh/preact@10';
import { useState, useEffect, useRef } from 'https://esm.sh/preact@10/hooks';
import { html } from 'https://esm.sh/htm@3/preact';

const api = {
  get: url => fetch(url).then(r => r.json()),
  post: (url, b) => fetch(url, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}).then(r=>r.json()),
  put: (url, b) => fetch(url, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}).then(r=>r.json()),
};

function Dot({s}) {
  const c = {ok:'var(--green)',running:'var(--blue)',pending:'var(--yellow)',error:'var(--red)',unknown:'var(--muted)',deployed:'var(--green)',connected:'var(--green)',disconnected:'var(--red)'};
  return html`<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${c[s]||c.unknown};margin-right:6px;"></span>`;
}

function BlockCard({block, onEdit}) {
  const [open, setOpen] = useState(true);
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(block.content);
  const [saving, setSaving] = useState(false);
  const kc = {intent:'#bc8cff',pipeline:'#58a6ff',orchestration:'#79c0ff',deploy:'#ffa657',log:'#8b949e',state:'#3fb950',history:'#d29922',pattern:'#e3b341',config:'#58a6ff',deps:'#8b949e',file:'#58a6ff',run:'#ffa657'};
  async function save() {
    setSaving(true);
    await api.put('/api/contract/block', {block_id:block.block_id, content});
    setSaving(false); setEditing(false);
    if (onEdit) onEdit(block.block_id, content);
  }
  return html`<div class="card">
    <div class="card-header" onClick=${()=>!editing&&setOpen(o=>!o)}>
      <span style="color:${kc[block.kind]||'#58a6ff'};font-family:var(--mono);font-size:12px;">markpact:${block.kind}</span>
      ${block.meta&&html`<span style="font-size:11px;color:var(--muted);">${block.meta}</span>`}
      ${block.path&&html`<span style="font-size:11px;color:var(--orange);">${block.path}</span>`}
      <span style="flex:1;"></span>
      <span style="font-size:11px;color:var(--muted);">${block.sha256?.slice(0,8)}</span>
      ${!editing&&html`<button class="btn btn-muted" style="padding:2px 8px;font-size:11px;margin-left:8px;" onClick=${e=>{e.stopPropagation();setEditing(true);setOpen(true);}}>Edit</button>`}
    </div>
    ${open&&html`<div class="card-body">
      ${editing?html`
        <textarea rows="8" style="width:100%;font-family:var(--mono);font-size:12px;" value=${content} onInput=${e=>setContent(e.target.value)}></textarea>
        <div style="display:flex;gap:8px;margin-top:8px;">
          <button class="btn btn-primary" onClick=${save} disabled=${saving}>${saving?'Saving…':'Save'}</button>
          <button class="btn btn-muted" onClick=${()=>{setEditing(false);setContent(block.content);}}>Cancel</button>
        </div>`
      :html`<pre>${block.content||html`<span style="color:var(--muted)">(empty)</span>`}</pre>`}
    </div>`}
  </div>`;
}

function ContractPanel({contractPath}) {
  const [contract, setContract] = useState(null);
  const [loading, setLoading] = useState(false);
  const [path, setPath] = useState(contractPath||'README.md');
  async function load() {
    setLoading(true);
    try { setContract(await api.get('/api/contract?path='+encodeURIComponent(path))); }
    catch(e){} finally { setLoading(false); }
  }
  useEffect(()=>{load();},[path]);
  return html`<div>
    <div style="display:flex;gap:8px;margin-bottom:16px;">
      <input type="text" value=${path} onInput=${e=>setPath(e.target.value)} style="flex:1;" placeholder="Path to README.md" />
      <button class="btn btn-primary" onClick=${load}>Load</button>
      <button class="btn btn-muted" onClick=${load}>↻</button>
    </div>
    ${loading&&html`<div style="color:var(--muted);text-align:center;padding:32px;">Loading…</div>`}
    ${contract&&!loading&&html`<div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">${contract.path} — ${contract.blocks?.length||0} blocks</div>
      ${(contract.blocks||[]).map(b=>html`<${BlockCard} key=${b.block_id} block=${b} onEdit=${()=>load()} />`)}
    </div>`}
    ${!contract&&!loading&&html`<div style="color:var(--muted);text-align:center;padding:32px;">No contract loaded</div>`}
  </div>`;
}

function ConversationPanel({contractPath}) {
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [voiceOn, setVoiceOn] = useState(false);
  const bottomRef = useRef(null);
  const recRef = useRef(null);
  async function loadHist() {
    const d = await api.get('/api/conversation/history?contract_path='+encodeURIComponent(contractPath||'README.md'));
    setHistory(d.history||[]);
  }
  useEffect(()=>{loadHist();},[contractPath]);
  useEffect(()=>{bottomRef.current?.scrollIntoView({behavior:'smooth'});},[history]);
  async function send() {
    if (!input.trim()||sending) return;
    const msg = input.trim(); setInput(''); setSending(true);
    setHistory(h=>[...h,{actor:'human',action:'message',data:msg,ts:new Date().toISOString()}]);
    const res = await api.post('/api/conversation/message',{message:msg,sender:'human',contract_path:contractPath});
    if (res.reply) setHistory(h=>[...h,{actor:'llm',action:'message',data:res.reply,ts:new Date().toISOString()}]);
    setSending(false);
  }
  function toggleVoice() {
    if (voiceOn) { recRef.current?.stop(); setVoiceOn(false); return; }
    const SR = window.SpeechRecognition||window.webkitSpeechRecognition;
    if (!SR) { alert('Speech API not supported'); return; }
    const r = new SR(); r.continuous=true; r.interimResults=true;
    r.onresult = e => setInput(Array.from(e.results).map(r=>r[0].transcript).join(''));
    r.onend = ()=>setVoiceOn(false); r.start(); recRef.current=r; setVoiceOn(true);
  }
  const ai = {human:'👤',llm:'🤖',script:'⚙️',pactown:'🚀',system:'🔧'};
  return html`<div style="display:flex;flex-direction:column;height:calc(100vh - 130px);">
    <div class="chat-history">
      ${history.length===0&&html`<div style="color:var(--muted);text-align:center;padding:32px;">No conversation yet</div>`}
      ${history.map((m,i)=>html`<div key=${i} class=${'chat-msg '+(m.actor||'system')}>
        <div class="chat-actor">${ai[m.actor]||'●'} ${m.actor} · ${m.action} · ${(m.ts||'').slice(11,19)}</div>
        <div class="chat-bubble">${typeof m.data==='string'?m.data:JSON.stringify(m.data,null,2)}</div>
      </div>`)}
      <div ref=${bottomRef} />
    </div>
    <div class="chat-input-row">
      <button class=${'btn '+(voiceOn?'btn-danger':'btn-muted')} onClick=${toggleVoice}>${voiceOn?'⏹':'🎤'}</button>
      <input class="chat-input" placeholder="Type or speak…" value=${input}
        onInput=${e=>setInput(e.target.value)} onKeyDown=${e=>e.key==='Enter'&&!e.shiftKey&&send()} />
      <button class="btn btn-primary" onClick=${send} disabled=${sending}>${sending?'…':'Send ➤'}</button>
    </div>
  </div>`;
}

function PipelinePanel() {
  const [runs, setRuns] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  async function load() {
    setLoading(true);
    try {
      const [r,t] = await Promise.all([api.get('/api/pipeline/runs'),api.get('/api/pipeline/tasks/pending')]);
      setRuns(r.runs||[]); setTasks(t.tasks||[]);
    } catch(e){} finally{setLoading(false);}
  }
  useEffect(()=>{load();const id=setInterval(load,5000);return()=>clearInterval(id);},[]);
  async function resolve(taskId,action) {
    await api.post('/api/pipeline/approve',{run_id:'',task_id:taskId,action,by:'human'});
    load();
  }
  const si={pending:'⬚',running:'⏳',completed:'✅',failed:'❌',blocked:'⏳',skipped:'⏭'};
  const ai={llm:'🤖',script:'⚙️',human:'👤'};
  return html`<div>
    ${tasks.length>0&&html`<div class="card" style="border-color:var(--yellow);">
      <div class="card-header" style="background:rgba(210,153,34,.1);">
        <span style="color:var(--yellow);">⏳ AWAITING APPROVAL (${tasks.length})</span>
      </div>
      <div class="card-body">
        ${tasks.map(t=>html`<div key=${t.id} style="padding:10px 0;border-bottom:1px solid var(--border);">
          <div style="font-weight:600;">${t.step_name}</div>
          <div style="color:var(--muted);font-size:12px;margin:4px 0;">${t.prompt}</div>
          <div style="display:flex;gap:8px;margin-top:8px;">
            <button class="btn btn-success" onClick=${()=>resolve(t.id,'approve')}>✅ Approve</button>
            <button class="btn btn-danger" onClick=${()=>resolve(t.id,'reject')}>❌ Reject</button>
          </div>
        </div>`)}
      </div>
    </div>`}
    ${loading&&runs.length===0&&html`<div style="color:var(--muted);text-align:center;padding:32px;">Loading…</div>`}
    ${!loading&&runs.length===0&&html`<div style="color:var(--muted);text-align:center;padding:32px;">No pipeline runs yet. Use <code>marksync create</code> to start.</div>`}
    ${runs.map(run=>html`<div key=${run.id} class="card">
      <div class="card-header">
        <span style="font-weight:600;">${run.pipeline_name}</span>
        <span class="badge">#${(run.id||'').slice(0,8)}</span>
        <span style="font-size:12px;color:${run.status==='completed'?'var(--green)':run.status==='failed'?'var(--red)':'var(--yellow)'};">${run.status}</span>
      </div>
      <div class="card-body">
        ${(run.results||[]).map((res,i)=>html`<div key=${i} class="step-row">
          <div class="step-icon">${si[res.status]||'⬚'}</div>
          <div class="step-info">
            <div class="step-name">${res.step_name}</div>
            <div class="step-actor">${ai[res.actor]||'●'} ${res.actor} ${res.duration_ms?'· '+res.duration_ms.toFixed(0)+'ms':''}</div>
          </div>
        </div>`)}
      </div>
    </div>`)}
  </div>`;
}

function DeployPanel({contractPath}) {
  const [status, setStatus] = useState(null);
  const [sync, setSync] = useState(null);
  async function load() {
    const [s,ss] = await Promise.all([
      api.get('/api/deploy/status?contract_path='+encodeURIComponent(contractPath||'README.md')),
      api.get('/api/sync/status'),
    ]);
    setStatus(s); setSync(ss);
  }
  useEffect(()=>{load();const id=setInterval(load,10000);return()=>clearInterval(id);},[]);
  return html`<div>
    <div class="two-col">
      <div class="card">
        <div class="card-header"><span>🔄 Sync Server</span></div>
        <div class="card-body">
          ${sync?html`<div><${Dot} s=${sync.server==='connected'?'ok':'error'} />${sync.server} — ${sync.uri||''}</div>
            ${sync.blocks!==undefined&&html`<div style="color:var(--muted);font-size:12px;margin-top:6px;">${sync.blocks} blocks</div>`}`
          :html`<div style="color:var(--muted);">Loading…</div>`}
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span>🚀 Pactown</span></div>
        <div class="card-body">
          ${status?html`<div><${Dot} s=${status.status} />${status.status}</div>
            ${status.config&&html`<div style="color:var(--muted);font-size:12px;margin-top:6px;">${status.config}</div>`}
            ${status.error&&html`<div style="color:var(--red);font-size:12px;margin-top:6px;">${status.error}</div>`}`
          :html`<div style="color:var(--muted);">Loading…</div>`}
        </div>
      </div>
    </div>
    ${status?.output&&html`<div class="card"><div class="card-header"><span>📋 Output</span></div>
      <div class="card-body"><pre style="max-height:300px;overflow-y:auto;">${status.output}</pre></div>
    </div>`}
  </div>`;
}

const STEPS = [
  'Human prompt recorded','LLM analyzing intent…','Generating pipeline YAML…',
  'LLM generating code…','Generating Pactown config…','Writing README.md…',
];

function CreatePanel({onCreated}) {
  const [prompt, setPrompt] = useState('');
  const [outDir, setOutDir] = useState('');
  const [useLlm, setUseLlm] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [done, setDone] = useState([]);

  async function create() {
    if (!prompt.trim()||busy) return;
    setBusy(true); setResult(null); setDone([]);
    let i=0;
    const tick = setInterval(()=>{ if(i<STEPS.length){setDone(d=>[...d,i]);i++;}else clearInterval(tick); },500);
    try {
      const res = await api.post('/api/create',{prompt:prompt.trim(),output_dir:outDir.trim()||null,use_llm:useLlm});
      clearInterval(tick); setDone(STEPS.map((_,j)=>j)); setResult(res);
      if (res.ok&&onCreated) onCreated(res.path);
    } catch(e) { clearInterval(tick); setResult({ok:false,error:String(e)}); }
    finally { setBusy(false); }
  }

  return html`<div style="max-width:640px;">
    <h2 style="margin-bottom:16px;font-size:14px;color:var(--muted);text-transform:uppercase;">Create New Contract</h2>
    <div class="form-group">
      <label>What do you want to build?</label>
      <textarea rows="4" placeholder="e.g. REST API for order management with AI validation and manager approval"
        value=${prompt} onInput=${e=>setPrompt(e.target.value)} disabled=${busy} />
    </div>
    <div class="form-group">
      <label>Output directory (optional)</label>
      <input type="text" placeholder="./contracts/my-project" value=${outDir} onInput=${e=>setOutDir(e.target.value)} disabled=${busy} />
    </div>
    <div class="form-group" style="display:flex;align-items:center;gap:10px;">
      <input type="checkbox" id="llm" checked=${useLlm} onChange=${e=>setUseLlm(e.target.checked)} disabled=${busy} />
      <label for="llm" style="text-transform:none;font-size:13px;color:var(--text);margin:0;">Use LLM for analysis and code generation</label>
    </div>
    <button class="btn btn-primary" onClick=${create} disabled=${busy||!prompt.trim()} style="margin-bottom:20px;">
      ${busy?'Creating…':'✨ Create Contract'}
    </button>

    ${busy&&html`<ul class="progress-steps">
      ${STEPS.map((s,i)=>html`<li key=${i} class=${done.includes(i)?'done':i===done.length?'active':''}>
        <span class="sn">${done.includes(i)?'✓':i===done.length?'▶':String(i+1)}</span>
        <span>${s}</span>
      </li>`)}
    </ul>`}

    ${result&&html`<div class="card" style="border-color:${result.ok?'var(--green)':'var(--red)'};">
      <div class="card-header"><span>${result.ok?'✅ Contract Created':'❌ Failed'}</span></div>
      <div class="card-body">
        ${result.ok?html`
          <div><strong>${result.name}</strong></div>
          <div style="color:var(--muted);font-size:12px;margin:6px 0;">${result.path}</div>
          <div style="font-size:12px;">Service: <span style="color:var(--blue);">${result.service_type}</span> · Actors: ${(result.actors||[]).join(', ')}</div>
          <div style="font-size:12px;margin-top:6px;">Blocks: ${(result.blocks||[]).join(', ')}</div>
        `:html`<div style="color:var(--red);">${result.error}</div>`}
      </div>
    </div>`}
  </div>`;
}

function App() {
  const [tab, setTab] = useState('contract');
  const [contractPath, setContractPath] = useState('README.md');
  const [liveEvents, setLiveEvents] = useState(0);
  const [syncOk, setSyncOk] = useState(false);

  useEffect(()=>{
    const es = new EventSource('/api/events');
    es.onmessage = e => {
      const d = JSON.parse(e.data);
      setLiveEvents(n=>n+1);
      if (d.type==='contract_created'&&d.path) setContractPath(d.path);
    };
    es.onerror = ()=>setSyncOk(false);
    es.onopen = ()=>setSyncOk(true);
    return ()=>es.close();
  },[]);

  const tabs = [
    {id:'contract',label:'📄 Contract'},
    {id:'conversation',label:'💬 Conversation'},
    {id:'pipeline',label:'📊 Pipeline'},
    {id:'deploy',label:'🚀 Deploy'},
    {id:'create',label:'✨ Create'},
  ];

  return html`<div id="root">
    <div class="topbar">
      <span class="logo">⚡ marksync</span>
      <span class="badge">Dashboard</span>
      <span class=${'badge '+(syncOk?'live-badge':'')}>${syncOk?'● LIVE':'○ OFFLINE'}</span>
      ${liveEvents>0&&html`<span class="badge" style="color:var(--purple);">${liveEvents} events</span>`}
      <span class="spacer"></span>
      <span style="font-size:11px;color:var(--muted);">${contractPath}</span>
    </div>
    <div class="tabs">
      ${tabs.map(t=>html`<div key=${t.id} class=${'tab '+(tab===t.id?'active':'')} onClick=${()=>setTab(t.id)}>${t.label}</div>`)}
    </div>
    <div class="panel">
      ${tab==='contract'&&html`<${ContractPanel} contractPath=${contractPath} />`}
      ${tab==='conversation'&&html`<${ConversationPanel} contractPath=${contractPath} />`}
      ${tab==='pipeline'&&html`<${PipelinePanel} />`}
      ${tab==='deploy'&&html`<${DeployPanel} contractPath=${contractPath} />`}
      ${tab==='create'&&html`<${CreatePanel} onCreated=${p=>{ setContractPath(p); setTab('contract'); }} />`}
    </div>
  </div>`;
}

render(html`<${App} />`, document.getElementById('root'));
</script>
</body>
</html>
"""
