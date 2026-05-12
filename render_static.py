"""
Build the GitHub Pages static site into docs/.
Run: python render_static.py
"""
import json, re, shutil
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Undefined

BASE   = Path(__file__).parent
TMPL   = BASE / "templates"
DOCS   = BASE / "docs"
OUTPUT = BASE / "output"
DOCS.mkdir(exist_ok=True)

# ── Load Holloway data ────────────────────────────────────────────────────────
with open(OUTPUT / "fields-WC-2026-084431-2026-05-10.json") as f:
    data = json.load(f)

fields      = data["fields"]
completeness = data["completeness"]
email_body  = data["email_body"]
pdf_files   = data["pdf_files"]
icd_conflicts = data["icd_conflicts"]
claim       = fields["claim_number"]

# ── Jinja2 env ────────────────────────────────────────────────────────────────
env = Environment(loader=FileSystemLoader(str(TMPL)), autoescape=False)

# ── 1. pipeline.html ─────────────────────────────────────────────────────────
print("Rendering pipeline.html ...")
tmpl = env.get_template("pipeline.html")
html = tmpl.render(
    claim        = claim,
    fields       = fields,
    completeness = completeness,
    email_body   = email_body,
    pdf_files    = pdf_files,
    icd_conflicts = icd_conflicts,
)
# fix back link: href="/" → demo.html
html = html.replace('href="/" class="hdr-back"', 'href="demo.html" class="hdr-back"')
# remove any placeOutboundCall fetch calls (keep button but no trigger)
html = html.replace(
    "fetch('/api/call'",
    "console.log('static: outbound call disabled'"
)
(DOCS / "pipeline.html").write_text(html, encoding="utf-8")
print("  → docs/pipeline.html")

# ── helper: fix panel/hub links in a file ────────────────────────────────────
LINK_MAP = {
    'href="/hub"'             : 'href="index.html"',
    'href="/demo"'            : 'href="demo.html"',
    'href="/panel/vision"'    : 'href="panel_vision.html"',
    'href="/panel/ecosystem"' : 'href="panel_ecosystem.html"',
    'href="/panel/integration"': 'href="panel_integration.html"',
    'href="/panel/workflow"'  : 'href="panel_workflow.html"',
    'href="/panel/economics"' : 'href="panel_economics.html"',
    'href="/panel/observe"'   : 'href="panel_observe.html"',
    'href="/panel/deploy"'    : 'href="panel_deploy.html"',
    'href="/panel/enterprise"': 'href="panel_enterprise.html"',
    'href="/panel/kg"'        : 'href="panel_kg.html"',
}

def fix_links(text):
    for old, new in LINK_MAP.items():
        text = text.replace(old, new)
    return text

# ── 2. index.html (hub) ───────────────────────────────────────────────────────
print("Copying hub.html → index.html ...")
hub = (TMPL / "hub.html").read_text(encoding="utf-8")
hub = fix_links(hub)
(DOCS / "index.html").write_text(hub, encoding="utf-8")
print("  → docs/index.html")

# ── 3. panel HTML files ───────────────────────────────────────────────────────
panels = [
    "panel_vision", "panel_ecosystem", "panel_integration",
    "panel_workflow", "panel_economics", "panel_observe",
    "panel_deploy", "panel_enterprise", "panel_kg",
]
for p in panels:
    src = TMPL / f"{p}.html"
    if src.exists():
        text = src.read_text(encoding="utf-8")
        text = fix_links(text)
        (DOCS / f"{p}.html").write_text(text, encoding="utf-8")
        print(f"  → docs/{p}.html")

# ── 4. demo.html — static simulation ─────────────────────────────────────────
print("Building static demo.html ...")

REFERRALS = [
    # voice rows (green) come in early
    {"claim":"WC-2026-084405","patient":"Teresa Nguyen",    "equip":"TENS Unit",          "hcpcs":"E0730","ch":"voice","gaps":1,"pri":"MED"},
    {"claim":"WC-2026-084412","patient":"Carlos Rivera",    "equip":"Knee Brace",         "hcpcs":"L1820","ch":"voice","gaps":2,"pri":"HIGH"},
    {"claim":"WC-2026-084419","patient":"Sandra Mitchell",  "equip":"Lumbar Orthosis",    "hcpcs":"L0631","ch":"voice","gaps":3,"pri":"HIGH"},
    # fax rows
    {"claim":"WC-2026-084420","patient":"Robert Chen",      "equip":"Wheelchair — K0001", "hcpcs":"K0001","ch":"fax",  "gaps":0,"pri":"MED"},
    {"claim":"WC-2026-084421","patient":"Maria Garcia",     "equip":"Hospital Bed",       "hcpcs":"E0250","ch":"fax",  "gaps":2,"pri":"MED"},
    {"claim":"WC-2026-084422","patient":"David Kim",        "equip":"CPAP Machine",       "hcpcs":"E0601","ch":"fax",  "gaps":0,"pri":"LOW"},
    {"claim":"WC-2026-084423","patient":"Lisa Thompson",    "equip":"Prosthetic Foot",    "hcpcs":"L5100","ch":"fax",  "gaps":1,"pri":"HIGH"},
    {"claim":"WC-2026-084424","patient":"James Wilson",     "equip":"Forearm Crutches",   "hcpcs":"E0110","ch":"fax",  "gaps":0,"pri":"LOW"},
    {"claim":"WC-2026-084425","patient":"Patricia Moore",   "equip":"Compression Pump",   "hcpcs":"E0650","ch":"fax",  "gaps":3,"pri":"MED"},
    {"claim":"WC-2026-084426","patient":"Michael Brown",    "equip":"TENS Unit",          "hcpcs":"E0730","ch":"fax",  "gaps":1,"pri":"MED"},
    {"claim":"WC-2026-084427","patient":"Jennifer Davis",   "equip":"Ankle Orthosis",     "hcpcs":"L1902","ch":"fax",  "gaps":0,"pri":"LOW"},
    {"claim":"WC-2026-084428","patient":"William Martinez", "equip":"Power Wheelchair",   "hcpcs":"K0823","ch":"fax",  "gaps":2,"pri":"HIGH"},
    {"claim":"WC-2026-084429","patient":"Barbara Anderson", "equip":"Nebulizer",          "hcpcs":"E0570","ch":"fax",  "gaps":1,"pri":"MED"},
    {"claim":"WC-2026-084430","patient":"Richard Taylor",   "equip":"Hospital Bed Rail",  "hcpcs":"E0305","ch":"fax",  "gaps":0,"pri":"LOW"},
    # HOLLOWAY — featured row
    {"claim":"WC-2026-084431","patient":"James Holloway",   "equip":"Rollator Walker",    "hcpcs":"E0143","ch":"fax",  "gaps":3,"pri":"HIGH","featured":True},
    {"claim":"WC-2026-084432","patient":"Susan Jackson",    "equip":"Lumbar Support",     "hcpcs":"L0631","ch":"fax",  "gaps":2,"pri":"MED"},
    {"claim":"WC-2026-084433","patient":"Joseph White",     "equip":"Knee Walker",        "hcpcs":"E0118","ch":"fax",  "gaps":0,"pri":"LOW"},
    {"claim":"WC-2026-084434","patient":"Linda Harris",     "equip":"Shoulder Orthosis",  "hcpcs":"L3960","ch":"fax",  "gaps":1,"pri":"MED"},
    {"claim":"WC-2026-084435","patient":"Charles Martin",   "equip":"Oxygen Concentrator","hcpcs":"E1390","ch":"fax",  "gaps":0,"pri":"MED"},
    {"claim":"WC-2026-084436","patient":"Dorothy Garcia",   "equip":"Wrist Splint",       "hcpcs":"L3906","ch":"fax",  "gaps":0,"pri":"LOW"},
    {"claim":"WC-2026-084437","patient":"Matthew Lee",      "equip":"Custom AFO",         "hcpcs":"L1900","ch":"fax",  "gaps":1,"pri":"HIGH"},
    {"claim":"WC-2026-084438","patient":"Robert Kim",       "equip":"Standard Wheelchair","hcpcs":"K0001","ch":"fax",  "gaps":0,"pri":"LOW"},
    {"claim":"WC-2026-084439","patient":"Nancy Wilson",     "equip":"TENS Unit",          "hcpcs":"E0730","ch":"fax",  "gaps":1,"pri":"MED"},
    {"claim":"WC-2026-084440","patient":"Anthony Clark",    "equip":"Commode Chair",      "hcpcs":"E0163","ch":"fax",  "gaps":0,"pri":"LOW"},
    {"claim":"WC-2026-084441","patient":"Karen Lewis",      "equip":"Bath Bench",         "hcpcs":"E0240","ch":"fax",  "gaps":0,"pri":"LOW"},
    {"claim":"WC-2026-084442","patient":"Mark Robinson",    "equip":"Elbow Orthosis",     "hcpcs":"L3760","ch":"fax",  "gaps":2,"pri":"MED"},
    {"claim":"WC-2026-084443","patient":"Betty Walker",     "equip":"Bariatric Rollator", "hcpcs":"E0149","ch":"fax",  "gaps":1,"pri":"HIGH"},
    {"claim":"WC-2026-084444","patient":"Donald Hall",      "equip":"Stair Lift",         "hcpcs":"E1399","ch":"fax",  "gaps":3,"pri":"HIGH"},
    {"claim":"WC-2026-084445","patient":"Helen Allen",      "equip":"Cervical Collar",    "hcpcs":"L0120","ch":"fax",  "gaps":0,"pri":"LOW"},
    {"claim":"WC-2026-084446","patient":"George Young",     "equip":"Cane — Quad",        "hcpcs":"E0105","ch":"fax",  "gaps":1,"pri":"MED"},
    {"claim":"WC-2026-084447","patient":"Sandra Hernandez", "equip":"Back Brace",         "hcpcs":"L0651","ch":"fax",  "gaps":0,"pri":"LOW"},
    {"claim":"WC-2026-084448","patient":"Kenneth King",     "equip":"Portable Suction",   "hcpcs":"E2000","ch":"fax",  "gaps":2,"pri":"MED"},
    {"claim":"WC-2026-084449","patient":"Donna Wright",     "equip":"Rollator Walker",    "hcpcs":"E0143","ch":"fax",  "gaps":0,"pri":"MED"},
    {"claim":"WC-2026-084450","patient":"Frank Scott",      "equip":"Power Scooter",      "hcpcs":"K0010","ch":"fax",  "gaps":1,"pri":"HIGH"},
    {"claim":"WC-2026-084451","patient":"Ruth Green",       "equip":"Patient Lift",       "hcpcs":"E0621","ch":"fax",  "gaps":2,"pri":"HIGH"},
    {"claim":"WC-2026-084452","patient":"Raymond Adams",    "equip":"Hospital Bed",       "hcpcs":"E0250","ch":"fax",  "gaps":0,"pri":"MED"},
    {"claim":"WC-2026-084453","patient":"Shirley Baker",    "equip":"Traction Equipment", "hcpcs":"E0840","ch":"fax",  "gaps":1,"pri":"MED"},
    {"claim":"WC-2026-084454","patient":"Carl Nelson",      "equip":"TENS Unit",          "hcpcs":"E0730","ch":"fax",  "gaps":0,"pri":"LOW"},
    {"claim":"WC-2026-084455","patient":"Joyce Carter",     "equip":"Knee Brace",         "hcpcs":"L1820","ch":"fax",  "gaps":1,"pri":"MED"},
    {"claim":"WC-2026-084456","patient":"Benjamin Mitchell","equip":"Custom KAFO",        "hcpcs":"L2030","ch":"fax",  "gaps":3,"pri":"HIGH"},
]

import json as _json
referrals_json = _json.dumps(REFERRALS)

# build holloway index for timing
holloway_idx = next(i for i, r in enumerate(REFERRALS) if r["claim"] == "WC-2026-084431")

demo_src = (TMPL / "demo.html").read_text(encoding="utf-8")

# Replace header back link
demo_src = demo_src.replace('href="/" class="logo"', 'href="index.html" class="logo"')
# Remove the hero sub text about "No simulation"
demo_src = demo_src.replace(
    'Real AI extraction · Real PDF processing · Real gap detection · Real outreach drafting · No simulation.',
    'Full pipeline walkthrough · ICD conflict resolution · Gap detection · Email &amp; voice outreach.'
)

# Inject static simulation script BEFORE closing </script> at the end, by replacing
# the entire <script>...</script> block
static_script = r"""
<script>
// ── STATIC SIMULATION ────────────────────────────────────────────────────────
const REFERRALS = """ + referrals_json + r""";
const HOLLOWAY_IDX = """ + str(holloway_idx) + r""";

let simState = {started:false, done:false};
let rowStatus = {};   // claim → {status, patient, gaps, outreach, pages, pri, ch}
let stats = {queued:40, processing:0, pages:0, routed:0, gaps:0, outreach:0, logLines:0};

// sidebar counters
let sbPages=0, sbGaps=0, sbOutreach=0, sbRouted=0, sbConflicts=0;
let inboxFilter = 'all';
let inboxQueueMap = {};

window.addEventListener('DOMContentLoaded', () => {
  // initialize inbox with pending status
  REFERRALS.forEach(r => { inboxQueueMap[r.claim] = {status:'queued', patient:r.patient, gaps:r.gaps, ch:r.ch}; });
  renderInbox();
  switchTab('inbox');  // start on inbox tab
});

function switchTab(name) {
  ['queue','inbox'].forEach(t => {
    document.getElementById('tab-' + t).classList.toggle('active', t === name);
    document.getElementById('tab-btn-' + t).classList.toggle('active', t === name);
  });
  if (name === 'inbox') renderInbox();
}

function setInboxFilter(f, btn) {
  inboxFilter = f;
  document.querySelectorAll('.inbox-filter').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderInbox();
}

function renderInbox() {
  const search = (document.getElementById('inbox-search').value || '').toLowerCase();
  const filtered = REFERRALS.filter(r => {
    if (search) {
      const hay = (r.claim + ' ' + r.patient).toLowerCase();
      if (!hay.includes(search)) return false;
    }
    const st = (inboxQueueMap[r.claim] || {}).status || 'queued';
    if (inboxFilter === 'fax')        return r.ch === 'fax';
    if (inboxFilter === 'voice')      return r.ch === 'voice';
    if (inboxFilter === 'pending')    return st === 'queued';
    if (inboxFilter === 'processing') return st === 'processing';
    if (inboxFilter === 'done')       return st === 'routed' || st === 'gaps';
    return true;
  });
  const tbody = document.getElementById('inbox-tbody');
  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--gray)">No referrals match filter</td></tr>';
    return;
  }
  tbody.innerHTML = filtered.map(r => inboxRow(r)).join('');
}

function inboxRow(r) {
  const st = (inboxQueueMap[r.claim] || {}).status || 'queued';
  let rowCls = '';
  if (st === 'processing') rowCls = 'ir-processing';
  else if (st === 'routed') rowCls = 'ir-routed';
  else if (st === 'gaps')   rowCls = 'ir-gaps';
  if (r.featured) rowCls += ' ir-featured';

  const chTag = r.ch === 'voice'
    ? '<span class="ftag ftag-voice">&#x1F3A4; Voice</span>'
    : '<span class="ftag ftag-fax">&#x1F4E0; Fax</span>';

  const featTag = r.featured ? '<span class="ftag ftag-demo">&#x2605;</span>' : '';

  let stTag = '<span class="ftag" style="background:var(--gray-l);color:var(--gray)">Queued</span>';
  if (st === 'processing') stTag = '<span class="ftag ftag-processing">Processing…</span>';
  else if (st === 'routed') stTag = '<span class="ftag ftag-routed">Routed</span>';
  else if (st === 'gaps')   stTag = '<span class="ftag ftag-gaps">Gaps Found</span>';

  const pdfs = `<span class="pdf-open">PDF 1</span><span class="pdf-open">PDF 2</span><span class="pdf-open">PDF 3</span>`;

  let actionBtn = '';
  if (r.featured && (st === 'routed' || st === 'gaps' || st === 'error')) {
    actionBtn = `<a href="pipeline.html" class="fc-pipe-link">Pipeline &#x2192;</a>`;
  }

  const time = st === 'routed' || st === 'gaps' ? `${Math.floor(Math.random()*60+60)}s` : '—';

  return `<tr class="${rowCls}"><td style="font-family:monospace;font-size:10px">${r.claim}</td><td>${r.patient}</td><td>${chTag}</td><td>${stTag} ${featTag}</td><td>${pdfs}</td><td style="text-align:center">${time}</td><td style="text-align:center">${actionBtn}</td></tr>`;
}

function startProcessing() {
  if (simState.started) return;
  simState.started = true;
  document.getElementById('btn-start').disabled = true;
  document.getElementById('btn-reset').style.display = 'inline-flex';
  document.getElementById('live-badge').style.display = 'flex';
  document.getElementById('status-text').textContent = 'Processing 40 referrals...';
  switchTab('queue');

  const tbody = document.getElementById('queue-tbody');
  // render all rows as queued
  tbody.innerHTML = REFERRALS.map((r,i) => queueRow(r,'queued')).join('');

  const totalMs = 90000; // 90 seconds
  const perItem = totalMs / REFERRALS.length;

  // process each referral with staggered delays
  REFERRALS.forEach((r, i) => {
    // start processing at staggered times
    setTimeout(() => startRow(r, i), i * (perItem * 0.7));
    // complete at slightly later time
    const finishDelay = i * (perItem * 0.7) + (perItem * 1.2) + Math.random() * 2000;
    setTimeout(() => finishRow(r, i), finishDelay);
  });

  // complete banner after all done
  setTimeout(() => completeSim(), totalMs + 2000);
}

function startRow(r, i) {
  rowStatus[r.claim] = 'processing';
  inboxQueueMap[r.claim] = {...inboxQueueMap[r.claim], status:'processing'};
  stats.queued = Math.max(0, stats.queued - 1);
  stats.processing++;
  updateStatsBar();
  updateQueueRow(r, 'processing');

  // sidebar log
  addLog(`+${Math.floor(i*2.3)}s`, `${r.patient} · reading ${2+Math.floor(Math.random()*2)} docs`);

  // sidebar pages counter
  const pages = 3 + Math.floor(Math.random() * 4);
  sbPages += pages; sbConflicts += (r.gaps > 0 ? 1 : 0);
  document.getElementById('sb-pages').textContent = sbPages;
  document.getElementById('sb-conflicts').textContent = sbConflicts;
  document.getElementById('stat-pages').textContent = sbPages;
  updateProgBar(i);
}

function finishRow(r, i) {
  const status = r.gaps > 0 ? 'gaps' : 'routed';
  rowStatus[r.claim] = status;
  inboxQueueMap[r.claim] = {...inboxQueueMap[r.claim], status};
  stats.processing = Math.max(0, stats.processing - 1);
  if (status === 'routed') stats.routed++;
  else stats.gaps++;
  stats.pages += 3 + Math.floor(Math.random() * 4);
  if (r.gaps > 0) { stats.outreach++; stats.gaps += r.gaps; }
  updateStatsBar();
  updateQueueRow(r, status);

  // sidebar counters
  if (r.gaps > 0) {
    sbGaps += r.gaps; sbOutreach++;
    document.getElementById('sb-gaps').textContent = sbGaps;
    document.getElementById('sb-outreach').textContent = sbOutreach;
    addLog(`+${Math.floor(i*2.3+2)}s`, `${r.patient} · ${r.gaps} gap(s) found · outreach sent`, 'warn');
  } else {
    sbRouted++;
    document.getElementById('sb-routed').textContent = sbRouted;
    addLog(`+${Math.floor(i*2.3+2)}s`, `${r.patient} · routed ✓`, 'ok');
  }

  // stat counters
  document.getElementById('stat-routed').textContent = stats.routed;
  document.getElementById('stat-gaps').textContent   = stats.gaps;
  document.getElementById('stat-outreach').textContent = stats.outreach;

  // holloway hint
  if (r.featured) {
    const hint = document.getElementById('holloway-hint');
    if (hint) { hint.style.display = 'flex'; }
    renderInbox();
  }
  updateProgBar(i + 1);
}

function updateQueueRow(r, status) {
  const tr = document.getElementById('qr-' + r.claim);
  if (!tr) return;

  const isHolloway = r.featured;
  if (status === 'processing') {
    tr.className = 'processing' + (isHolloway ? ' holloway' : '');
  } else if (status === 'routed') {
    tr.className = 'routed' + (isHolloway ? ' holloway-done' : '');
    if (isHolloway) tr.setAttribute('onclick', 'location.href="pipeline.html"');
  } else if (status === 'gaps') {
    tr.className = 'gaps' + (isHolloway ? ' holloway-done' : '');
    if (isHolloway) tr.setAttribute('onclick', 'location.href="pipeline.html"');
  }

  const stCell = tr.querySelector('.status-cell');
  if (stCell) stCell.innerHTML = statusBadge(status);
}

function queueRow(r, status) {
  const chTag = r.ch === 'voice'
    ? '<span class="ch-voice">Voice</span>'
    : '<span class="ch-fax">Fax</span>';
  const priTag = `<span class="pri-${r.pri}">${r.pri}</span>`;
  const gapBadge = r.gaps > 0
    ? `<span class="gap-badge">${r.gaps}</span>`
    : '<span class="gap-badge zero">0</span>';

  return `<tr id="qr-${r.claim}">
    <td>${r.patient}</td>
    <td style="font-family:monospace;font-size:10px">${r.claim}</td>
    <td>${r.equip} · ${r.hcpcs}</td>
    <td style="text-align:center">${chTag}</td>
    <td class="status-cell" style="text-align:center">${statusBadge(status)}</td>
    <td style="text-align:center">${gapBadge}</td>
    <td style="text-align:center">—</td>
    <td style="text-align:center">${priTag}</td>
  </tr>`;
}

function statusBadge(st) {
  if (st === 'queued')     return '<span class="s-queued">Queued</span>';
  if (st === 'processing') return '<span class="s-processing">Reading…</span>';
  if (st === 'routed')     return '<span class="s-routed">&#x2713; Routed</span>';
  if (st === 'gaps')       return '<span class="s-gaps">&#x26A0; Gaps</span>';
  return '<span class="s-queued">—</span>';
}

function updateStatsBar() {
  document.getElementById('stat-queued').textContent    = stats.queued;
  document.getElementById('stat-processing').textContent = stats.processing;
  document.getElementById('stat-pages').textContent     = sbPages;
}

function updateProgBar(done) {
  const pct = Math.round((done / REFERRALS.length) * 100);
  document.getElementById('prog-fill').style.width = pct + '%';
  document.getElementById('prog-pct').textContent  = pct + '%';
  document.getElementById('prog-label').textContent = `Processing ${Math.min(done, REFERRALS.length)} of ${REFERRALS.length} referrals…`;
}

function completeSim() {
  simState.done = true;
  document.getElementById('live-badge').style.display = 'none';
  document.getElementById('status-text').textContent = 'Processing complete';
  document.getElementById('prog-fill').style.width = '100%';
  document.getElementById('prog-pct').textContent  = '100%';
  document.getElementById('prog-label').textContent = '40 of 40 referrals processed';

  const banner = document.getElementById('complete-banner');
  if (banner) {
    banner.classList.add('visible');
    const sub = document.getElementById('cb-sub');
    if (sub) sub.textContent = `40 referrals · ${sbRouted} routed · ${sbGaps} gaps detected · ${sbOutreach} outreach sent`;
  }

  const scaleCard = document.getElementById('scale-card');
  if (scaleCard) scaleCard.classList.add('visible');
  const scaleCallout = document.getElementById('scale-callout');
  if (scaleCallout) scaleCallout.classList.add('visible');

  renderInbox();
}

function addLog(ts, msg, cls='') {
  const log = document.getElementById('agent-log');
  if (!log) return;
  const d = document.createElement('div');
  d.className = 'log-line' + (cls ? ' ' + cls : '');
  d.innerHTML = `<span class="ts">${ts}</span>${msg}`;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function openPipeline() {
  location.href = 'pipeline.html';
}

function resetDemo() {
  location.reload();
}

function openFaxModal() {
  document.getElementById('fax-modal').classList.add('open');
}
function closeFaxModal() {
  document.getElementById('fax-modal').classList.remove('open');
}
function triggerDemoFax() {
  closeFaxModal();
  alert('In the live system, this fax would enter the processing queue automatically.');
}

// ── keep outbound call button visible but non-triggering ─────────────────────
function placeOutboundCall() {
  alert('In the live system, the agent places an outbound call automatically after 24 hours with no email response.\n\n(Demo: outbound calling requires Vapi integration — not active in static demo.)');
}
</script>
"""

# Replace the <script> block — use string find to avoid regex backreference issues
script_start = demo_src.rfind('<script>')
if script_start == -1:
    raise ValueError("Could not find <script> tag in demo.html")
demo_src = demo_src[:script_start] + static_script

demo_src = fix_links(demo_src)

# Make fax button visible from the start (static: no server to show/hide it)
demo_src = demo_src.replace(
    '<button class="btn-fax" id="btn-fax" onclick="openFaxModal()">',
    '<button class="btn-fax" id="btn-fax" onclick="openFaxModal()" style="display:inline-flex">'
)

(DOCS / "demo.html").write_text(demo_src, encoding="utf-8")
print("  → docs/demo.html")

print("\nDone. All files written to docs/")
print("Files:", [f.name for f in sorted(DOCS.iterdir())])
