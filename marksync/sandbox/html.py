"""Sandbox HTML UI — separated for maintainability."""

SANDBOX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>marksync Sandbox</title>
<style>
  :root { --bg: #0d1117; --fg: #c9d1d9; --accent: #58a6ff; --green: #3fb950;
          --red: #f85149; --yellow: #d29922; --surface: #161b22; --border: #30363d;
          --code-bg: #1c2128; --font: 'Segoe UI', system-ui, sans-serif; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--fg); font-family: var(--font);
         display: flex; height: 100vh; overflow: hidden; }

  .sidebar { width: 280px; background: var(--surface); border-right: 1px solid var(--border);
             display: flex; flex-direction: column; flex-shrink: 0; }
  .sidebar h1 { padding: 16px; font-size: 18px; color: var(--accent);
                border-bottom: 1px solid var(--border); cursor:pointer; }
  .sidebar h1 span { color: var(--fg); font-weight: 300; }
  .example-list { flex: 1; overflow-y: auto; padding: 8px; }
  .example-item { padding: 10px 12px; border-radius: 6px; cursor: pointer;
                  margin-bottom: 4px; transition: background 0.15s; }
  .example-item:hover { background: var(--border); }
  .example-item.active { background: #1f6feb33; border-left: 3px solid var(--accent); }
  .example-item .name { font-weight: 600; font-size: 14px; }
  .example-item .meta { font-size: 12px; color: #8b949e; margin-top: 2px; }

  .status-bar { padding: 12px; border-top: 1px solid var(--border); font-size: 12px; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }
  .status-dot.ok { background: var(--green); }
  .status-dot.err { background: var(--red); }

  .main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  .toolbar { display: flex; gap: 8px; padding: 12px 16px; background: var(--surface);
             border-bottom: 1px solid var(--border); align-items: center; flex-wrap: wrap; }
  .toolbar .group { display: flex; gap: 6px; align-items: center; }
  .toolbar .sep { width: 1px; height: 24px; background: var(--border); margin: 0 4px; }

  .btn { padding: 6px 14px; border-radius: 6px; border: 1px solid var(--border);
         background: var(--surface); color: var(--fg); cursor: pointer; font-size: 13px;
         transition: all 0.15s; white-space: nowrap; }
  .btn:hover { border-color: var(--accent); color: var(--accent); }
  .btn.primary { background: #1f6feb; border-color: #1f6feb; color: #fff; }
  .btn.primary:hover { background: #388bfd; }
  .btn.danger { border-color: var(--red); color: var(--red); }
  .btn:disabled { opacity: 0.4; cursor: default; }

  .tabs { display: flex; border-bottom: 1px solid var(--border); background: var(--surface); }
  .tab { padding: 10px 20px; cursor: pointer; font-size: 13px; border-bottom: 2px solid transparent;
         transition: all 0.15s; color: #8b949e; }
  .tab:hover { color: var(--fg); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }

  .content { flex: 1; overflow: hidden; display: flex; }
  .panel { flex: 1; overflow-y: auto; padding: 16px; }
  .panel.hidden { display: none; }

  .block-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
                margin-bottom: 12px; overflow: hidden; }
  .block-header { display: flex; justify-content: space-between; align-items: center;
                  padding: 10px 14px; background: var(--code-bg); border-bottom: 1px solid var(--border); }
  .block-header .id { font-family: monospace; font-size: 13px; color: var(--accent); }
  .block-header .meta { font-size: 12px; color: #8b949e; }
  .block-body textarea { width: 100%; min-height: 120px; background: var(--bg); color: var(--fg);
                         border: none; padding: 12px 14px; font-family: 'Fira Code', 'Cascadia Code',
                         'JetBrains Mono', monospace; font-size: 13px; line-height: 1.5;
                         resize: vertical; outline: none; tab-size: 4; }
  .block-footer { display: flex; justify-content: space-between; align-items: center;
                  padding: 8px 14px; font-size: 12px; color: #8b949e; }

  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
  .badge.deps { background: #1f6feb33; color: var(--accent); }
  .badge.file { background: #3fb95033; color: var(--green); }
  .badge.run { background: #d2992233; color: var(--yellow); }

  #markdown-editor { width: 100%; height: 100%; background: var(--bg); color: var(--fg);
                     border: none; padding: 16px; font-family: 'Fira Code', monospace;
                     font-size: 13px; line-height: 1.6; resize: none; outline: none; tab-size: 4; }

  .orch-section { margin-bottom: 16px; }
  .orch-section h3 { font-size: 14px; margin-bottom: 8px; color: var(--accent); }
  .orch-item { padding: 6px 12px; background: var(--surface); border-radius: 4px;
               margin-bottom: 4px; font-size: 13px; font-family: monospace; }

  #log { background: var(--code-bg); padding: 12px; font-family: monospace; font-size: 12px;
         line-height: 1.6; white-space: pre-wrap; max-height: 200px; overflow-y: auto;
         border-radius: 6px; margin: 12px 16px; border: 1px solid var(--border); }
  .log-ok { color: var(--green); }
  .log-err { color: var(--red); }
  .log-info { color: var(--accent); }

  .empty { text-align: center; padding: 48px; color: #8b949e; }
  .empty h2 { margin-bottom: 8px; }
</style>
</head>
<body>

<div class="sidebar">
  <h1 onclick="navigateTo('')">marksync <span>sandbox</span></h1>
  <div class="example-list" id="examples"></div>
  <div class="status-bar" id="status-bar">
    <span class="status-dot err" id="status-dot"></span>
    <span id="status-text">Checking server...</span>
  </div>
</div>

<div class="main">
  <div class="toolbar" id="toolbar" style="display:none">
    <div class="group">
      <strong id="example-title" style="font-size:15px"></strong>
    </div>
    <div class="sep"></div>
    <div class="group">
      <button class="btn primary" onclick="pushToServer()">Push to Server</button>
      <button class="btn" onclick="navigateTo(currentExample+'/orchestrate')">Orchestration Plan</button>
      <button class="btn" onclick="saveMarkdown()">Save</button>
    </div>
  </div>

  <div class="tabs" id="tab-bar" style="display:none">
    <div class="tab" data-tab="blocks" onclick="navigateTo(currentExample+'/blocks')">Blocks</div>
    <div class="tab" data-tab="editor" onclick="navigateTo(currentExample+'/editor')">Markdown</div>
    <div class="tab" data-tab="orchestrate" onclick="navigateTo(currentExample+'/orchestrate')">Orchestrate</div>
    <div class="tab" data-tab="pipeline" onclick="navigateTo(currentExample+'/pipeline')">Pipeline</div>
    <div class="tab" data-tab="settings" onclick="navigateTo(currentExample+'/settings')">Settings</div>
  </div>

  <div class="content">
    <div class="panel" id="panel-welcome">
      <div class="empty">
        <h2>marksync Sandbox</h2>
        <p>Select an example from the sidebar to begin.</p>
        <p style="margin-top:12px;font-size:13px;color:#8b949e">
          Edit code blocks, push to sync server, orchestrate agents, run pipelines.
        </p>
      </div>
    </div>

    <div class="panel hidden" id="panel-blocks"></div>
    <div class="panel hidden" id="panel-editor">
      <textarea id="markdown-editor" spellcheck="false"></textarea>
    </div>
    <div class="panel hidden" id="panel-orchestrate"></div>
    <div class="panel hidden" id="panel-pipeline"></div>
    <div class="panel hidden" id="panel-settings"></div>
  </div>

  <div id="log"></div>
</div>

<script>
'use strict';

const TABS = ['blocks', 'editor', 'orchestrate', 'pipeline', 'settings'];
let currentExample = null;
let currentData = null;
let currentTab = 'blocks';
let _pipelineTimer = null;

// ── Logging helper ──────────────────────────────────────────────────

function _log(level, ...args) {
  const prefix = `[sandbox:${level}]`;
  if (level === 'error') console.error(prefix, ...args);
  else if (level === 'warn') console.warn(prefix, ...args);
  else if (level === 'debug') console.debug(prefix, ...args);
  else console.log(prefix, ...args);
}

function logMsg(type, msg) {
  const el = document.getElementById('log');
  const ts = new Date().toLocaleTimeString();
  const cls = type === 'ok' ? 'log-ok' : type === 'err' ? 'log-err' : 'log-info';
  el.innerHTML += `<span class="${cls}">[${ts}] ${escHtml(msg)}</span>\n`;
  el.scrollTop = el.scrollHeight;
  _log(type === 'err' ? 'error' : 'info', msg);
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── URL hash router ─────────────────────────────────────────────────
//
// Hash format:
//   #/              -> welcome
//   #/1             -> example 1, blocks tab
//   #/1/blocks      -> example 1, blocks tab
//   #/1/editor      -> example 1, markdown editor
//   #/1/orchestrate -> orchestration plan
//   #/1/pipeline    -> pipeline demos
//   #/1/settings    -> settings

function navigateTo(path) {
  _log('debug', 'navigateTo:', path);
  window.location.hash = '#/' + (path || '');
}

function parseHash() {
  const h = window.location.hash.replace(/^#\/?/, '');
  const parts = h.split('/').filter(Boolean);
  return { example: parts[0] || null, tab: parts[1] || 'blocks' };
}

async function handleRoute() {
  const { example, tab } = parseHash();
  _log('debug', 'handleRoute:', JSON.stringify({ example, tab, currentExample }));

  if (!example) {
    document.getElementById('toolbar').style.display = 'none';
    document.getElementById('tab-bar').style.display = 'none';
    showPanel('welcome');
    document.querySelectorAll('.example-item').forEach(e => e.classList.remove('active'));
    currentExample = null;
    currentTab = null;
    return;
  }

  if (example !== currentExample) {
    _log('info', 'Loading example:', example);
    await loadExample(example);
  }

  if (TABS.includes(tab)) {
    showTab(tab);
  }
}

window.addEventListener('hashchange', () => handleRoute());

// ── Init ────────────────────────────────────────────────────────────

async function init() {
  _log('info', 'Sandbox init');
  await loadExampleList();
  checkStatus();
  setInterval(checkStatus, 60000);

  if (!window.location.hash || window.location.hash === '#/' || window.location.hash === '#') {
    showPanel('welcome');
  } else {
    await handleRoute();
  }
  _log('info', 'Sandbox ready');
}

// ── Examples ────────────────────────────────────────────────────────

async function loadExampleList() {
  _log('debug', 'Loading example list');
  const res = await fetch('/api/examples');
  const data = await res.json();
  const el = document.getElementById('examples');
  el.innerHTML = data.examples.map(ex => `
    <div class="example-item" data-id="${ex.id}" onclick="navigateTo('${ex.id}/blocks')">
      <div class="name">${escHtml(ex.name)}</div>
      <div class="meta">examples/${ex.id}/README.md${ex.has_agents_yml ? ' &middot; agents.yml' : ''}</div>
    </div>
  `).join('');
  _log('info', 'Loaded ' + data.examples.length + ' examples');
}

async function loadExample(id) {
  _log('info', 'Fetching example:', id);
  try {
    const res = await fetch('/api/examples/' + id);
    if (!res.ok) { logMsg('err', 'Example ' + id + ' not found'); return; }
    currentData = await res.json();
    currentExample = id;
  } catch (e) {
    logMsg('err', 'Failed to load example ' + id + ': ' + e);
    return;
  }

  document.querySelectorAll('.example-item').forEach(e => e.classList.remove('active'));
  const item = document.querySelector('.example-item[data-id="' + id + '"]');
  if (item) item.classList.add('active');

  document.getElementById('toolbar').style.display = 'flex';
  document.getElementById('tab-bar').style.display = 'flex';
  document.getElementById('example-title').textContent = currentData.blocks.length
    ? 'Example ' + id + ' \u2014 ' + currentData.blocks.length + ' blocks'
    : 'Example ' + id;

  renderBlocks();
  document.getElementById('markdown-editor').value = currentData.markdown;
  logMsg('info', 'Loaded example ' + id + ': ' + currentData.blocks.length + ' blocks');
}

// ── Tab switching (visual only, then loads data) ────────────────────

function showPanel(name) {
  TABS.concat(['welcome']).forEach(function(id) {
    var el = document.getElementById('panel-' + id);
    if (el) el.classList.toggle('hidden', id !== name);
  });
}

function showTab(name) {
  _log('debug', 'showTab:', name);
  currentTab = name;

  document.querySelectorAll('.tab').forEach(function(t) {
    t.classList.toggle('active', t.dataset.tab === name);
  });

  showPanel(name);

  // Load tab data on demand — NO recursive calls back to switchTab
  if (name === 'orchestrate' && currentExample) loadOrchestratePlan();
  if (name === 'pipeline') loadPipeline();
  if (name === 'settings') loadSettings();
}

// ── Blocks ──────────────────────────────────────────────────────────

function renderBlocks() {
  var el = document.getElementById('panel-blocks');
  if (!currentData || !currentData.blocks.length) {
    el.innerHTML = '<div class="empty"><h2>No blocks found</h2></div>';
    return;
  }
  el.innerHTML = currentData.blocks.map(function(b, i) {
    var rows = Math.min(Math.max(b.content.split('\n').length, 3), 25);
    return '<div class="block-card">' +
      '<div class="block-header">' +
        '<span class="id">' + escHtml(b.block_id) + '</span>' +
        '<span class="meta"><span class="badge ' + b.kind + '">' + b.kind + '</span> ' +
        b.lang + ' &middot; L' + b.line_start + '-' + b.line_end + '</span>' +
      '</div>' +
      '<div class="block-body">' +
        '<textarea id="block-' + i + '" data-bid="' + escHtml(b.block_id) + '" rows="' + rows + '">' +
        escHtml(b.content) + '</textarea>' +
      '</div>' +
      '<div class="block-footer">' +
        '<span>sha: ' + b.sha256.slice(0,12) + (b.path ? ' &middot; ' + escHtml(b.path) : '') + '</span>' +
        '<button class="btn" onclick="saveBlock(' + i + ')">Save Block</button>' +
      '</div></div>';
  }).join('');
}

async function saveBlock(idx) {
  var ta = document.getElementById('block-' + idx);
  var bid = ta.dataset.bid;
  _log('info', 'Saving block:', bid);
  var res = await fetch('/api/examples/' + currentExample + '/blocks', {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({block_id: bid, content: ta.value}),
  });
  var data = await res.json();
  if (data.ok) {
    logMsg('ok', 'Block ' + bid + ' saved (' + data.size + ' chars)');
    await loadExample(currentExample);
  } else {
    logMsg('err', 'Save failed: ' + (data.detail || 'unknown error'));
  }
}

// ── Markdown ────────────────────────────────────────────────────────

async function saveMarkdown() {
  if (!currentExample) return;
  var md = document.getElementById('markdown-editor').value;
  _log('info', 'Saving markdown for', currentExample);
  var res = await fetch('/api/examples/' + currentExample + '/markdown', {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({markdown: md}),
  });
  var data = await res.json();
  if (data.ok) {
    logMsg('ok', 'Markdown saved (' + data.blocks + ' blocks, ' + data.chars + ' chars)');
    await loadExample(currentExample);
  }
}

// ── Push ─────────────────────────────────────────────────────────────

async function pushToServer() {
  if (!currentExample) return;
  logMsg('info', 'Pushing example ' + currentExample + ' to sync server...');
  var res = await fetch('/api/push/' + currentExample, {method: 'POST'});
  var data = await res.json();
  if (data.ok) {
    logMsg('ok', 'Pushed: ' + data.patches + ' patches, saved ' + data.bytes_saved + ' bytes');
  } else {
    logMsg('err', 'Push failed: ' + data.error);
  }
}

// ── Orchestration (loads data only, no tab switch) ──────────────────

async function loadOrchestratePlan() {
  if (!currentExample) return;
  var configPath = 'examples/' + currentExample + '/agents.yml';
  _log('debug', 'Loading orchestration plan:', configPath);
  var res = await fetch('/api/orchestrate/plan', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({config_path: configPath, dry_run: true}),
  });
  var data = await res.json();
  var el = document.getElementById('panel-orchestrate');

  if (data.detail) {
    el.innerHTML = '<div class="empty"><h2>No agents.yml</h2><p>' + escHtml(data.detail) + '</p></div>';
    return;
  }
  el.innerHTML =
    '<div class="orch-section"><h3>Agents (' + data.agents.length + ')</h3>' +
    data.agents.map(function(a) { return '<div class="orch-item">' + escHtml(a.name) + ': ' + a.role + (a.auto_edit ? ' (auto-edit)' : '') + '</div>'; }).join('') +
    '</div>' +
    '<div class="orch-section"><h3>Pipelines (' + data.pipelines.length + ')</h3>' +
    data.pipelines.map(function(p) { return '<div class="orch-item">' + escHtml(p.name) + ': ' + (p.stages.join(' &rarr; ') || '(steps-based)') + '</div>'; }).join('') +
    '</div>' +
    '<div class="orch-section"><h3>Routes (' + data.routes.length + ')</h3>' +
    data.routes.map(function(r) { return '<div class="orch-item">' + escHtml(r.pattern) + ' &rarr; ' + escHtml(r.agent) + '</div>'; }).join('') +
    '</div>' +
    '<div class="orch-section"><h3>DSL Commands</h3>' +
    data.dsl_commands.map(function(c) { return '<div class="orch-item">' + escHtml(c) + '</div>'; }).join('') +
    '</div>';
  _log('info', 'Orchestration plan loaded');
}

// ── Status (backend caches, poll every 60s) ─────────────────────────

async function checkStatus() {
  _log('debug', 'Checking server status');
  try {
    var res = await fetch('/api/status');
    var data = await res.json();
    var dot = document.getElementById('status-dot');
    var text = document.getElementById('status-text');
    if (data.server === 'connected') {
      dot.className = 'status-dot ok';
      text.textContent = 'Server: ' + data.blocks + ' blocks';
    } else {
      dot.className = 'status-dot err';
      text.textContent = 'Server: disconnected';
    }
  } catch (e) {
    document.getElementById('status-dot').className = 'status-dot err';
    document.getElementById('status-text').textContent = 'Sandbox error';
    _log('error', 'Status check failed:', e);
  }
}

// ── Settings ────────────────────────────────────────────────────────

async function loadSettings() {
  _log('debug', 'Loading settings');
  var res = await fetch('/api/settings');
  var data = await res.json();
  document.getElementById('panel-settings').innerHTML =
    '<div class="orch-section"><h3>Current Settings (from .env)</h3>' +
    Object.entries(data).map(function(kv) { return '<div class="orch-item">' + escHtml(kv[0]) + ' = ' + escHtml(kv[1]) + '</div>'; }).join('') +
    '</div>';
}

// ── Pipeline demos ──────────────────────────────────────────────────

async function loadPipeline() {
  _log('debug', 'Loading pipeline data');
  var el = document.getElementById('panel-pipeline');
  var scenData, taskData, runData;
  try {
    var results = await Promise.all([
      fetch('/api/pipeline/demo/scenarios'),
      fetch('/api/pipeline/tasks'),
      fetch('/api/pipeline/runs'),
    ]);
    scenData = await results[0].json();
    taskData = await results[1].json();
    runData = await results[2].json();
  } catch (e) {
    el.innerHTML = '<div class="empty"><h2>Pipeline API error</h2><p>' + escHtml(e) + '</p></div>';
    _log('error', 'Pipeline load failed:', e);
    return;
  }

  var html = '<div class="orch-section"><h3>Demo Scenarios</h3>' +
    '<p style="font-size:13px;color:#8b949e;margin-bottom:10px">' +
    'Each scenario mixes LLM, Script, and Human actors. Human steps block until you approve/reject.</p>';
  (scenData.scenarios || []).forEach(function(s) {
    var flow = s.steps.map(function(st) {
      var type = st.split(':')[0];
      var color = type==='llm'?'var(--accent)':type==='human'?'var(--yellow)':'var(--green)';
      return '<span style="color:' + color + '">' + escHtml(st) + '</span>';
    }).join(' &rarr; ');
    html += '<div class="block-card" style="margin-bottom:8px">' +
      '<div class="block-header"><span class="id">' + escHtml(s.name) + '</span>' +
      '<button class="btn primary" onclick="startDemo(\'' + s.id + '\')">Run Demo</button></div>' +
      '<div style="padding:10px 14px;font-size:13px"><div>' + escHtml(s.description) + '</div>' +
      '<div style="margin-top:6px;font-family:monospace;color:#8b949e">' + flow + '</div></div></div>';
  });
  html += '</div>';

  var pending = taskData.pending || [];
  if (pending.length) {
    html += '<div class="orch-section"><h3 style="color:var(--yellow)">Pending Human Tasks (' + pending.length + ')</h3>';
    pending.forEach(function(t) {
      html += '<div class="block-card" style="border-color:var(--yellow)">' +
        '<div class="block-header" style="background:#d2992215">' +
        '<span class="id">' + escHtml(t.step_name) + '</span>' +
        '<span class="meta">' + escHtml(t.task_type) + ' via ' + escHtml(t.channel) + ' &middot; ' + escHtml(t.id) + '</span></div>' +
        '<div style="padding:12px 14px">' +
        '<div style="font-size:14px;font-weight:600;margin-bottom:8px">' + escHtml(t.prompt) + '</div>' +
        '<div style="font-size:12px;color:#8b949e;margin-bottom:10px">Run: ' + escHtml(t.run_id) + '</div>' +
        (t.data && t.data.content ? '<pre style="background:var(--code-bg);padding:8px;border-radius:4px;font-size:12px;max-height:150px;overflow:auto;margin-bottom:10px">' + escHtml(String(t.data.content)) + '</pre>' : '') +
        '<div style="display:flex;gap:8px;align-items:center">' +
        '<button class="btn primary" onclick="resolveTask(\'' + t.id + '\',\'approve\')">Approve</button>' +
        '<button class="btn danger" onclick="resolveTask(\'' + t.id + '\',\'reject\')">Reject</button>' +
        '<input id="task-input-' + t.id + '" placeholder="Optional comment..." style="flex:1;padding:6px 10px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--fg);font-size:13px">' +
        '</div></div></div>';
    });
    html += '</div>';
  }

  var runs = runData.runs || [];
  if (runs.length) {
    html += '<div class="orch-section"><h3>Pipeline Runs (' + runs.length + ')</h3>';
    runs.slice().reverse().forEach(function(r) {
      var stColor = r.status==='completed'?'var(--green)':r.status==='failed'?'var(--red)':r.status==='blocked'?'var(--yellow)':'var(--fg)';
      html += '<div class="block-card"><div class="block-header">' +
        '<span class="id">' + escHtml(r.pipeline_name) + '</span>' +
        '<span style="color:' + stColor + ';font-weight:600;font-size:12px">' + r.status.toUpperCase() + '</span></div>' +
        '<div style="padding:10px 14px;font-size:12px">' +
        '<div style="color:#8b949e;margin-bottom:6px">' + escHtml(r.id) + (r.current_step_name ? ' &middot; at: ' + escHtml(r.current_step_name) : '') + '</div>' +
        '<div style="display:flex;gap:4px;flex-wrap:wrap">';
      r.steps.forEach(function(s, i) {
        var result = r.results[i];
        var st = result ? result.status : 'pending';
        var bg = st==='completed'?'#3fb95033':st==='failed'?'#f8514933':st==='running'?'#58a6ff33':st==='blocked'?'#d2992233':'var(--code-bg)';
        var fg = st==='completed'?'var(--green)':st==='failed'?'var(--red)':st==='running'?'var(--accent)':st==='blocked'?'var(--yellow)':'#8b949e';
        var icon = s.actor==='llm'?'\u{1F916}':s.actor==='human'?'\u{1F464}':'\u{2699}';
        html += '<div style="background:' + bg + ';color:' + fg + ';padding:4px 10px;border-radius:4px;font-family:monospace">' +
          icon + ' ' + escHtml(s.name) + (result ? ' (' + Math.round(result.duration_ms) + 'ms)' : '') + '</div>';
        if (i < r.steps.length - 1) html += '<div style="color:#8b949e;padding:4px 2px">&rarr;</div>';
      });
      html += '</div></div></div>';
    });
    html += '</div>';
  }

  el.innerHTML = html;

  clearInterval(_pipelineTimer);
  var hasActive = runs.some(function(r) { return r.status==='running' || r.status==='blocked'; });
  if (hasActive || pending.length) {
    _pipelineTimer = setInterval(function() {
      if (currentTab === 'pipeline') loadPipeline();
    }, 3000);
  }
  _log('info', 'Pipeline loaded:', runs.length, 'runs,', pending.length, 'pending tasks');
}

async function startDemo(scenario) {
  logMsg('info', 'Starting demo: ' + scenario + '...');
  _log('info', 'Starting demo scenario:', scenario);
  var res = await fetch('/api/pipeline/demo', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({scenario: scenario}),
  });
  var data = await res.json();
  if (data.run_id) {
    logMsg('ok', data.message);
    setTimeout(loadPipeline, 500);
  } else {
    logMsg('err', data.detail || 'Failed to start demo');
  }
}

async function resolveTask(taskId, action) {
  var input = document.getElementById('task-input-' + taskId);
  var comment = input ? input.value : '';
  _log('info', 'Resolving task:', taskId, action, comment);
  var res = await fetch('/api/pipeline/tasks/' + taskId, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: action, response: {comment: comment, reason: comment}, resolved_by: 'sandbox-user'}),
  });
  var data = await res.json();
  if (data.ok) {
    logMsg('ok', 'Task ' + taskId + ': ' + action);
    setTimeout(loadPipeline, 500);
  } else {
    logMsg('err', data.detail || 'Failed to resolve task');
  }
}

// ── Start ───────────────────────────────────────────────────────────
init();
</script>
</body>
</html>"""
