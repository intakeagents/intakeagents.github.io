"""
DME Referral Intake Agent
Reads a folder of referral PDFs, extracts fields, detects gaps,
drafts outreach email, saves completed episode to output/
"""
import os
import json
import base64
import smtplib
import datetime
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], timeout=120.0)
    return _client

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")

REQUIRED_FIELDS = [
    "patient_name", "dob", "claim_number",
    "auth_ref", "appt_window", "transportation",
    "language", "dme_item", "hcpcs", "delivery_address",
    "physician_name", "physician_npi",
    "insurance_carrier", "adjuster_name", "adjuster_email",
    "icd_code", "icd_description",
]

HARD_BLOCKS = {"auth_ref", "appt_window", "dme_item", "hcpcs", "delivery_address"}


# ── MODULE 1: INTAKE ──────────────────────────────────────────────────────────

def load_pdfs(folder: str) -> list[dict]:
    """Read all PDFs in the folder and encode as base64."""
    docs = []
    for f in sorted(Path(folder).glob("*.pdf")):
        with open(f, "rb") as fh:
            docs.append({
                "filename": f.name,
                "b64": base64.standard_b64encode(fh.read()).decode("utf-8"),
            })
    print(f"  Loaded {len(docs)} documents: {[d['filename'] for d in docs]}")
    return docs


# ── MODULE 2: EXTRACTION + INTELLIGENCE ──────────────────────────────────────

def extract_fields(docs: list[dict], claim_number: str) -> dict:
    """Send all PDFs to Claude in one call. Extract fields and detect ICD conflicts."""

    content = []
    for doc in docs:
        content.append({
            "type": "text",
            "text": f"Document: {doc['filename']}"
        })
        content.append({
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": doc["b64"],
            }
        })

    content.append({
        "type": "text",
        "text": """You are a DME referral intake specialist. Extract all available fields from these referral documents.

Return a single JSON object with these keys (use empty string "" if not found):
- patient_name, dob, claim_number
- injury_date (date of injury or accident)
- policy_number (insurance policy number)
- auth_ref (authorization reference number)
- appt_window (preferred appointment date/time window)
- transportation (transportation confirmation: yes/no/arranged/blank)
- language (language or interpreter requirement)
- dme_item (equipment description)
- hcpcs (HCPCS code)
- quantity (quantity ordered, default "1" if not stated)
- delivery_address
- physician_name, physician_npi, physician_practice, physician_phone
- insurance_carrier, adjuster_name, adjuster_email, adjuster_phone
- icd_code (the CORRECT ICD-10 code after cross-referencing all documents)
- icd_description
- icd_conflict (true/false — was there ANY conflict across documents?)
- icd_conflict_detail (explain the primary conflict found and how you resolved it)
- confidence (0-100 — your confidence in the primary icd_code if there was a conflict)
- escalate (true/false — true if ANY conflict has confidence < 80)
- icd_conflicts (array — one entry per ICD code conflict found across all documents):
    Each entry: {
      "conflict_id": integer starting at 1,
      "label": short label for this code e.g. "Primary Diagnosis" or "Pain Classification",
      "form_code": ICD code as it appears on the referral form,
      "notes_code": ICD code as it appears in clinical notes,
      "rx_code": ICD code as it appears on the prescription,
      "resolved_code": the correct code you selected (null if escalating),
      "confidence": 0-100,
      "escalate": true/false for this specific conflict,
      "reasoning": one sentence explaining how you resolved or why you escalated
    }
    Leave as [] if no conflicts found.
- priority (HIGH/MED/LOW — based purely on clinical risk, diagnosis severity, and equipment urgency):
    HIGH: acute injuries, fractures, post-surgical cases, neurological conditions (ALS, MS, spinal cord), power mobility devices, escalation needed, ICD conflict with low confidence
    MED: chronic musculoskeletal conditions, orthopedic braces/supports, moderate mobility aids, respiratory equipment, resolved ICD conflicts
    LOW: stable chronic conditions, preventive/supportive equipment, minor aids
- priority_reason (one sentence explaining the priority assignment)
- notes (any other important observations)

Cross-reference ICD codes across ALL documents. If there is a conflict, resolve it using clinical notes and prescription as the authority over the referral form. Set confidence accordingly.

Return ONLY valid JSON. No explanation outside the JSON."""
    })

    print("  Sending to Claude for extraction...")
    import time as _time
    for _attempt in range(3):
        try:
            response = _get_client().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                messages=[{"role": "user", "content": content}]
            )
            break
        except Exception as _e:
            if _attempt == 2:
                raise
            is_rate_limit = "rate" in str(_e).lower() or "529" in str(_e) or "overloaded" in str(_e).lower()
            wait = min((2 ** _attempt) * (3 if is_rate_limit else 1), 5)  # cap at 5s
            print(f"  API error (attempt {_attempt+1}): {_e} — retrying in {wait}s")
            _time.sleep(wait)

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    # Extract just the JSON object — handles extra text after closing brace
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]
    return json.loads(raw)


# ── MODULE 3: COMPLETENESS CHECK ─────────────────────────────────────────────

def check_completeness(fields: dict) -> dict:
    """Identify missing fields and classify by criticality."""
    gaps = {}
    for f in REQUIRED_FIELDS:
        val = fields.get(f, "")
        if not val or str(val).strip() == "":
            criticality = "HARD BLOCK" if f in HARD_BLOCKS else "REQUIRED"
            gaps[f] = criticality

    hard_blocks = [k for k, v in gaps.items() if v == "HARD BLOCK"]
    required = [k for k, v in gaps.items() if v == "REQUIRED"]

    return {
        "gaps": gaps,
        "hard_blocks": hard_blocks,
        "required_missing": required,
        "is_complete": len(gaps) == 0,
    }


# ── MODULE 4: OUTREACH DRAFT ──────────────────────────────────────────────────

def draft_outreach_email(fields: dict, completeness: dict) -> str:
    """Ask Claude to write the outreach email to the case manager."""
    gap_list = list(completeness["gaps"].keys())
    adjuster = fields.get("adjuster_name", "Case Manager")
    claim = fields.get("claim_number", "Unknown")
    patient = fields.get("patient_name", "Patient")

    prompt = f"""Draft a professional outreach email to {adjuster} at {fields.get('adjuster_email', '')}.

Context:
- Patient: {patient}
- Claim: {claim}
- Missing fields needed to complete this DME referral: {', '.join(gap_list)}
- Hard blocks (hold routing): {', '.join(completeness['hard_blocks'])}

Requirements:
- Professional and concise
- List each missing item clearly and specifically
- State the 24-business-hour response deadline
- Reference the claim number
- Sign as: Coastal DME Intake Agent

Return only the email body (no subject line)."""

    import time as _time
    for _attempt in range(3):
        try:
            response = _get_client().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as _e:
            if _attempt == 2:
                raise
            is_rate_limit = "rate" in str(_e).lower() or "529" in str(_e) or "overloaded" in str(_e).lower()
            wait = min((2 ** _attempt) * (3 if is_rate_limit else 1), 5)  # cap at 5s
            print(f"  API error drafting email (attempt {_attempt+1}): {_e} — retrying in {wait}s")
            _time.sleep(wait)


# ── MODULE 5: SEND EMAIL ──────────────────────────────────────────────────────

def send_email(to_address: str, subject: str, body: str) -> bool:
    """Send via Gmail SMTP. Returns True if sent."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("  [EMAIL] Gmail not configured — saving draft only")
        return False
    if not to_address:
        print("  [EMAIL] No adjuster email found — saving draft only")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = to_address
        msg["Bcc"] = GMAIL_USER
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"  [EMAIL] Sent to {to_address} (BCC: {GMAIL_USER})")
        return True
    except Exception as e:
        print(f"  [EMAIL] Failed: {e}")
        return False


# ── MODULE 6: ROUTE OUTPUT ────────────────────────────────────────────────────

def save_episode(fields: dict, completeness: dict, email_body: str, email_sent: bool, folder: str):
    """Write the completed episode record to output/"""
    claim = fields.get("claim_number", "UNKNOWN")
    date = datetime.date.today().isoformat()
    out_path = Path(__file__).parent / "output" / f"episode-{claim}-{date}.md"

    status = "ROUTED" if completeness["is_complete"] else "PENDING_CM_RESPONSE"

    lines = [
        f"# Episode Record — {claim}",
        f"**Status:** {status}",
        f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Patient",
        f"- **Name:** {fields.get('patient_name', '—')}",
        f"- **DOB:** {fields.get('dob', '—')}",
        f"- **Claim #:** {fields.get('claim_number', '—')}",
        "",
        "## Insurance",
        f"- **Carrier:** {fields.get('insurance_carrier', '—')}",
        f"- **Adjuster:** {fields.get('adjuster_name', '—')} · {fields.get('adjuster_email', '—')}",
        f"- **Auth Ref:** {fields.get('auth_ref', '⚠ MISSING')}",
        "",
        "## Equipment",
        f"- **Item:** {fields.get('dme_item', '—')}",
        f"- **HCPCS:** {fields.get('hcpcs', '—')}",
        f"- **ICD-10:** {fields.get('icd_code', '—')} — {fields.get('icd_description', '—')}",
    ]

    if fields.get("icd_conflict"):
        lines.append(f"- **⚠ ICD Conflict Detected:** {fields.get('icd_conflict_detail', '')}")
        lines.append(f"- **Confidence:** {fields.get('confidence', '—')}%")
        if fields.get("escalate"):
            lines.append("- **🚨 ESCALATED TO HUMAN REVIEW** (confidence < 80%)")

    lines += [
        "",
        "## Logistics",
        f"- **Delivery Address:** {fields.get('delivery_address', '—')}",
        f"- **Appointment Window:** {fields.get('appt_window', '⚠ MISSING')}",
        f"- **Transportation:** {fields.get('transportation', '⚠ MISSING')}",
        f"- **Language:** {fields.get('language', '—')}",
        "",
        "## Provider",
        f"- **Physician:** {fields.get('physician_name', '—')} · NPI {fields.get('physician_npi', '—')}",
        "",
    ]

    if completeness["gaps"]:
        lines += ["## Gaps Detected", ""]
        for field, crit in completeness["gaps"].items():
            lines.append(f"- `{field}` — **{crit}**")
        lines.append("")

    lines += [
        "## Outreach",
        f"- **Email sent:** {'Yes' if email_sent else 'No (draft saved)'}",
        f"- **To:** {fields.get('adjuster_email', '—')}",
        "",
        "### Email Draft",
        "```",
        email_body,
        "```",
    ]

    if fields.get("notes"):
        lines += ["", "## Agent Notes", fields.get("notes")]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Episode saved: {out_path}")
    return out_path


# ── MODULE 7: OUTBOUND CALL SCHEDULER ────────────────────────────────────────

def schedule_outbound_call(fields: dict, completeness: dict, episode_path: Path, delay_hours: float = None):
    """Fire an outbound Vapi call after delay_hours if episode still pending."""
    from outbound_call import place_outbound_call

    if delay_hours is None:
        delay_hours = float(os.environ.get("CALL_DELAY_HOURS", "24"))
    delay_seconds = delay_hours * 3600
    print(f"     (fires in {delay_hours}h = {int(delay_seconds/60)} min)")

    def _call_after_delay():
        import time
        time.sleep(delay_seconds)
        # Re-check episode status before calling
        content = Path(episode_path).read_text(encoding="utf-8")
        if "PENDING_CM_RESPONSE" not in content:
            print(f"\n[AUTO-CALL] {fields.get('claim_number')} already resolved — skipping call")
            return
        print(f"\n[AUTO-CALL] 24h elapsed — placing outbound call for {fields.get('claim_number')}")
        episode = {
            "patient_name":   fields.get("patient_name", ""),
            "claim_number":   fields.get("claim_number", ""),
            "adjuster_name":  fields.get("adjuster_name", ""),
            "adjuster_phone": fields.get("adjuster_phone", ""),
            "adjuster_email": fields.get("adjuster_email", ""),
            "gaps":           list(completeness.get("gaps", {}).keys()),
        }
        place_outbound_call(episode)

    t = threading.Thread(target=_call_after_delay, daemon=False)
    t.start()
    print(f"     Outbound call queued — fires in {delay_hours}h for {fields.get('claim_number')}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def run(referral_folder: str):
    print(f"\n{'='*60}")
    print(f"INTAKE AGENT — Processing: {referral_folder}")
    print(f"{'='*60}")

    # Module 1: Load PDFs
    print("\n[1] Loading documents...")
    docs = load_pdfs(referral_folder)

    # Module 2: Extract + Intelligence
    print("\n[2] Extracting fields + intelligence layer...")
    fields = extract_fields(docs, claim_number="unknown")

    print(f"  Patient:  {fields.get('patient_name')} | Claim: {fields.get('claim_number')}")
    print(f"  ICD Code: {fields.get('icd_code')} (conflict: {fields.get('icd_conflict', False)})")
    if fields.get("icd_conflict"):
        print(f"  Conflict: {fields.get('icd_conflict_detail')}")
        print(f"  Confidence: {fields.get('confidence')}% | Escalate: {fields.get('escalate')}")

    # Module 2b: Knowledge Graph — deterministic validation
    print("\n[2b] Knowledge graph validation (deterministic)...")
    from knowledge_graph import validate as kg_validate, format_report
    kg_report = kg_validate(fields)
    fields["kg_validation"] = kg_report
    print(format_report(kg_report))

    # Escalation queue — low-confidence ICD decisions routed to human review
    if fields.get("escalate"):
        from escalation_review import add_to_queue
        icd_parts = fields.get("icd_conflict_detail", "").split("vs") if "vs" in fields.get("icd_conflict_detail", "") else []
        add_to_queue({
            "claim_number":    fields.get("claim_number", "UNKNOWN"),
            "patient_name":    fields.get("patient_name", "Unknown"),
            "dme_item":        fields.get("dme_item", "—"),
            "hcpcs":           fields.get("hcpcs", "—"),
            "insurance_carrier": fields.get("insurance_carrier", "—"),
            "reason":          "ICD conflict — confidence below 80%",
            "conflict_detail": fields.get("icd_conflict_detail", ""),
            "confidence":      fields.get("confidence", 0),
            "icd_correct":     fields.get("icd_code", ""),
            "icd_correct_desc": fields.get("icd_description", ""),
            "icd_form":        icd_parts[0].strip() if len(icd_parts) > 1 else "",
            "icd_form_desc":   "",
        })
        print("  [ESCALATION] Queued for human review at /review")

    # Module 3: Completeness check
    print("\n[3] Completeness check...")
    completeness = check_completeness(fields)
    if completeness["is_complete"]:
        print("  ✓ All required fields present — routing directly")
    else:
        print(f"  GAPS: {len(completeness['gaps'])} found:")
        for f, c in completeness["gaps"].items():
            print(f"    - {f} [{c}]")

    # Module 4: Draft outreach email
    email_body = ""
    email_sent = False
    if not completeness["is_complete"]:
        print("\n[4] Drafting outreach email...")
        email_body = draft_outreach_email(fields, completeness)
        print("  Draft ready.")

        # Module 5: Send email
        print("\n[5] Sending outreach...")
        subject = f"DME Referral — Missing Information Required · {fields.get('claim_number', 'Unknown Claim')}"
        email_sent = send_email(fields.get("adjuster_email", ""), subject, email_body)
    else:
        print("\n[4/5] No gaps — skipping outreach")

    # Module 6: Save episode
    print("\n[6] Saving episode record...")
    out_path = save_episode(fields, completeness, email_body, email_sent, referral_folder)

    # Module 7: Schedule outbound call after 24h if gaps remain
    if email_sent and not completeness["is_complete"]:
        print("\n[7] Outbound call scheduled — auto-triggers in 24h if gaps unresolved")
        schedule_outbound_call(fields, completeness, out_path)

    print(f"\n{'='*60}")
    print(f"COMPLETE — Status: {'ROUTED' if completeness['is_complete'] else 'PENDING_CM_RESPONSE'}")
    print(f"Episode: {out_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import sys
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "referrals", "WC-2026-084431"
    )
    run(folder)
