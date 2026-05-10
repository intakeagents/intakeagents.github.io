"""
Escalation Review UI — DME Intake Agent
Serves a web screen for associates to review and correct
low-confidence AI decisions (ICD conflicts, field uncertainties).
Runs as part of the Flask server in voice_webhook.py
"""
import os, json, datetime, uuid
from pathlib import Path
from flask import Blueprint, request, jsonify, render_template_string

review_bp = Blueprint("review", __name__)

QUEUE_FILE = Path(__file__).parent / "output" / "escalation_queue.json"


# ── QUEUE HELPERS ─────────────────────────────────────────────────────────────

def load_queue() -> list:
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    return []

def save_queue(queue: list):
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(queue, indent=2), encoding="utf-8")

def add_to_queue(item: dict):
    queue = load_queue()
    item["id"] = str(uuid.uuid4())[:8]
    item["queued_at"] = datetime.datetime.now().isoformat()
    item["status"] = "pending"
    if "type" not in item:
        item["type"] = "icd_conflict"
    queue.append(item)
    save_queue(queue)
    print(f"  [ESCALATION] Added to review queue: {item.get('claim_number')} — {item.get('reason')}")


# ── HTML TEMPLATE ─────────────────────────────────────────────────────────────

REVIEW_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Escalation Review — Coastal DME</title>
  <meta charset="utf-8">
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f1f5f9;color:#1e293b}
    header{background:#1e3a5f;color:white;padding:14px 24px;display:flex;align-items:center;gap:12px}
    header h1{font-size:16px;font-weight:700}
    header span{font-size:12px;opacity:.6}
    .container{max-width:900px;margin:24px auto;padding:0 16px}
    .badge{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700}
    .badge.pending{background:#fef9c3;color:#854d0e}
    .badge.resolved{background:#dcfce7;color:#166534}
    .badge.ai_resolved{background:#dbeafe;color:#1d4ed8}
    .badge.field_confidence{background:#fff7ed;color:#c2410c}
    .empty{background:white;border-radius:12px;padding:40px;text-align:center;color:#64748b;font-size:14px}
    .card{background:white;border-radius:12px;border:1px solid #e2e8f0;margin-bottom:16px;overflow:hidden}
    .card-header{padding:14px 18px;border-bottom:1px solid #f1f5f9;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
    .card-header h2{font-size:14px;font-weight:700;flex:1}
    .card-body{padding:18px}
    .conflict-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}
    .option{border-radius:10px;padding:14px;border:2px solid transparent;cursor:pointer;transition:all .15s}
    .option.ai{background:#f5f3ff;border-color:#ddd6fe}
    .option.alt{background:#f0fdf4;border-color:#bbf7d0}
    .option h3{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
    .option .code{font-size:18px;font-weight:900;margin-bottom:3px}
    .option .desc{font-size:11px;color:#64748b;line-height:1.5}
    .option .source{font-size:10px;font-weight:700;margin-top:8px;opacity:.7}
    .ai h3{color:#7c3aed}.alt h3{color:#16a34a}
    .confidence-bar{background:#f1f5f9;border-radius:8px;padding:10px 14px;margin-bottom:14px;display:flex;align-items:center;gap:12px}
    .conf-label{font-size:11px;font-weight:700;color:#64748b;width:80px}
    .bar-track{flex:1;height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden}
    .bar-fill{height:100%;border-radius:4px;transition:width .3s}
    .conf-val{font-size:13px;font-weight:800;width:40px;text-align:right}
    .low .bar-fill{background:#ef4444}.low .conf-val{color:#ef4444}
    .med .bar-fill{background:#f59e0b}.med .conf-val{color:#f59e0b}
    .high .bar-fill{background:#22c55e}.high .conf-val{color:#22c55e}
    .field-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:14px}
    .field{background:#f8fafc;border-radius:6px;padding:8px 10px}
    .field .k{font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}
    .field .v{font-size:11px;font-weight:600;color:#1e293b;margin-top:2px}
    .btn-row{display:flex;gap:8px;flex-wrap:wrap}
    .btn{padding:9px 18px;border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;border:none}
    .btn-purple{background:#7c3aed;color:white}
    .btn-green{background:#16a34a;color:white}
    .btn-gray{background:#e2e8f0;color:#475569}
    .btn-red{background:#dc2626;color:white}
    .btn-blue{background:#2563eb;color:white}
    .custom-input{display:none;margin-top:10px;padding:10px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0}
    .custom-input input{width:100%;padding:7px 10px;border-radius:6px;border:1px solid #e2e8f0;font-size:12px;margin-top:4px}
    .custom-input label{font-size:11px;font-weight:700;color:#64748b}
    .resolved-card{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:12px 16px;margin-top:8px;font-size:12px;color:#166534}
    .ai-block{background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:14px 16px;margin-top:4px}
    .ai-block-title{font-size:11px;font-weight:800;color:#1d4ed8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px;display:flex;align-items:center;gap:6px}
    .ai-code-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:10px}
    .ai-code-selected .code-val{font-size:18px;font-weight:900;color:#1d4ed8}
    .ai-code-overrode .code-val{font-size:14px;font-weight:700;color:#94a3b8;text-decoration:line-through}
    .code-label{font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px}
    .code-desc{font-size:11px;color:#64748b;margin-top:2px}
    .ai-reasoning{font-size:11px;color:#1e40af;line-height:1.6;border-top:1px solid #bfdbfe;padding-top:10px;margin-top:4px}
    .field-block{background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;padding:14px 16px}
    .field-block-title{font-size:11px;font-weight:800;color:#c2410c;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}
    .field-vals{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}
    .uncertainty-note{background:#fef9c3;border:1px solid #fde047;border-radius:6px;padding:8px 10px;font-size:11px;color:#713f12;line-height:1.6;margin-bottom:12px}
    .field-input-row{display:flex;gap:8px;margin-top:4px}
    .field-input-row input{flex:1;padding:8px 10px;border-radius:6px;border:1px solid #e2e8f0;font-size:13px;font-weight:700}
    .field-resolved-card{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:12px 16px;font-size:12px;color:#166534}
    .section-divider{font-size:10px;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;padding:6px 0 10px;margin-top:4px}
    .queue-summary{background:white;border-radius:10px;padding:12px 16px;margin-bottom:16px;display:flex;gap:20px;align-items:center;border:1px solid #e2e8f0;flex-wrap:wrap}
    .qs-stat{text-align:center;min-width:60px}
    .qs-n{font-size:22px;font-weight:900}
    .qs-l{font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase}
    .pending-n{color:#d97706}.resolved-n{color:#16a34a}.ai-n{color:#2563eb}.total-n{color:#475569}
  </style>
</head>
<body>
<header>
  <div>
    <h1>Escalation Review — Coastal DME Intake</h1>
    <span>Low-confidence AI decisions requiring human verification</span>
  </div>
</header>
<div class="container">

  <!-- Summary bar -->
  <div class="queue-summary">
    <div class="qs-stat"><div class="qs-n pending-n">{{pending_count}}</div><div class="qs-l">Pending</div></div>
    <div class="qs-stat"><div class="qs-n ai-n">{{ai_resolved_count}}</div><div class="qs-l">AI Resolved</div></div>
    <div class="qs-stat"><div class="qs-n resolved-n">{{human_resolved_count}}</div><div class="qs-l">Human Resolved</div></div>
    <div class="qs-stat"><div class="qs-n total-n">{{total_count}}</div><div class="qs-l">Total</div></div>
    <div style="flex:1"></div>
    <span style="font-size:11px;color:#94a3b8">Auto-refreshes every 30s</span>
  </div>

  {% if items %}
    {% for item in items %}
    <div class="card" id="card-{{loop.index0}}">
      <div class="card-header">
        <h2>{{item.patient_name}} &middot; {{item.claim_number}}</h2>
        {% if item.get('type') == 'field_confidence' %}
          <span class="badge field_confidence">FIELD CHECK</span>
        {% endif %}
        <span class="badge {{item.status}}">
          {% if item.status == 'ai_resolved' %}AI RESOLVED
          {% elif item.status == 'resolved' %}HUMAN RESOLVED
          {% else %}{{item.status.upper()}}{% endif %}
        </span>
        <span style="font-size:11px;color:#94a3b8">{{item.queued_at[:16].replace('T',' ')}}</span>
      </div>
      <div class="card-body">

        <!-- Episode fields -->
        <div class="field-grid">
          <div class="field"><div class="k">DME Item</div><div class="v">{{item.dme_item}}</div></div>
          {% if item.get('type') == 'field_confidence' %}
            <div class="field"><div class="k">Uncertain Field</div><div class="v">{{item.field_label}}</div></div>
          {% else %}
            <div class="field"><div class="k">HCPCS</div><div class="v">{{item.hcpcs}}</div></div>
          {% endif %}
          <div class="field"><div class="k">Carrier</div><div class="v">{{item.insurance_carrier}}</div></div>
          <div class="field"><div class="k">Reason</div><div class="v">{{item.reason}}</div></div>
        </div>

        <!-- Confidence bar -->
        {% set conf = item.confidence|int %}
        {% set conf_class = 'low' if conf < 60 else ('med' if conf < 80 else 'high') %}
        <div class="confidence-bar {{conf_class}}">
          <span class="conf-label">Confidence</span>
          <div class="bar-track"><div class="bar-fill" style="width:{{conf}}%"></div></div>
          <span class="conf-val">{{conf}}%</span>
        </div>

        <!-- ── CARD BODY: branch on type + status ── -->

        {% if item.get('type') == 'field_confidence' %}

          {% if item.status == 'pending' %}
          <!-- Field confidence — needs correction -->
          <div class="field-block">
            <div class="field-block-title">Field Verification Required</div>
            <div class="field-vals">
              <div>
                <div class="code-label">Field</div>
                <div style="font-size:13px;font-weight:700;color:#1e293b">{{item.field_label}}</div>
              </div>
              <div>
                <div class="code-label">AI Read</div>
                <div style="font-size:18px;font-weight:900;color:#c2410c">{{item.extracted_value}}</div>
              </div>
            </div>
            <div class="uncertainty-note">{{item.context}}</div>
            <label style="font-size:11px;font-weight:700;color:#64748b">Confirmed value</label>
            <div class="field-input-row">
              <input type="text" id="field-val-{{loop.index0}}" value="{{item.extracted_value}}" placeholder="Enter correct value">
              <button class="btn btn-green" onclick="submitFieldFix({{loop.index0}}, '{{item.uncertain_field}}', '{{item.id}}', '{{item.claim_number}}')">Confirm</button>
            </div>
          </div>

          {% else %}
          <!-- Field confidence — resolved -->
          <div class="field-resolved-card">
            <b>Corrected by:</b> {{item.get('resolved_by', 'Associate')}} &nbsp;|&nbsp;
            <b>Original:</b> {{item.extracted_value}} &nbsp;&rarr;&nbsp;
            <b>Confirmed:</b> {{item.get('corrected_value', '—')}}
          </div>
          {% endif %}

        {% elif item.status == 'ai_resolved' %}
        <!-- ICD conflict — AI auto-resolved -->
        <div class="ai-block">
          <div class="ai-block-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#1d4ed8" stroke-width="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            AI Auto-Resolved
          </div>
          <div class="ai-code-grid">
            <div class="ai-code-selected">
              <div class="code-label">Selected Code</div>
              <div class="code-val">{{item.icd_correct}}</div>
              <div class="code-desc">{{item.icd_correct_desc}}</div>
            </div>
            <div class="ai-code-overrode">
              <div class="code-label">Overrode</div>
              <div class="code-val">{{item.icd_form}}</div>
              <div class="code-desc">{{item.icd_form_desc}}</div>
            </div>
          </div>
          <div class="ai-reasoning">
            <b>AI reasoning:</b> {{item.get('ai_resolution', item.get('conflict_detail', ''))}}
          </div>
        </div>

        {% elif item.status == 'pending' %}
        <!-- ICD conflict — pending human decision -->
        <p style="font-size:11px;font-weight:700;color:#64748b;margin-bottom:8px;text-transform:uppercase;letter-spacing:.06em">Select the correct ICD-10 code:</p>
        <div class="conflict-grid">
          <div class="option ai" onclick="selectOption({{loop.index0}}, 'ai')">
            <h3>AI Selected</h3>
            <div class="code">{{item.icd_correct}}</div>
            <div class="desc">{{item.icd_correct_desc}}</div>
            <div class="source">Source: Clinical Notes + Prescription</div>
          </div>
          <div class="option alt" onclick="selectOption({{loop.index0}}, 'alt')">
            <h3>Referral Form</h3>
            <div class="code">{{item.icd_form}}</div>
            <div class="desc">{{item.icd_form_desc}}</div>
            <div class="source">Source: Referral Form</div>
          </div>
        </div>

        <div style="background:#fef9c3;border:1px solid #fde047;border-radius:8px;padding:10px 12px;margin-bottom:14px;font-size:11px;color:#713f12;line-height:1.6">
          <b>Conflict detail:</b> {{item.conflict_detail}}
        </div>

        <div class="btn-row">
          <button class="btn btn-purple" onclick="submitDecision({{loop.index0}}, '{{item.icd_correct}}', '{{item.icd_correct_desc}}', 'ai_confirmed', '{{item.id}}', '{{item.claim_number}}')">
            Confirm AI Code ({{item.icd_correct}})
          </button>
          <button class="btn btn-green" onclick="submitDecision({{loop.index0}}, '{{item.icd_form}}', '{{item.icd_form_desc}}', 'form_selected', '{{item.id}}', '{{item.claim_number}}')">
            Use Form Code ({{item.icd_form}})
          </button>
          <button class="btn btn-gray" onclick="showCustom({{loop.index0}})">Enter Different Code</button>
        </div>
        <div class="custom-input" id="custom-{{loop.index0}}">
          <label>ICD-10 Code</label>
          <input type="text" id="custom-code-{{loop.index0}}" placeholder="e.g. S83.001A">
          <label style="margin-top:8px;display:block">Description</label>
          <input type="text" id="custom-desc-{{loop.index0}}" placeholder="Diagnosis description">
          <button class="btn btn-red" style="margin-top:8px" onclick="submitCustom({{loop.index0}}, '{{item.id}}', '{{item.claim_number}}')">Submit Custom Code</button>
        </div>

        {% else %}
        <!-- ICD conflict — resolved by associate -->
        <div class="resolved-card">
          <b>Resolved by:</b> {{item.get('resolved_by', 'Associate')}} &nbsp;|&nbsp;
          <b>Decision:</b> {{item.get('decision_type', '—')}} &nbsp;|&nbsp;
          <b>Code:</b> {{item.get('final_icd', '—')}} &mdash; {{item.get('final_icd_desc', '—')}}
        </div>
        {% endif %}

      </div>
    </div>
    {% endfor %}
  {% else %}
    <div class="empty">No escalations pending — all cases resolved automatically.</div>
  {% endif %}

</div>

<script>
function selectOption(idx, type) {
  document.querySelectorAll(`#card-${idx} .option`).forEach(o => o.style.border = '2px solid transparent');
  const sel = document.querySelector(`#card-${idx} .option.${type === 'ai' ? 'ai' : 'alt'}`);
  if(sel) sel.style.border = '2px solid #2563eb';
}

function showCustom(idx) {
  const el = document.getElementById(`custom-${idx}`);
  el.style.display = el.style.display === 'block' ? 'none' : 'block';
}

function submitDecision(idx, code, desc, decisionType, itemId, claimNumber) {
  fetch('/review/resolve', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      item_id: itemId,
      claim_number: claimNumber,
      resolution_type: 'icd_conflict',
      final_icd: code,
      final_icd_desc: desc,
      decision_type: decisionType,
      resolved_by: 'Associate'
    })
  }).then(r => r.json()).then(d => {
    if(d.status === 'ok') location.reload();
  });
}

function submitCustom(idx, itemId, claimNumber) {
  const code = document.getElementById(`custom-code-${idx}`).value.trim();
  const desc = document.getElementById(`custom-desc-${idx}`).value.trim();
  if(!code) { alert('Please enter an ICD-10 code'); return; }
  submitDecision(idx, code, desc, 'custom_entry', itemId, claimNumber);
}

function submitFieldFix(idx, fieldName, itemId, claimNumber) {
  const val = document.getElementById(`field-val-${idx}`).value.trim();
  if(!val) { alert('Please enter the confirmed value'); return; }
  fetch('/review/resolve', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      item_id: itemId,
      claim_number: claimNumber,
      resolution_type: 'field_confidence',
      field_name: fieldName,
      corrected_value: val,
      resolved_by: 'Associate'
    })
  }).then(r => r.json()).then(d => {
    if(d.status === 'ok') location.reload();
  });
}

setTimeout(() => location.reload(), 30000);
</script>
</body>
</html>
"""


# ── ROUTES ────────────────────────────────────────────────────────────────────

@review_bp.route("/review")
def review_queue():
    queue = load_queue()

    pending_icd   = [i for i in queue if i.get("status") == "pending"     and i.get("type", "icd_conflict") == "icd_conflict"]
    pending_field = [i for i in queue if i.get("status") == "pending"     and i.get("type") == "field_confidence"]
    ai_resolved   = [i for i in queue if i.get("status") == "ai_resolved"]
    human_resolved= [i for i in queue if i.get("status") == "resolved"]

    items = pending_icd + pending_field + ai_resolved + human_resolved

    return render_template_string(
        REVIEW_HTML,
        items=items,
        pending_count=len(pending_icd) + len(pending_field),
        ai_resolved_count=len(ai_resolved),
        human_resolved_count=len(human_resolved),
        total_count=len(queue),
    )


@review_bp.route("/review/resolve", methods=["POST"])
def resolve_item():
    data = request.get_json()
    item_id = data.get("item_id")
    resolution_type = data.get("resolution_type", "icd_conflict")
    queue = load_queue()

    for item in queue:
        if item.get("id") == item_id and item.get("status") == "pending":
            item["resolved_by"] = data.get("resolved_by", "Associate")
            item["resolved_at"] = datetime.datetime.now().isoformat()

            if resolution_type == "field_confidence":
                item["status"] = "resolved"
                item["corrected_value"] = data.get("corrected_value")
                _update_episode_field(item)
            else:
                item["status"] = "resolved"
                item["final_icd"] = data.get("final_icd")
                item["final_icd_desc"] = data.get("final_icd_desc")
                item["decision_type"] = data.get("decision_type")
                _update_episode(item)
            break

    save_queue(queue)
    return jsonify({"status": "ok"})


def _update_episode(item: dict):
    """Patch the episode markdown with the associate's ICD decision."""
    date = datetime.date.today().isoformat()
    claim = item.get("claim_number", "UNKNOWN")
    path = Path(__file__).parent / "output" / f"episode-{claim}-{date}.md"
    if not path.exists():
        return

    content = path.read_text(encoding="utf-8")
    old_line = next((l for l in content.splitlines() if "ICD-10:" in l), None)
    if old_line:
        new_line = f"- **ICD-10:** {item['final_icd']} — {item['final_icd_desc']} ✓ *Associate confirmed*"
        content = content.replace(old_line, new_line)

    content = content.replace(
        "🚨 ESCALATED TO HUMAN REVIEW",
        f"✓ RESOLVED BY ASSOCIATE — {item['decision_type']}"
    )
    content += (
        f"\n\n## Escalation Resolution"
        f"\n- **Decision:** {item['decision_type']}"
        f"\n- **Final ICD:** {item['final_icd']} — {item['final_icd_desc']}"
        f"\n- **Resolved at:** {item['resolved_at']}"
    )
    path.write_text(content, encoding="utf-8")
    print(f"  [REVIEW] Episode updated with associate decision: {item['final_icd']}")


def _update_episode_field(item: dict):
    """Patch the episode markdown with the associate's field correction."""
    date = datetime.date.today().isoformat()
    claim = item.get("claim_number", "UNKNOWN")
    path = Path(__file__).parent / "output" / f"episode-{claim}-{date}.md"
    if not path.exists():
        return

    field_name = item.get("field_name", item.get("uncertain_field", ""))
    corrected  = item.get("corrected_value", "")

    # Map field names to the markdown label fragment to find the right line
    label_map = {
        "hcpcs":    "**HCPCS:**",
        "auth_ref": "**Auth Ref:**",
        "icd_code": "**ICD-10:**",
        "dme_item": "**Item:**",
        "physician_npi": "**Physician:**",
    }
    label = label_map.get(field_name)

    content = path.read_text(encoding="utf-8")
    if label:
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if label in line:
                # Replace the value portion after the label
                prefix = line[:line.index(label) + len(label)]
                lines[i] = f"{prefix} {corrected} ✓ *Associate confirmed*"
                break
        content = "\n".join(lines)

    content += (
        f"\n\n## Field Correction — {field_name}"
        f"\n- **Original:** {item.get('extracted_value')}"
        f"\n- **Corrected:** {corrected}"
        f"\n- **Resolved at:** {item.get('resolved_at')}"
    )
    path.write_text(content, encoding="utf-8")
    print(f"  [REVIEW] Episode field corrected: {field_name} -> {corrected}")
