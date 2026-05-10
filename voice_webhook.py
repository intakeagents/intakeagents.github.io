"""
Vapi Voice Webhook — DME Intake Agent
Receives call-end events from Vapi, extracts fields,
and feeds them into the same intake pipeline as PDF referrals.
Run this alongside intake_agent.py.
"""
import os, json, datetime, threading
from pathlib import Path
from flask import Flask, request, jsonify
from pyngrok import ngrok
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Import shared pipeline modules from intake_agent
from intake_agent import check_completeness, draft_outreach_email, send_email, save_episode
from escalation_review import review_bp, add_to_queue

app = Flask(__name__)
app.register_blueprint(review_bp)
VAPI_KEY = os.environ.get("VAPI_API_Key", "")

OUTPUT_DIR = Path(__file__).parent / "output"

# Fields Vapi assistant should capture — must match assistant prompt
VAPI_FIELD_MAP = {
    "patient_name":     ["patient name", "patient_name", "name"],
    "dob":              ["date of birth", "dob", "date_of_birth"],
    "claim_number":     ["claim number", "claim_number", "claim"],
    "auth_ref":         ["authorization reference", "auth_ref", "auth number"],
    "dme_item":         ["equipment", "dme_item", "device", "item"],
    "hcpcs":            ["hcpcs code", "hcpcs", "billing code"],
    "delivery_address": ["delivery address", "address"],
    "appt_window":      ["appointment", "appt_window", "preferred time"],
    "transportation":   ["transportation", "transport"],
    "language":         ["language", "interpreter"],
    "insurance_carrier":["insurance", "carrier", "insurance_carrier"],
    "adjuster_name":    ["adjuster", "adjuster_name", "case manager"],
    "adjuster_email":   ["adjuster email", "adjuster_email"],
    "adjuster_phone":   ["adjuster phone", "adjuster_phone"],
    "physician_name":   ["physician", "doctor", "physician_name"],
    "physician_npi":    ["npi", "physician_npi"],
    "icd_code":         ["diagnosis code", "icd", "icd_code"],
    "icd_description":  ["diagnosis", "icd_description"],
}


# ── REFERRAL QUEUE ────────────────────────────────────────────────────────────

REFERRAL_QUEUE_FILE = OUTPUT_DIR / "referral_queue.json"

def load_referral_queue() -> list:
    if REFERRAL_QUEUE_FILE.exists():
        return json.loads(REFERRAL_QUEUE_FILE.read_text(encoding="utf-8"))
    return []

def save_referral_queue(queue: list):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REFERRAL_QUEUE_FILE.write_text(json.dumps(queue, indent=2), encoding="utf-8")

def add_to_referral_queue(call_data: dict):
    queue = load_referral_queue()
    call_id = call_data.get("id", "unknown")
    entry = {
        "call_id":       call_id,
        "channel":       "voice",
        "status":        "processing",
        "received_at":   datetime.datetime.now().isoformat(),
        "caller_number": call_data.get("customer", {}).get("number", "unknown"),
        "duration_sec":  call_data.get("duration", 0),
        "ended_reason":  call_data.get("endedReason", "unknown"),
        "claim_number":  None,
        "patient_name":  None,
        "episode_path":  None,
    }
    queue.append(entry)
    save_referral_queue(queue)
    print(f"  [REFERRAL QUEUE] Added: call {call_id[:8]}")
    return call_id

def update_referral_queue(call_id: str, updates: dict):
    queue = load_referral_queue()
    for entry in queue:
        if entry.get("call_id") == call_id:
            entry.update(updates)
            break
    save_referral_queue(queue)


# ── TRANSCRIPT ────────────────────────────────────────────────────────────────

def save_transcript(call_data: dict) -> Path:
    call_id   = call_data.get("id", "unknown")
    date      = datetime.date.today().isoformat()
    artifact  = call_data.get("artifact", {})
    messages  = artifact.get("messages", [])
    analysis  = call_data.get("analysis", {})

    lines = [
        f"# Call Transcript",
        f"**Call ID:** {call_id}",
        f"**Date:** {date}",
        f"**Duration:** {call_data.get('duration', 0)}s",
        f"**Ended reason:** {call_data.get('endedReason', 'unknown')}",
        f"**Caller:** {call_data.get('customer', {}).get('number', 'unknown')}",
        "",
        "---",
        "",
        "## Conversation",
        "",
    ]

    for msg in messages:
        role    = msg.get("role", "unknown")
        content = msg.get("content", "").strip()
        if not content:
            continue
        if role in ("bot", "assistant"):
            label = "AGENT"
        elif role in ("user", "human"):
            label = "CALLER"
        else:
            label = role.upper()
        lines.append(f"**{label}:** {content}")
        lines.append("")

    if analysis.get("summary"):
        lines += ["---", "", "## Call Summary", "", analysis["summary"], ""]

    if analysis.get("structuredData"):
        lines += ["## Structured Data Extracted", "```json",
                  json.dumps(analysis["structuredData"], indent=2), "```", ""]

    out_path = OUTPUT_DIR / f"transcript-{call_id[:8]}-{date}.md"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [TRANSCRIPT] Saved: {out_path.name}")
    return out_path


# ── FIELD EXTRACTION ──────────────────────────────────────────────────────────

def extract_from_call(call_data: dict) -> dict:
    """
    Map Vapi call artifact fields to our episode record format.
    Tries structuredData first, falls back to transcript/analysis.
    """
    fields = {k: "" for k in VAPI_FIELD_MAP}

    artifact   = call_data.get("artifact", {})
    structured = artifact.get("structuredData", {})
    if structured:
        for our_field, vapi_keys in VAPI_FIELD_MAP.items():
            for vk in vapi_keys:
                if vk in structured:
                    fields[our_field] = structured[vk]
                    break
        print("  [VOICE] Fields from structured data")
        return fields

    analysis = call_data.get("analysis", {})
    if analysis.get("structuredData"):
        sd = analysis["structuredData"]
        for our_field, vapi_keys in VAPI_FIELD_MAP.items():
            for vk in vapi_keys:
                if vk in sd:
                    fields[our_field] = sd[vk]
                    break

    fields["call_id"]       = call_data.get("id", "")
    fields["call_duration"] = (
        str(call_data.get("costs", [{}])[0].get("minutes", "")) + " min"
        if call_data.get("costs") else ""
    )
    fields["channel"] = "voice"

    print("  [VOICE] Fields from transcript/analysis")
    return fields


# ── PIPELINE ──────────────────────────────────────────────────────────────────

def process_voice_referral(call_data: dict):
    """Full intake pipeline for a voice referral."""
    print("\n" + "="*60)
    print("VOICE INTAKE — Processing call")
    print("="*60)

    call_id      = call_data.get("id", "unknown")
    ended_reason = call_data.get("endedReason", "unknown")
    duration     = call_data.get("duration", 0)
    print(f"  Call ID:  {call_id}")
    print(f"  Duration: {duration}s | Ended: {ended_reason}")

    # Save transcript immediately
    print("\n[0] Saving call transcript...")
    save_transcript(call_data)

    # Extract fields
    print("\n[1] Extracting fields from call...")
    fields = extract_from_call(call_data)
    fields["icd_conflict"]        = False
    fields["icd_conflict_detail"] = ""
    fields["confidence"]          = 100
    fields["escalate"]            = False
    fields["notes"]               = f"Voice intake via Vapi · Call ID: {call_id} · Duration: {duration}s"

    patient = fields.get("patient_name", "Unknown")
    claim   = fields.get("claim_number") or f"VOICE-{datetime.date.today().isoformat()}-{call_id[:6]}"
    fields["claim_number"] = claim
    print(f"  Patient: {patient} | Claim: {claim}")

    # Completeness check
    print("\n[2] Completeness check...")
    completeness = check_completeness(fields)
    if completeness["is_complete"]:
        print("  All fields captured on call — routing directly")
    else:
        print(f"  GAPS: {len(completeness['gaps'])} found:")
        for f, c in completeness["gaps"].items():
            print(f"    - {f} [{c}]")

    # Outreach for remaining gaps
    email_body = ""
    email_sent = False
    if not completeness["is_complete"] and fields.get("adjuster_email"):
        print("\n[3] Drafting outreach for remaining gaps...")
        email_body = draft_outreach_email(fields, completeness)
        subject    = f"DME Referral — Missing Information · {claim}"
        email_sent = send_email(fields.get("adjuster_email", ""), subject, email_body)
    else:
        print("\n[3] No gaps or no adjuster email — skipping outreach")

    # Save episode
    print("\n[4] Saving episode record...")
    out_path = save_episode(fields, completeness, email_body, email_sent, "voice")

    # Update referral queue with completed status
    final_status = "complete" if completeness["is_complete"] else "pending_info"
    update_referral_queue(call_id, {
        "status":       final_status,
        "claim_number": claim,
        "patient_name": patient,
        "episode_path": str(out_path),
        "completed_at": datetime.datetime.now().isoformat(),
        "gaps":         list(completeness.get("gaps", {}).keys()),
    })

    status = "ROUTED" if completeness["is_complete"] else "PENDING_CM_RESPONSE"
    print(f"\nVOICE INTAKE COMPLETE — {status}")
    print(f"Episode:    {out_path}")
    print(f"Transcript: output/transcript-{call_id[:8]}-{datetime.date.today().isoformat()}.md")
    print("="*60 + "\n")


# ── FOLDER WATCHER ───────────────────────────────────────────────────────────

REFERRALS_DIR     = Path(__file__).parent / "referrals"
PROCESSED_FILE    = OUTPUT_DIR / "processed_folders.json"

def load_processed() -> set:
    if PROCESSED_FILE.exists():
        return set(json.loads(PROCESSED_FILE.read_text(encoding="utf-8")))
    return set()

def save_processed(processed: set):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_FILE.write_text(json.dumps(sorted(processed)), encoding="utf-8")

def watch_referrals_folder():
    """Poll referrals/ every 5 s — auto-process any new PDF folder."""
    import time
    from intake_agent import run as run_intake

    print("  [WATCHER] Monitoring referrals/ for new PDF folders...")
    while True:
        try:
            processed = load_processed()
            if REFERRALS_DIR.exists():
                for folder in sorted(REFERRALS_DIR.iterdir()):
                    if folder.is_dir() and folder.name not in processed:
                        pdfs = list(folder.glob("*.pdf"))
                        if pdfs:
                            print(f"\n[WATCHER] New referral detected: {folder.name} — starting intake")
                            processed.add(folder.name)
                            save_processed(processed)
                            threading.Thread(
                                target=run_intake,
                                args=(str(folder),),
                                daemon=False
                            ).start()
        except Exception as e:
            print(f"  [WATCHER] Error: {e}")
        time.sleep(5)


# ── WEBHOOK ENDPOINT ──────────────────────────────────────────────────────────

@app.route("/vapi-webhook", methods=["POST"])
def vapi_webhook():
    data       = request.get_json(silent=True) or {}
    event_type = data.get("message", {}).get("type", "") or data.get("type", "")

    print(f"\n[WEBHOOK] Received: {event_type}")

    if event_type in ("end-of-call-report", "call.ended", "end_of_call_report"):
        call_data = data.get("message", {}).get("call", {}) or data.get("call", {}) or data
        # Add to referral queue immediately (before processing)
        add_to_referral_queue(call_data)
        # Process pipeline in background thread — fully automatic, no click needed
        threading.Thread(target=process_voice_referral, args=(call_data,), daemon=True).start()
        return jsonify({"status": "processing"}), 200

    return jsonify({"status": "ignored", "type": event_type}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "DME Voice Intake Webhook"}), 200


@app.route("/referrals", methods=["GET"])
def referral_queue_view():
    queue = load_referral_queue()
    return jsonify({"count": len(queue), "referrals": queue})


# ── STARTUP ───────────────────────────────────────────────────────────────────

def update_vapi_webhook(public_url: str):
    import httpx
    assistant_id = "50709c92-4768-4571-ae17-40176aa72989"
    webhook_url  = f"{public_url}/vapi-webhook"
    r = httpx.patch(
        f"https://api.vapi.ai/assistant/{assistant_id}",
        headers={"Authorization": f"Bearer {VAPI_KEY}"},
        json={"serverUrl": webhook_url}
    )
    if r.status_code == 200:
        print(f"  Vapi assistant updated -> {webhook_url}")
    else:
        print(f"  Vapi update failed: {r.status_code} {r.text[:200]}")


if __name__ == "__main__":
    print("\nStarting DME Voice Intake Webhook...")

    ngrok_token = os.environ.get("NGrok_auth_token") or os.environ.get("NGROK_AUTHTOKEN", "")
    if ngrok_token:
        ngrok.set_auth_token(ngrok_token)

    tunnel     = ngrok.connect(5050)
    public_url = tunnel.public_url
    print(f"\n  Public URL: {public_url}")
    print(f"  Webhook:    {public_url}/vapi-webhook")

    print("\n  Updating Vapi assistant webhook URL...")
    update_vapi_webhook(public_url)

    print("\n  Listening for calls on +1 (201) 897-3854")
    print("  Outbound calls fire automatically (no click needed)")
    print("  Review screen:   http://localhost:5050/review")
    print("  Referral queue:  http://localhost:5050/referrals")
    print("  Ctrl+C to stop\n")

    # Start folder watcher — auto-processes any PDF dropped in referrals/
    threading.Thread(target=watch_referrals_folder, daemon=True).start()

    app.run(port=5050, debug=False)
