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

# ── Password gate — injected into every docs/ page ───────────────────────────
PASSWORD_GATE = """
<div id="pw-gate" style="display:none;position:fixed;inset:0;background:rgba(15,23,42,0.97);z-index:99999;align-items:center;justify-content:center;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <div style="background:#1e293b;border:1px solid #334155;border-radius:16px;padding:48px 40px;max-width:380px;width:90%;text-align:center;box-shadow:0 25px 60px rgba(0,0,0,0.5)">
    <div style="font-size:28px;margin-bottom:8px">&#x1F512;</div>
    <div style="font-size:18px;font-weight:800;color:#f1f5f9;margin-bottom:4px">Coastal DME</div>
    <div style="font-size:13px;color:#64748b;margin-bottom:28px">Intake Agent Platform · Private Demo</div>
    <input id="pw-input" type="password" placeholder="Enter access code" autocomplete="off"
      style="width:100%;box-sizing:border-box;padding:12px 16px;border-radius:8px;border:1px solid #334155;background:#0f172a;color:#f1f5f9;font-size:15px;outline:none;margin-bottom:12px;text-align:center;letter-spacing:2px">
    <button onclick="checkPw()"
      style="width:100%;padding:12px;border-radius:8px;background:#2563eb;color:#fff;font-size:15px;font-weight:700;border:none;cursor:pointer">
      Enter &#x2192;
    </button>
    <div id="pw-err" style="display:none;color:#f87171;font-size:13px;margin-top:12px">Incorrect access code — try again</div>
  </div>
</div>
<script>
(function(){
  if(sessionStorage.getItem('demo_auth')==='coastal2026'){return;}
  var g=document.getElementById('pw-gate');
  if(g){g.style.display='flex';document.body.style.overflow='hidden';}
})();
function checkPw(){
  var v=document.getElementById('pw-input').value;
  if(v==='coastal2026'){
    sessionStorage.setItem('demo_auth','coastal2026');
    document.getElementById('pw-gate').style.display='none';
    document.body.style.overflow='';
  } else {
    document.getElementById('pw-err').style.display='block';
    document.getElementById('pw-input').value='';
    document.getElementById('pw-input').focus();
  }
}
document.addEventListener('DOMContentLoaded',function(){
  var inp=document.getElementById('pw-input');
  if(inp){inp.addEventListener('keydown',function(e){if(e.key==='Enter')checkPw();});}
  inp && inp.focus();
});
</script>
"""

def inject_gate(html):
    if '</body>' in html:
        return html.replace('</body>', PASSWORD_GATE + '\n</body>', 1)
    return html + PASSWORD_GATE

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

# ── fix outbound call — match post-render string (claim already substituted) ──
old_call = f"""function placeOutboundCall() {{
  const btn = document.getElementById('call-btn');
  const status = document.getElementById('call-status');
  if (btn) {{ btn.style.display = 'none'; btn.disabled = true; }}
  status.style.color = '#6b7280';
  status.innerHTML = '&#x23F3; Connecting to AI voice agent — placing call now...';

  fetch('/api/outbound-call/{claim}', {{ method: 'POST' }})
    .then(r => r.json())
    .then(data => {{
      if (data.success) {{
        status.style.color = '#16a34a';
        status.innerHTML = '&#x2705; Call placed · ID: ' + (data.call_id || 'confirmed') + ' · Agent dialing now';
      }} else {{
        status.style.color = '#dc2626';
        status.innerHTML = '&#x26A0; Call failed: ' + (data.reason || 'unknown error');
        if (btn) {{ btn.style.display = 'inline-flex'; btn.disabled = false; btn.innerHTML = '&#x1F4DE; Retry Call'; }}
      }}
    }})
    .catch(err => {{
      status.style.color = '#dc2626';
      status.innerHTML = '&#x26A0; Network error — check server';
      if (btn) {{ btn.style.display = 'inline-flex'; btn.disabled = false; btn.innerHTML = '&#x1F4DE; Retry Call'; }}
    }});
}}"""
new_call = """function placeOutboundCall() {
  const btn = document.getElementById('call-btn');
  const status = document.getElementById('call-status');
  if (btn) { btn.style.display = 'none'; btn.disabled = true; }
  status.style.color = '#6b7280';
  status.innerHTML = '&#x23F3; Connecting to AI voice agent — placing call now...';
  setTimeout(() => {
    status.style.color = '#16a34a';
    status.innerHTML = '&#x2705; Call placed &middot; 84s &middot; Linda Torres &middot; Auth ref, appt window &amp; transportation confirmed';
  }, 2200);
}"""
html = html.replace(old_call, new_call)

# ── fix escalation review — replace fetch with static Holloway data ───────────
html = html.replace(
    """function loadEscalationReview() {
  fetch('/api/escalations')
    .then(r => r.json())
    .then(queue => {
      const pending = queue.filter(e => e.status === 'pending');
      const panel = document.getElementById('esc-review-panel');
      const card  = document.getElementById('esc-review-card');
      if (!pending.length) {
        panel.style.display = 'none';
        return;
      }
      panel.style.display = 'block';
      renderEscCard(card, pending[0]);
    })
    .catch(() => {});
}""",
    """function loadEscalationReview() {
  const panel = document.getElementById('esc-review-panel');
  const card  = document.getElementById('esc-review-card');
  if (!panel || !card) return;
  panel.style.display = 'block';
  renderEscCard(card, {
    id: 'esc-001',
    patient_name: 'James Holloway',
    claim_number: 'WC-2026-084431',
    dme_item: 'Rollator Walker — E0143',
    insurance_carrier: 'Pacific Mutual Workers Comp',
    confidence: 72,
    icd_correct: 'S83.209A',
    icd_correct_desc: 'Tear of unspecified meniscus, right knee, initial encounter',
    icd_form: 'M23.611',
    icd_form_desc: 'Spontaneous disruption of anterior cruciate ligament, right knee',
    conflict_detail: 'Clinical notes and prescription both document S83.209A (meniscus tear) following ACL reconstruction, but referral form lists M23.611 (ACL disruption). Clinically significant difference — requires specialist confirmation before dispatch.'
  });
}"""
)

# ── fix resolveEscalation — remove fetch, show success directly ───────────────
html = html.replace(
    "  fetch('/review/resolve', {",
    "  if(false) fetch('/review/resolve', {"
)
html = html.replace(
    "  .catch(() => alert('Error recording decision'));",
    "  setTimeout(() => { const card=document.getElementById('esc-review-card'); if(card){ card.innerHTML='<div style=\"display:flex;align-items:center;gap:12px;padding:8px 0\"><span style=\"font-size:28px\">&#x2705;</span><div><div style=\"font-size:14px;font-weight:800;color:#16a34a\">Decision Recorded — Episode Updated</div><div style=\"font-size:11px;color:#64748b;margin-top:4px\">Resolved by: Specialist · '+new Date().toLocaleTimeString()+'</div></div></div>'; card.style.background='#f0fdf4'; card.style.border='2px solid #86efac'; } }, 800);"
)

# fix PDF doc links to serve from docs/pdfs/
html = html.replace('"1_referral_form.pdf"',  '"pdfs/1_referral_form.pdf"')
html = html.replace('"2_clinical_notes.pdf"', '"pdfs/2_clinical_notes.pdf"')
html = html.replace('"3_prescription.pdf"',   '"pdfs/3_prescription.pdf"')
# fix doc-name text + add View PDF links
html = html.replace(
    '>1_referral_form.pdf<',
    '><a href="pdfs/1_referral_form.pdf" target="_blank" style="color:var(--blue);font-weight:700;text-decoration:none">&#x1F4C4; Referral Form — View PDF &rarr;</a><'
)
html = html.replace(
    '>2_clinical_notes.pdf<',
    '><a href="pdfs/2_clinical_notes.pdf" target="_blank" style="color:var(--blue);font-weight:700;text-decoration:none">&#x1F4CB; Clinical Notes — View PDF &rarr;</a><'
)
html = html.replace(
    '>3_prescription.pdf<',
    '><a href="pdfs/3_prescription.pdf" target="_blank" style="color:var(--blue);font-weight:700;text-decoration:none">&#x1F48A; Prescription — View PDF &rarr;</a><'
)

(DOCS / "pipeline.html").write_text(inject_gate(html), encoding="utf-8")
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
(DOCS / "index.html").write_text(inject_gate(hub), encoding="utf-8")
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
        (DOCS / f"{p}.html").write_text(inject_gate(text), encoding="utf-8")
        print(f"  → docs/{p}.html")

# ── 4. demo.html — static simulation ─────────────────────────────────────────
print("Building static demo.html ...")

REFERRALS = [
    # HOLLOWAY first — featured, clickable
    {"claim":"WC-2026-084431","patient":"James Holloway",   "equip":"Rollator Walker",    "hcpcs":"E0143","ch":"fax",  "gaps":3,"pri":"HIGH","why":"Post-surgical ACL reconstruction, unsafe ambulation, pain 9/10; ICD conflict + bariatric flag (285 lbs)","featured":True},
    # voice rows — all clickable
    {"claim":"WC-2026-084405","patient":"Teresa Nguyen",    "equip":"TENS Unit",          "hcpcs":"E0730","ch":"voice","gaps":1,"pri":"MED", "why":"Chronic pain management — stable, non-urgent; auth ref missing","clickable":True},
    {"claim":"WC-2026-084412","patient":"Carlos Rivera",    "equip":"Knee Brace",         "hcpcs":"L1820","ch":"voice","gaps":2,"pri":"HIGH","why":"Post-op ACL repair, weight-bearing restricted; appt window and auth ref missing","clickable":True},
    {"claim":"WC-2026-084419","patient":"Sandra Mitchell",  "equip":"Lumbar Orthosis",    "hcpcs":"L0631","ch":"voice","gaps":3,"pri":"HIGH","why":"Acute lumbar fracture, pain 8/10; auth ref, appt window, and transport all missing","clickable":True},
    # fax rows
    {"claim":"WC-2026-084420","patient":"Robert Chen",      "equip":"Wheelchair — K0001", "hcpcs":"K0001","ch":"fax",  "gaps":0,"pri":"MED", "why":"Lower limb injury, ambulatory with assistance; all fields confirmed"},
    {"claim":"WC-2026-084421","patient":"Maria Garcia",     "equip":"Hospital Bed",       "hcpcs":"E0250","ch":"fax",  "gaps":2,"pri":"MED", "why":"Post-surgical recovery at home; delivery address and auth ref pending"},
    {"claim":"WC-2026-084422","patient":"David Kim",        "equip":"CPAP Machine",       "hcpcs":"E0601","ch":"fax",  "gaps":0,"pri":"LOW", "why":"Sleep apnea — non-urgent; all fields confirmed, routine dispatch"},
    {"claim":"WC-2026-084423","patient":"Lisa Thompson",    "equip":"Prosthetic Foot",    "hcpcs":"L5100","ch":"fax",  "gaps":1,"pri":"HIGH","why":"Below-knee amputation, mobility compromised; auth ref outstanding","clickable":True},
    {"claim":"WC-2026-084424","patient":"James Wilson",     "equip":"Forearm Crutches",   "hcpcs":"E0110","ch":"fax",  "gaps":0,"pri":"LOW", "why":"Ankle sprain — temporary aid; all fields confirmed"},
    {"claim":"WC-2026-084425","patient":"Patricia Moore",   "equip":"Compression Pump",   "hcpcs":"E0650","ch":"fax",  "gaps":3,"pri":"MED", "why":"Lymphedema management; auth ref, appt window, and transport missing"},
    {"claim":"WC-2026-084426","patient":"Michael Brown",    "equip":"TENS Unit",          "hcpcs":"E0730","ch":"fax",  "gaps":1,"pri":"MED", "why":"Chronic back pain — stable; transportation confirmation pending"},
    {"claim":"WC-2026-084427","patient":"Jennifer Davis",   "equip":"Ankle Orthosis",     "hcpcs":"L1902","ch":"fax",  "gaps":0,"pri":"LOW", "why":"Ankle ligament sprain; all fields confirmed, routine dispatch"},
    {"claim":"WC-2026-084428","patient":"William Martinez", "equip":"Power Wheelchair",   "hcpcs":"K0823","ch":"fax",  "gaps":2,"pri":"HIGH","why":"Spinal cord injury, non-ambulatory; auth ref and appt window missing","clickable":True},
    {"claim":"WC-2026-084429","patient":"Barbara Anderson", "equip":"Nebulizer",          "hcpcs":"E0570","ch":"fax",  "gaps":1,"pri":"MED", "why":"Occupational asthma; delivery address needs confirmation"},
    {"claim":"WC-2026-084430","patient":"Richard Taylor",   "equip":"Hospital Bed Rail",  "hcpcs":"E0305","ch":"fax",  "gaps":0,"pri":"LOW", "why":"Fall prevention aid; all fields confirmed, routine dispatch"},
    # HOLLOWAY — featured row
    {"claim":"WC-2026-084431","patient":"James Holloway",   "equip":"Rollator Walker",    "hcpcs":"E0143","ch":"fax",  "gaps":3,"pri":"HIGH","why":"Post-surgical ACL reconstruction, unsafe ambulation, pain 9/10; ICD conflict + bariatric flag (285 lbs)","featured":True},
    {"claim":"WC-2026-084432","patient":"Susan Jackson",    "equip":"Lumbar Support",     "hcpcs":"L0631","ch":"fax",  "gaps":2,"pri":"MED", "why":"Herniated disc, conservative management; auth ref and appt window pending"},
    {"claim":"WC-2026-084433","patient":"Joseph White",     "equip":"Knee Walker",        "hcpcs":"E0118","ch":"fax",  "gaps":0,"pri":"LOW", "why":"Foot fracture, non-weight-bearing; all fields confirmed"},
    {"claim":"WC-2026-084434","patient":"Linda Harris",     "equip":"Shoulder Orthosis",  "hcpcs":"L3960","ch":"fax",  "gaps":1,"pri":"MED", "why":"Rotator cuff repair; transportation confirmation pending"},
    {"claim":"WC-2026-084435","patient":"Charles Martin",   "equip":"Oxygen Concentrator","hcpcs":"E1390","ch":"fax",  "gaps":0,"pri":"MED", "why":"Occupational lung disease; all fields confirmed, standard dispatch"},
    {"claim":"WC-2026-084436","patient":"Dorothy Garcia",   "equip":"Wrist Splint",       "hcpcs":"L3906","ch":"fax",  "gaps":0,"pri":"LOW", "why":"Carpal tunnel — repetitive strain; all fields confirmed"},
    {"claim":"WC-2026-084437","patient":"Matthew Lee",      "equip":"Custom AFO",         "hcpcs":"L1900","ch":"fax",  "gaps":1,"pri":"HIGH","why":"Drop foot post-nerve injury, fall risk; auth ref outstanding"},
    {"claim":"WC-2026-084438","patient":"Robert Kim",       "equip":"Standard Wheelchair","hcpcs":"K0001","ch":"fax",  "gaps":0,"pri":"LOW", "why":"Knee injury, temporary mobility aid; all fields confirmed"},
    {"claim":"WC-2026-084439","patient":"Nancy Wilson",     "equip":"TENS Unit",          "hcpcs":"E0730","ch":"fax",  "gaps":1,"pri":"MED", "why":"Chronic shoulder pain; appt window pending"},
    {"claim":"WC-2026-084440","patient":"Anthony Clark",    "equip":"Commode Chair",      "hcpcs":"E0163","ch":"fax",  "gaps":0,"pri":"LOW", "why":"Hip replacement recovery; all fields confirmed"},
    {"claim":"WC-2026-084441","patient":"Karen Lewis",      "equip":"Bath Bench",         "hcpcs":"E0240","ch":"fax",  "gaps":0,"pri":"LOW", "why":"Balance impairment post-concussion; all fields confirmed"},
    {"claim":"WC-2026-084442","patient":"Mark Robinson",    "equip":"Elbow Orthosis",     "hcpcs":"L3760","ch":"fax",  "gaps":2,"pri":"MED", "why":"Lateral epicondylitis; auth ref and transport missing"},
    {"claim":"WC-2026-084443","patient":"Betty Walker",     "equip":"Bariatric Rollator", "hcpcs":"E0149","ch":"fax",  "gaps":1,"pri":"HIGH","why":"Morbid obesity, bilateral knee OA, fall risk; auth ref pending"},
    {"claim":"WC-2026-084444","patient":"Donald Hall",      "equip":"Stair Lift",         "hcpcs":"E1399","ch":"fax",  "gaps":3,"pri":"HIGH","why":"Severe mobility limitation post-fall; auth ref, appt window, and transport all missing"},
    {"claim":"WC-2026-084445","patient":"Helen Allen",      "equip":"Cervical Collar",    "hcpcs":"L0120","ch":"fax",  "gaps":0,"pri":"LOW", "why":"Cervical strain, soft tissue — stable; all fields confirmed"},
    {"claim":"WC-2026-084446","patient":"George Young",     "equip":"Cane — Quad",        "hcpcs":"E0105","ch":"fax",  "gaps":1,"pri":"MED", "why":"Balance deficit post-knee surgery; appt window pending"},
    {"claim":"WC-2026-084447","patient":"Sandra Hernandez", "equip":"Back Brace",         "hcpcs":"L0651","ch":"fax",  "gaps":0,"pri":"LOW", "why":"Lumbar strain — conservative care; all fields confirmed"},
    {"claim":"WC-2026-084448","patient":"Kenneth King",     "equip":"Portable Suction",   "hcpcs":"E2000","ch":"fax",  "gaps":2,"pri":"MED", "why":"Tracheostomy management; auth ref and delivery confirmation missing"},
    {"claim":"WC-2026-084449","patient":"Donna Wright",     "equip":"Rollator Walker",    "hcpcs":"E0143","ch":"fax",  "gaps":0,"pri":"MED", "why":"Hip fracture recovery — standard weight limit; all fields confirmed"},
    {"claim":"WC-2026-084450","patient":"Frank Scott",      "equip":"Power Scooter",      "hcpcs":"K0010","ch":"fax",  "gaps":1,"pri":"HIGH","why":"Bilateral leg amputation, non-ambulatory; auth ref outstanding"},
    {"claim":"WC-2026-084451","patient":"Ruth Green",       "equip":"Patient Lift",       "hcpcs":"E0621","ch":"fax",  "gaps":2,"pri":"HIGH","why":"Complete transfer dependency post-stroke; appt window and transport missing"},
    {"claim":"WC-2026-084452","patient":"Raymond Adams",    "equip":"Hospital Bed",       "hcpcs":"E0250","ch":"fax",  "gaps":0,"pri":"MED", "why":"Home recovery post-spinal fusion; all fields confirmed"},
    {"claim":"WC-2026-084453","patient":"Shirley Baker",    "equip":"Traction Equipment", "hcpcs":"E0840","ch":"fax",  "gaps":1,"pri":"MED", "why":"Cervical disc herniation; transportation confirmation pending"},
    {"claim":"WC-2026-084454","patient":"Carl Nelson",      "equip":"TENS Unit",          "hcpcs":"E0730","ch":"fax",  "gaps":0,"pri":"LOW", "why":"Chronic knee pain — stable; all fields confirmed"},
    {"claim":"WC-2026-084455","patient":"Joyce Carter",     "equip":"Knee Brace",         "hcpcs":"L1820","ch":"fax",  "gaps":1,"pri":"MED", "why":"Meniscus tear — pre-surgical bracing; auth ref pending"},
    {"claim":"WC-2026-084456","patient":"Benjamin Mitchell","equip":"Custom KAFO",        "hcpcs":"L2030","ch":"fax",  "gaps":3,"pri":"HIGH","why":"Bilateral foot drop, severe gait impairment; auth ref, appt window, and transport all missing"},
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
  const isClickable = isHolloway || r.clickable;
  if (status === 'processing') {
    tr.className = 'processing' + (isHolloway ? ' holloway' : '');
  } else if (status === 'routed') {
    tr.className = 'routed' + (isClickable ? ' holloway-done' : '');
    if (isClickable) tr.setAttribute('onclick', 'location.href="pipeline.html"');
  } else if (status === 'gaps') {
    tr.className = 'gaps' + (isClickable ? ' holloway-done' : '');
    if (isClickable) tr.setAttribute('onclick', 'location.href="pipeline.html"');
  }

  const stCell = tr.querySelector('.status-cell');
  if (stCell) stCell.innerHTML = statusBadge(status);

  if (status === 'gaps' && r.gaps > 0) {
    const outCell = tr.querySelector('.outreach-cell');
    if (outCell) outCell.innerHTML = '<span class="outreach-badge">&#x2709; Sent</span>';
  }
}

const PDF_LINKS = `<a href="pdfs/1_referral_form.pdf" target="_blank" class="pdf-open" title="Referral Form">RF</a><a href="pdfs/2_clinical_notes.pdf" target="_blank" class="pdf-open" title="Clinical Notes">CN</a><a href="pdfs/3_prescription.pdf" target="_blank" class="pdf-open" title="Prescription">Rx</a>`;

function queueRow(r, status) {
  const idx = REFERRALS.indexOf(r);
  const chTag = r.ch === 'voice'
    ? '<span class="ch-voice">Voice</span>'
    : '<span class="ch-fax">Fax</span>';
  const priTitle = r.why ? r.why : r.pri;
  const priTag = `<span class="pri-${r.pri}" title="${priTitle}" style="cursor:help">${r.pri}</span>`;
  const gapBadge = r.gaps > 0
    ? `<span class="gap-badge">${r.gaps}</span>`
    : '<span class="gap-badge zero">0</span>';
  const pdfCell = idx < 10 ? PDF_LINKS : '—';

  const patientCell = idx < 10
    ? `${r.patient}<br><span style="margin-top:3px;display:inline-flex;gap:3px">${PDF_LINKS}</span>`
    : r.patient;

  return `<tr id="qr-${r.claim}">
    <td>${patientCell}</td>
    <td style="font-family:monospace;font-size:10px">${r.claim}</td>
    <td>${r.equip} · ${r.hcpcs}</td>
    <td style="text-align:center">${chTag}</td>
    <td class="status-cell" style="text-align:center">${statusBadge(status)}</td>
    <td style="text-align:center">${gapBadge}</td>
    <td class="outreach-cell" style="text-align:center">—</td>
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

(DOCS / "demo.html").write_text(inject_gate(demo_src), encoding="utf-8")
print("  → docs/demo.html")

print("\nDone. All files written to docs/")
print("Files:", [f.name for f in sorted(DOCS.iterdir())])
