"""
HTML Reporter — GraphQL Schema Explorer (SPA style)
Smart search: by name / arguments / fields with checkboxes.
"""

import json
from pathlib import Path
from datetime import datetime


def write_html(result: dict, path: Path, apk_name: str = "unknown.apk"):
    ops = result.get("operations", [])
    types = result.get("types", [])
    strategy = result.get("strategy", "unknown")

    for op in ops:
        for var in op.get("variables", []):
            var["required"] = var.get("type", "").endswith("!")

    endpoints = result.get("endpoints", [])

    data_json = json.dumps({
        "apk": apk_name,
        "strategy": strategy,
        "timestamp": datetime.now().isoformat(),
        "operations": ops,
        "types": types,
        "endpoints": endpoints,
    }, ensure_ascii=False)

    queries      = [o for o in ops if o["type"] == "query"]
    mutations    = [o for o in ops if o["type"] == "mutation"]
    subscriptions = [o for o in ops if o["type"] == "subscription"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>apka-P :: {_e(apk_name)}</title>
<style>
:root {{
  --bg: #0d1117;
  --sidebar: #161b22;
  --surface: #1c2128;
  --surface2: #22272e;
  --border: #2d333b;
  --text: #cdd9e5;
  --muted: #636e7b;
  --query: #388bfd;
  --mutation: #f78166;
  --subscription: #3fb950;
  --type-color: #bc8cff;
  --required: #f78166;
  --tag-bg: #22272e;
  --highlight: #e3b341;
  --radius: 6px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 13px;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}}

/* ── Top bar ── */
.topbar {{
  background: var(--sidebar);
  border-bottom: 1px solid var(--border);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-shrink: 0;
}}
.logo {{ font-size: 15px; font-weight: 700; color: #bc8cff; white-space: nowrap; }}
.apk-pill {{
  background: var(--surface2);
  border: 1px solid var(--border);
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}}
.tab-bar {{ display: flex; gap: 2px; margin-left: auto; }}
.tab-btn {{
  background: none;
  border: 1px solid transparent;
  color: var(--muted);
  padding: 5px 12px;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}}
.tab-btn:hover {{ color: var(--text); background: var(--surface2); }}
.tab-btn.active {{ color: var(--text); background: var(--surface2); border-color: var(--border); }}
.count-badge {{
  display: inline-block;
  padding: 1px 6px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 700;
  margin-left: 4px;
}}
.cb-query {{ background:#0d2149; color:var(--query); }}
.cb-mutation {{ background:#3d1a17; color:var(--mutation); }}
.cb-subscription {{ background:#0d2818; color:var(--subscription); }}

/* ── Layout ── */
.layout {{ display: flex; flex: 1; overflow: hidden; }}

/* ── Sidebar ── */
.sidebar {{
  width: 240px;
  flex-shrink: 0;
  background: var(--sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}}

/* ── Smart Search ── */
.search-area {{
  border-bottom: 1px solid var(--border);
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}}
.search-input-wrap {{ position: relative; }}
.search-input-wrap input {{
  width: 100%;
  background: var(--surface2);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px 30px 6px 10px;
  border-radius: var(--radius);
  font-size: 12px;
  outline: none;
}}
.search-input-wrap input:focus {{ border-color: #bc8cff55; }}
.search-clear {{
  position: absolute;
  right: 8px; top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
  cursor: pointer;
  font-size: 14px;
  display: none;
  line-height: 1;
  background: none;
  border: none;
  padding: 0;
}}
.search-clear.visible {{ display: block; }}

/* search scope checkboxes */
.search-scope {{
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}}
.scope-chip {{
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: var(--surface2);
  cursor: pointer;
  font-size: 11px;
  color: var(--muted);
  user-select: none;
  transition: all 0.1s;
}}
.scope-chip input {{ display: none; }}
.scope-chip.checked {{
  border-color: #bc8cff66;
  background: #2a1f3d;
  color: var(--type-color);
}}
.scope-chip .dot {{
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--muted);
  flex-shrink: 0;
}}
.scope-chip.checked .dot {{ background: var(--type-color); }}

/* match count */
.match-info {{
  font-size: 10px;
  color: var(--muted);
  padding: 0 2px;
  min-height: 14px;
}}
.match-info .hit {{ color: var(--type-color); font-weight: 600; }}
.match-info .scope-tag {{
  background: #2a1f3d;
  color: var(--type-color);
  padding: 0 5px;
  border-radius: 3px;
  font-size: 10px;
  margin-left: 2px;
}}

/* ── Op list ── */
.op-list {{ flex: 1; overflow-y: auto; padding: 6px 0; }}
.op-item {{
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  border-left: 2px solid transparent;
  transition: background 0.1s;
}}
.op-item:hover {{ background: var(--surface2); }}
.op-item.active {{ background: var(--surface); border-left-color: #bc8cff; }}
.op-item.hidden {{ display: none; }}
.op-dot {{ width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; margin-top: 4px; }}
.d-query {{ background: var(--query); }}
.d-mutation {{ background: var(--mutation); }}
.d-subscription {{ background: var(--subscription); }}
.op-item-body {{ flex: 1; min-width: 0; }}
.op-item-name {{
  font-size: 12px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.op-item-hint {{
  font-size: 10px;
  color: var(--muted);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
mark {{
  background: #e3b34133;
  color: var(--highlight);
  border-radius: 2px;
  padding: 0 1px;
}}

/* ── Main panel ── */
.main {{ flex: 1; overflow-y: auto; }}
.empty-state {{
  display: flex; align-items: center; justify-content: center;
  height: 100%; color: var(--muted); font-size: 14px;
}}
.detail {{ padding: 24px 28px; max-width: 900px; }}
.detail-header {{
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 22px; flex-wrap: wrap;
}}
.type-badge {{
  font-size: 11px; font-weight: 700; padding: 3px 9px;
  border-radius: 4px; text-transform: lowercase; letter-spacing: 0.3px;
}}
.tb-query {{ background:#0d2149; color:var(--query); }}
.tb-mutation {{ background:#3d1a17; color:var(--mutation); }}
.tb-subscription {{ background:#0d2818; color:var(--subscription); }}
.detail-name {{ font-size: 20px; font-weight: 700; color: var(--text); }}

.section-block {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 16px;
  overflow: hidden;
}}
.section-label {{
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.8px; color: var(--muted);
  padding: 10px 14px 8px;
  border-bottom: 1px solid var(--border);
  background: var(--surface2);
}}

.args-table {{ width: 100%; border-collapse: collapse; }}
.args-table th {{
  text-align: left; padding: 8px 14px;
  font-size: 11px; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.5px;
  border-bottom: 1px solid var(--border);
}}
.args-table td {{ padding: 8px 14px; border-bottom: 1px solid #22272e; font-size: 13px; }}
.args-table tr:last-child td {{ border-bottom: none; }}
.arg-name {{ color: var(--text); font-family: monospace; }}
.arg-type {{ color: var(--type-color); font-family: monospace; }}
.arg-required {{ color: var(--required); font-size: 11px; font-weight: 600; }}
.arg-optional {{ color: var(--muted); font-size: 11px; }}
.no-args {{ padding: 12px 14px; color: var(--muted); font-style: italic; font-size: 12px; }}

.fields-wrap {{ padding: 12px 14px; display: flex; flex-wrap: wrap; gap: 6px; }}
.field-tag {{
  background: var(--tag-bg); border: 1px solid var(--border);
  border-radius: 4px; padding: 3px 9px;
  font-family: monospace; font-size: 12px; color: var(--text);
}}
.field-tag.nested {{ color: var(--type-color); border-color: #3d2f5c; background: #1a1230; }}
.no-fields {{ padding: 12px 14px; color: var(--muted); font-style: italic; font-size: 12px; }}

.raw-wrap {{ position: relative; }}
.copy-btn {{
  position: absolute; top: 10px; right: 10px;
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--muted); padding: 4px 10px; border-radius: 4px;
  cursor: pointer; font-size: 11px; z-index: 2;
}}
.copy-btn:hover {{ color: var(--text); }}
pre {{
  margin: 0; padding: 14px;
  font-family: 'JetBrains Mono','Fira Code',monospace;
  font-size: 12px; line-height: 1.7; overflow-x: auto;
  color: var(--text); background: var(--bg);
}}
.kw {{ color: #f47067; }}
.var-hl {{ color: #e3b341; }}
.type-hl {{ color: var(--type-color); }}
.punct {{ color: #3fb950; }}
.frag-hl {{ color: #f0883e; }}


.endpoint-bar {{
  background: var(--sidebar);
  border-bottom: 1px solid var(--border);
  padding: 6px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--muted);
  flex-shrink: 0;
}}
.endpoint-bar.hidden {{ display: none; }}
.endpoint-pill {{
  color: #58a6ff;
  font-family: monospace;
  font-size: 11px;
  text-decoration: none;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
}}
.endpoint-pill:hover {{ text-decoration: underline; color: #79c0ff; }}
::-webkit-scrollbar {{ width: 5px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
</style>
</head>
<body>

<div class="topbar">
  <div class="logo">apka-P</div>
  <div class="apk-pill">📦 {_e(apk_name)}</div>
  <div class="tab-bar">
    <button class="tab-btn active" data-tab="all">All <span class="count-badge" style="background:#2d2d3d;color:#cdd9e5">{len(ops)}</span></button>
    <button class="tab-btn" data-tab="query">Queries <span class="count-badge cb-query">{len(queries)}</span></button>
    <button class="tab-btn" data-tab="mutation">Mutations <span class="count-badge cb-mutation">{len(mutations)}</span></button>
    <button class="tab-btn" data-tab="subscription">Subscriptions <span class="count-badge cb-subscription">{len(subscriptions)}</span></button>
  </div>
</div>

<div class="endpoint-bar" id="endpoint-bar">
  <span>⚡ Endpoint:</span>
  <div id="endpoint-pills" style="display:flex;gap:6px;flex-wrap:wrap"></div>
</div>

<div class="layout">
  <div class="sidebar">

    <div class="search-area">
      <div class="search-input-wrap">
        <input id="search" type="text" placeholder="Search..." autocomplete="off">
        <button class="search-clear" id="search-clear" title="Clear">×</button>
      </div>

      <div class="search-scope">
        <label class="scope-chip checked" id="chip-name">
          <input type="checkbox" id="scope-name" checked>
          <span class="dot"></span> Name
        </label>
        <label class="scope-chip" id="chip-args">
          <input type="checkbox" id="scope-args">
          <span class="dot"></span> Args
        </label>
        <label class="scope-chip" id="chip-fields">
          <input type="checkbox" id="scope-fields">
          <span class="dot"></span> Fields
        </label>
        <label class="scope-chip" id="chip-raw">
          <input type="checkbox" id="scope-raw">
          <span class="dot"></span> Raw
        </label>
      </div>

      <div class="match-info" id="match-info"></div>
    </div>

    <div class="op-list" id="op-list"></div>
  </div>

  <div class="main" id="main">
    <div class="empty-state" id="empty-state">← Select an operation</div>
    <div class="detail" id="detail" style="display:none"></div>
  </div>
</div>

<script>
const DATA = {data_json};
const ops = DATA.operations;

let currentTab = 'all';
let currentOp = null;

// ── Search helpers ──────────────────────────────────────────────────

function getScopes() {{
  return {{
    name:   document.getElementById('scope-name').checked,
    args:   document.getElementById('scope-args').checked,
    fields: document.getElementById('scope-fields').checked,
    raw:    document.getElementById('scope-raw').checked,
  }};
}}

function getQuery() {{
  return document.getElementById('search').value.toLowerCase().trim();
}}

function opMatchesQuery(op, q, scopes) {{
  if (!q) return {{ match: true, hint: '' }};

  const hits = [];

  if (scopes.name && op.name.toLowerCase().includes(q)) {{
    hits.push('name');
  }}

  if (scopes.args) {{
    const argHit = (op.variables || []).find(v =>
      v.name.toLowerCase().includes(q) || v.type.toLowerCase().includes(q)
    );
    if (argHit) hits.push('arg:' + argHit.name);
  }}

  if (scopes.fields) {{
    const flat = flattenFields(op.fields || []);
    const fieldHit = flat.find(f => f.label.toLowerCase().includes(q));
    if (fieldHit) hits.push('field:' + fieldHit.label.split('{{')[0]);
  }}

  if (scopes.raw && (op.raw || '').toLowerCase().includes(q)) {{
    hits.push('raw');
  }}

  return {{
    match: hits.length > 0,
    hint: hits.length > 0 ? hits[0] : '',
  }};
}}

// ── Sidebar rendering ───────────────────────────────────────────────

function renderSidebar() {{
  const q = getQuery();
  const scopes = getScopes();
  const list = document.getElementById('op-list');
  const matchInfo = document.getElementById('match-info');
  const clearBtn = document.getElementById('search-clear');

  clearBtn.classList.toggle('visible', q.length > 0);

  let matchCount = 0;
  let html = '';

  ops.forEach((op, idx) => {{
    const tabMatch = currentTab === 'all' || op.type === currentTab;
    if (!tabMatch) return;

    const {{ match, hint }} = opMatchesQuery(op, q, scopes);
    if (!match) return;

    matchCount++;

    const isActive = currentOp === idx;
    const nameHl = q && scopes.name ? highlightMatch(esc(op.name), q) : esc(op.name);
    const hintHtml = hint && hint !== 'name'
      ? `<div class="op-item-hint">match in <span style="color:var(--type-color)">${{esc(hint)}}</span></div>`
      : '';

    html += `<div class="op-item ${{isActive ? 'active' : ''}}" data-idx="${{idx}}">
      <span class="op-dot d-${{op.type}}"></span>
      <div class="op-item-body">
        <div class="op-item-name">${{nameHl}}</div>
        ${{hintHtml}}
      </div>
    </div>`;
  }});

  if (!html) {{
    html = '<div style="padding:16px;color:var(--muted);font-size:12px;text-align:center">No results</div>';
  }}

  list.innerHTML = html;

  // Match info bar
  if (q) {{
    const activeScopes = Object.entries(scopes).filter(([,v])=>v).map(([k])=>k);
    const scopeTags = activeScopes.map(s => `<span class="scope-tag">${{s}}</span>`).join('');
    matchInfo.innerHTML = `<span class="hit">${{matchCount}}</span> match${{matchCount!==1?'es':''}} in ${{scopeTags}}`;
  }} else {{
    matchInfo.innerHTML = '';
  }}
}}

// ── Detail panel ────────────────────────────────────────────────────

function renderDetail(idx) {{
  const op = ops[idx];
  if (!op) return;
  currentOp = idx;

  const vars   = op.variables || [];
  const fields = op.fields    || [];
  const raw    = op.raw       || '';

  // Arguments
  let argsHtml = vars.length === 0
    ? '<div class="no-args">No arguments</div>'
    : `<table class="args-table">
        <thead><tr><th>Name</th><th>Type</th><th>Required</th></tr></thead>
        <tbody>
          ${{vars.map(v => `<tr>
            <td><span class="arg-name">${{esc(v.name)}}</span></td>
            <td><span class="arg-type">${{esc(v.type)}}</span></td>
            <td>${{v.required
              ? '<span class="arg-required">✓ Required</span>'
              : '<span class="arg-optional">Optional</span>'}}</td>
          </tr>`).join('')}}
        </tbody>
      </table>`;

  // Response fields
  const flat = flattenFields(fields);
  const fieldsHtml = flat.length === 0
    ? '<div class="no-fields">Field info not available — see raw query</div>'
    : `<div class="fields-wrap">
        ${{flat.map(f => `<span class="field-tag ${{f.nested?'nested':''}}">${{esc(f.label)}}</span>`).join('')}}
      </div>`;

  const endpointHtml = DATA.endpoints && DATA.endpoints.length > 0
    ? DATA.endpoints.map(e => `<a class="endpoint-pill" href="${{esc(e)}}" target="_blank">${{esc(e)}}</a>`).join('')
    : '';

  document.getElementById('detail').innerHTML = `
    <div class="detail-header">
      <span class="type-badge tb-${{op.type}}">${{op.type}}</span>
      <span class="detail-name">${{esc(op.name)}}</span>
      ${{endpointHtml ? `<div style="margin-left:auto;display:flex;gap:6px">${{endpointHtml}}</div>` : ''}}
    </div>
    <div class="section-block">
      <div class="section-label">Arguments (${{vars.length}})</div>
      ${{argsHtml}}
    </div>
    <div class="section-block">
      <div class="section-label">Response Fields</div>
      ${{fieldsHtml}}
    </div>
    <div class="section-block">
      <div class="section-label">Raw Query</div>
      <div class="raw-wrap">
        <button class="copy-btn" onclick="copyRaw()">Copy</button>
        <pre id="raw-pre">${{highlightGQL(esc(raw))}}</pre>
      </div>
    </div>`;

  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('detail').style.display = 'block';
  renderSidebar();
}}

// ── Utilities ───────────────────────────────────────────────────────

function flattenFields(fields, depth) {{
  depth = depth || 0;
  if (depth > 4) return [];
  const result = [];
  (fields || []).forEach(f => {{
    if (f.fields && f.fields.length > 0) {{
      const childNames = f.fields.map(c => c.name).join(',');
      result.push({{ label: f.name + '{{' + childNames + '}}', nested: true }});
    }} else {{
      result.push({{ label: f.name, nested: false }});
    }}
  }});
  return result;
}}

function highlightMatch(text, q) {{
  if (!q) return text;
  const re = new RegExp('(' + q.replace(/[.*+?^${{}}()|[\\]\\\\]/g,'\\\\$&') + ')', 'gi');
  return text.replace(re, '<mark>$1</mark>');
}}

function highlightGQL(code) {{
  code = code.replace(/\\b(query|mutation|subscription|fragment|on)\\b/g, '<span class="kw">$1</span>');
  code = code.replace(/(\\$\\w+)/g, '<span class="var-hl">$1</span>');
  code = code.replace(/(:\\s*)([A-Z]\\w+[!?\\[\\]]*)/g, '$1<span class="type-hl">$2</span>');
  code = code.replace(/([{{}}()\\[\\]])/g, '<span class="punct">$1</span>');
  code = code.replace(/(\\.\\.\\.)(\\w+)/g, '<span class="frag-hl">...$2</span>');
  return code;
}}

function esc(s) {{
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function copyRaw() {{
  const pre = document.getElementById('raw-pre');
  if (pre) navigator.clipboard.writeText(pre.textContent).then(() => {{
    const btn = document.querySelector('.copy-btn');
    btn.textContent = '✓ Copied';
    setTimeout(()=> btn.textContent = 'Copy', 1500);
  }});
}}

// ── Events ──────────────────────────────────────────────────────────

// Tabs
document.querySelectorAll('.tab-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentTab = btn.dataset.tab;
    currentOp = null;
    document.getElementById('empty-state').style.display = 'flex';
    document.getElementById('detail').style.display = 'none';
    renderSidebar();
  }});
}});

// Search input
document.getElementById('search').addEventListener('input', renderSidebar);

// Clear button
document.getElementById('search-clear').addEventListener('click', () => {{
  document.getElementById('search').value = '';
  renderSidebar();
}});

// Scope checkboxes
['name','args','fields','raw'].forEach(scope => {{
  const cb  = document.getElementById('scope-' + scope);
  const chip = document.getElementById('chip-' + scope);
  cb.addEventListener('change', () => {{
    chip.classList.toggle('checked', cb.checked);
    renderSidebar();
  }});
}});

// Sidebar click
document.getElementById('op-list').addEventListener('click', e => {{
  const item = e.target.closest('.op-item');
  if (item) renderDetail(parseInt(item.dataset.idx));
}});

// ── Init ────────────────────────────────────────────────────────────
// Render endpoint bar
const epBar = document.getElementById('endpoint-bar');
const epPills = document.getElementById('endpoint-pills');
if (DATA.endpoints && DATA.endpoints.length > 0) {{
  epPills.innerHTML = DATA.endpoints.map(e =>
    `<a class="endpoint-pill" href="${{esc(e)}}" target="_blank">${{esc(e)}}</a>`
  ).join('');
}} else {{
  epBar.classList.add('hidden');
}}
renderSidebar();
if (ops.length > 0) renderDetail(0);
</script>
</body>
</html>"""

    path.write_text(html, encoding="utf-8")


def _e(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
