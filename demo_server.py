"""
Intake Agent — Live Demo Server
Real agent, real Claude API, real processing.
Run: python demo_server.py
Open: http://localhost:5000
"""
import os, json, time, datetime, threading, uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, request, render_template, send_from_directory, session, redirect, url_for
import secrets

_email_semaphore = threading.Semaphore(5)   # max 5 concurrent email drafts
_claude_semaphore = threading.Semaphore(8)  # max 8 concurrent Claude API calls
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from intake_agent import load_pdfs, extract_fields, check_completeness, draft_outreach_email, save_episode, send_email

DEMO_EMAIL = "coastalinsurance@gmail.com"
from escalation_review import review_bp, add_to_queue

app = Flask(__name__)
app.secret_key = os.environ.get("DEMO_SECRET_KEY", secrets.token_hex(32))
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "coastal2026")
app.register_blueprint(review_bp)

# ── PATHS ─────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
REFERRALS_DIR = BASE_DIR / "referrals"
OUTPUT_DIR    = BASE_DIR / "output"
UPLOAD_DIR    = BASE_DIR / "referrals" / "incoming"
OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

# ── AUTH ──────────────────────────────────────────────────────────────────────
def _authed():
    return session.get("authed") is True

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == DEMO_PASSWORD:
            session["authed"] = True
            return redirect(request.args.get("next") or url_for("index"))
        error = "Incorrect password — try again."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── DEMO REFERRAL METADATA ────────────────────────────────────────────────────
# Voice claims and featured claim loaded from JSON config — no hardcoding here
_voice_cfg    = REFERRALS_DIR / "voice_claims.json"
_featured_cfg = REFERRALS_DIR / "featured_claim.json"
VOICE_CLAIMS   = set(json.loads(_voice_cfg.read_text())    if _voice_cfg.exists()    else [])
FEATURED_CLAIM = json.loads(_featured_cfg.read_text()).strip('"') if _featured_cfg.exists() else ""

def _compute_priority(fields: dict, completeness: dict) -> str:
    """Use Claude's clinical priority assessment from the extraction."""
    p = str(fields.get("priority", "")).strip().upper()
    if p in ("HIGH", "MED", "LOW"):
        return p
    # Fallback if Claude didn't return priority
    if fields.get("escalate"):
        return "HIGH"
    return "MED"

# ── PROCESSING STATE ──────────────────────────────────────────────────────────
_lock = threading.Lock()
_state = {
    "status":    "idle",   # idle | running | complete
    "total":     0,
    "processed": 0,
    "queue":     [],       # list of episode dicts
    "stats": {
        "pages_read": 0, "gaps_detected": 0,
        "outreach_drafted": 0, "routed": 0,
        "icd_conflicts": 0, "escalations": 0,
    },
    "start_time":  None,
    "end_time":    None,
    "wall_sec":    0,
    "events":      [],     # log of agent actions
}

def _log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    with _lock:
        _state["events"].append({"ts": ts, "msg": msg})
        if len(_state["events"]) > 200:
            _state["events"] = _state["events"][-200:]

def _add_queue_item(claim: str):
    channel = "voice" if claim in VOICE_CLAIMS else "fax"
    item = {
        "claim":    claim,
        "patient":  "",
        "equipment": "",
        "channel":  channel,
        "priority": "",
        "priority_reason": "",
        "status":   "queued",
        "gaps":     0,
        "outreach": False,
        "icd_conflict": False,
        "icd_conflict_count": 0,
        "elapsed":  0,
        "is_featured": claim == FEATURED_CLAIM,
    }
    with _lock:
        _state["queue"].append(item)
    return item

def _update_queue_item(claim: str, **kwargs):
    with _lock:
        for item in _state["queue"]:
            if item["claim"] == claim:
                item.update(kwargs)
                break


# ── PROCESS ONE REFERRAL ──────────────────────────────────────────────────────
def process_referral(folder: Path) -> dict:
    claim = folder.name
    t0 = time.time()

    try:
        _update_queue_item(claim, status="processing")

        _log(f"Reading {claim} — {len(list(folder.glob('*.pdf')))} docs")

        # Module 1: Load PDFs
        docs = load_pdfs(str(folder))
        try:
            from pypdf import PdfReader
            pages = sum(len(PdfReader(f).pages) for f in folder.glob("*.pdf"))
        except Exception:
            pages = len(docs) * 2

        # Count pages as soon as PDFs are loaded — before Claude call
        with _lock:
            _state["stats"]["pages_read"] += pages

        # Module 2: Extract + Intelligence (real Claude call)
        _log(f"{claim} — sending to Claude Sonnet")
        with _claude_semaphore:
            fields = extract_fields(docs, claim)
        patient = fields.get("patient_name", "Unknown")
        equipment = fields.get("dme_item", "")

        _update_queue_item(claim, patient=patient, equipment=equipment)
        _log(f"{claim} — extracted: {patient} | {fields.get('icd_code', '—')}")

        # Module 2b: Knowledge Graph — deterministic validation
        from knowledge_graph import validate as kg_validate
        kg_report = kg_validate(fields)
        fields["kg_validation"] = kg_report
        _log(f"{claim} — KG validation: {kg_report['status']} · {kg_report['rules_fired']} rules fired · {kg_report['confirmations']} confirmed")

        # ICD conflict
        if fields.get("icd_conflict"):
            with _lock:
                _state["stats"]["icd_conflicts"] += 1
            _log(f"{claim} — ICD conflict: {fields.get('icd_conflict_detail', '')[:60]}")

        # Escalation
        if fields.get("escalate"):
            with _lock:
                _state["stats"]["escalations"] += 1
            _log(f"{claim} — escalated to human review (confidence {fields.get('confidence')}%)")
            icd_parts = fields.get("icd_conflict_detail", "").split("vs") if "vs" in fields.get("icd_conflict_detail", "") else []
            add_to_queue({
                "claim_number":      fields.get("claim_number", claim),
                "patient_name":      patient,
                "dme_item":          fields.get("dme_item", ""),
                "hcpcs":             fields.get("hcpcs", ""),
                "insurance_carrier": fields.get("insurance_carrier", ""),
                "reason":            "ICD conflict — confidence below 80%",
                "type":              "icd_conflict",
                "icd_correct":       fields.get("icd_code", ""),
                "icd_correct_desc":  fields.get("icd_description", ""),
                "icd_form":          icd_parts[0].strip() if len(icd_parts) > 1 else "",
                "icd_form_desc":     "",
                "conflict_detail":   fields.get("icd_conflict_detail", ""),
                "confidence":        fields.get("confidence", 0),
            })

        # Module 3: Completeness check
        completeness = check_completeness(fields)
        gap_count = len(completeness["gaps"])

        if gap_count > 0:
            with _lock:
                _state["stats"]["gaps_detected"] += gap_count
            _log(f"{claim} — {gap_count} gaps: {', '.join(list(completeness['gaps'].keys())[:3])}")

        elapsed = round(time.time() - t0, 1)
        status = "routed" if completeness["is_complete"] else "gaps"
        priority = _compute_priority(fields, completeness)
        priority_reason = fields.get("priority_reason", "")

        if completeness["is_complete"]:
            with _lock:
                _state["stats"]["routed"] += 1

        # Mark row complete immediately after extraction — email runs in background
        _update_queue_item(
            claim,
            patient=patient,
            equipment=equipment,
            status=status,
            priority=priority,
            priority_reason=priority_reason,
            gaps=gap_count,
            outreach=not completeness["is_complete"],
            icd_conflict=bool(fields.get("icd_conflict")),
            icd_conflict_count=len(fields.get("icd_conflicts", [])),
            elapsed=elapsed,
        )
        _log(f"{claim} — DONE in {elapsed}s | {status.upper()}")

        with _lock:
            _state["processed"] += 1

        # Module 4+5: Email draft + save episode — runs in background (doesn't block row completion)
        def _finalize(fields=fields, completeness=completeness, folder=folder, claim=claim):
            email_body = ""
            email_sent = False
            if not completeness["is_complete"]:
                try:
                    with _email_semaphore:
                        email_body = draft_outreach_email(fields, completeness)
                    subject = f"DME Referral — Missing Information Required · {fields.get('claim_number', claim)}"
                    email_sent = send_email(DEMO_EMAIL, subject, email_body)
                    with _lock:
                        _state["stats"]["outreach_drafted"] += 1
                    _log(f"{claim} — outreach email {'sent' if email_sent else 'drafted'}")
                except Exception as e:
                    _log(f"{claim} — email error: {str(e)[:60]}")
            save_episode(fields, completeness, email_body, email_sent=email_sent, folder=str(folder))
            sidecar = OUTPUT_DIR / f"fields-{claim}-{datetime.date.today().isoformat()}.json"
            sidecar.write_text(json.dumps({
                "fields":        fields,
                "completeness":  completeness,
                "email_body":    email_body,
                "pdf_files":     [f.name for f in sorted(folder.glob("*.pdf"))],
                "icd_conflicts": fields.get("icd_conflicts", []),
            }, indent=2), encoding="utf-8")

        threading.Thread(target=_finalize, daemon=True).start()

        return {"claim": claim, "status": "ok", "elapsed": elapsed}

    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        _update_queue_item(claim, status="error", elapsed=elapsed)
        _log(f"{claim} — ERROR: {str(e)[:80]}")
        with _lock:
            _state["processed"] += 1
        return {"claim": claim, "status": "error", "error": str(e)}


# ── BACKGROUND BATCH RUNNER ───────────────────────────────────────────────────
def run_batch(folders: list, workers: int = 20):
    with _lock:
        _state["status"]     = "running"
        _state["start_time"] = time.time()
        _state["total"]      = len(folders)
        _state["processed"]  = 0

    _log(f"Starting {len(folders)} referrals — {workers} concurrent workers")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_referral, f): f for f in folders}
        for future in as_completed(futures):
            future.result()

    wall = round(time.time() - _state["start_time"], 1)
    with _lock:
        _state["status"]   = "complete"
        _state["end_time"] = time.time()
        _state["wall_sec"] = wall

    _log(f"Batch complete — {len(folders)} referrals in {wall}s ({wall/60:.1f} min)")


# ── API ENDPOINTS ─────────────────────────────────────────────────────────────

PUBLIC_ROUTES = {"login", "static"}

@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ROUTES:
        return
    if not _authed():
        return redirect(url_for("login", next=request.url))

@app.route("/")
def index():
    return render_template("demo.html")


@app.route("/inbox")
def inbox():
    return render_template("inbox.html")


@app.route("/hub")
def hub():
    return render_template("hub.html")


@app.route("/panel/vision")
def panel_vision():
    return render_template("panel_vision.html")


@app.route("/panel/workflow")
def panel_workflow():
    return render_template("panel_workflow.html")


@app.route("/panel/economics")
def panel_economics():
    return render_template("panel_economics.html")


@app.route("/panel/observe")
def panel_observe():
    return render_template("panel_observe.html")


@app.route("/panel/deploy")
def panel_deploy():
    return render_template("panel_deploy.html")


@app.route("/panel/enterprise")
def panel_enterprise():
    return render_template("panel_enterprise.html")


@app.route("/referrals/<claim>/<filename>")
def serve_referral_pdf(claim, filename):
    """Serve a referral PDF directly from the referrals folder."""
    claim_dir = REFERRALS_DIR / claim
    if not claim_dir.exists() or not filename.endswith(".pdf"):
        return "Not found", 404
    return send_from_directory(str(claim_dir), filename, mimetype="application/pdf")


@app.route("/api/referrals")
def api_referrals():
    """Return all referral folders with their PDFs and known metadata."""
    folders = []

    # All claim folders — existing 75 + any live uploads
    claim_dirs = sorted(
        [d for d in REFERRALS_DIR.iterdir()
         if d.is_dir() and not d.name.startswith(".")
         and d.name != "incoming"],
        key=lambda d: d.name
    )

    # Build a patient map from existing sidecar JSONs
    patient_map = {}
    for sidecar in OUTPUT_DIR.glob("fields-*.json"):
        try:
            parts = sidecar.stem.split("-", 1)  # ["fields", "WC-2026-084431-2026-05-09"]
            if len(parts) > 1:
                # claim is everything before the date suffix
                stem = parts[1]  # "WC-2026-084431-2026-05-09"
                # last part is date YYYY-MM-DD
                tokens = stem.rsplit("-", 3)
                if len(tokens) >= 4:
                    claim_key = "-".join(tokens[:-3])
                    data = json.loads(sidecar.read_text(encoding="utf-8"))
                    patient_map[claim_key] = data.get("fields", {}).get("patient_name", "")
        except Exception:
            pass

    for d in claim_dirs:
        claim = d.name
        pdfs = sorted([f.name for f in d.glob("*.pdf")])
        channel = "voice" if claim in VOICE_CLAIMS else "fax"
        is_live = claim.startswith("WC-LIVE") or claim.startswith("WC-INCOMING")
        folders.append({
            "claim":      claim,
            "channel":    channel,
            "pdfs":       pdfs,
            "patient":    patient_map.get(claim, ""),
            "is_featured": claim == FEATURED_CLAIM,
            "is_live":    is_live,
        })

    return jsonify(folders)


@app.route("/api/status")
def api_status():
    with _lock:
        state = dict(_state)
        state["stats"] = dict(_state["stats"])
        state["queue"] = list(_state["queue"])
        state["events"] = list(_state["events"][-30:])
    # Add timing
    if state["start_time"] and state["status"] == "running":
        state["elapsed_sec"] = round(time.time() - state["start_time"], 1)
    elif state["wall_sec"]:
        state["elapsed_sec"] = state["wall_sec"]
    else:
        state["elapsed_sec"] = 0
    # Scale projection
    if state["processed"] > 0 and state["elapsed_sec"] > 0:
        rate = state["processed"] / state["elapsed_sec"]
        state["projection_10k_min"] = round(10000 / rate / 60, 1) if rate > 0 else 0
    else:
        state["projection_10k_min"] = 0
    return jsonify(state)


@app.route("/api/start", methods=["POST"])
def api_start():
    with _lock:
        if _state["status"] == "running":
            return jsonify({"error": "Already running"}), 400

    # Reset state
    with _lock:
        _state["status"]     = "idle"
        _state["processed"]  = 0
        _state["queue"]      = []
        _state["events"]     = []
        _state["start_time"] = None
        _state["end_time"]   = None
        _state["wall_sec"]   = 0
        for k in _state["stats"]:
            _state["stats"][k] = 0

    # Get referral folders (75 demo referrals, exclude benchmark_1000)
    folders = sorted([
        f for f in REFERRALS_DIR.iterdir()
        if f.is_dir() and f.name.startswith("WC-2026-084")
    ])

    # Pre-populate queue
    for f in folders:
        _add_queue_item(f.name)

    default_workers = 20
    workers = int(request.json.get("workers", default_workers)) if request.is_json else default_workers

    # Run in background thread
    t = threading.Thread(target=run_batch, args=(folders, workers), daemon=False)
    t.start()

    return jsonify({"status": "started", "total": len(folders), "workers": workers})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    with _lock:
        _state["status"]     = "idle"
        _state["processed"]  = 0
        _state["queue"]      = []
        _state["events"]     = []
        _state["start_time"] = None
        _state["end_time"]   = None
        _state["wall_sec"]   = 0
        for k in _state["stats"]:
            _state["stats"][k] = 0
    # Clear escalation queue so each demo run starts fresh
    eq_file = OUTPUT_DIR / "escalation_queue.json"
    if eq_file.exists():
        eq_file.write_text("[]", encoding="utf-8")
    return jsonify({"status": "reset"})


@app.route("/pipeline/<claim>")
def pipeline_view(claim):
    matches = sorted(OUTPUT_DIR.glob(f"fields-{claim}-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        return f"<h2>Episode not yet processed: {claim}</h2><p><a href='/'>Back to queue</a></p>", 404
    data = json.loads(matches[0].read_text(encoding="utf-8"))
    f = data["fields"]
    return render_template("pipeline.html",
        claim=claim,
        fields=f,
        completeness=data["completeness"],
        email_body=data["email_body"],
        pdf_files=data.get("pdf_files", []),
        icd_conflicts=data.get("icd_conflicts", []),
        kg=f.get("kg_validation"),
        conf=f.get("confidence"),
        escalate=f.get("escalate", False),
        icd_conf=bool(data.get("icd_conflicts")),
    )


@app.route("/api/outbound-call/<claim>", methods=["POST"])
def api_outbound_call(claim):
    """Trigger a live Vapi outbound call for this episode."""
    from outbound_call import place_outbound_call
    matches = sorted(OUTPUT_DIR.glob(f"fields-{claim}-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        return jsonify({"error": "Episode not found"}), 404
    data = json.loads(matches[0].read_text(encoding="utf-8"))
    fields = data["fields"]
    gaps = list(data["completeness"].get("gaps", {}).keys())
    episode = {
        "patient_name":  fields.get("patient_name", ""),
        "claim_number":  fields.get("claim_number", claim),
        "adjuster_name": fields.get("adjuster_name", "Case Manager"),
        "adjuster_phone": fields.get("adjuster_phone", ""),
        "adjuster_email": fields.get("adjuster_email", ""),
        "gaps": gaps,
    }
    result = place_outbound_call(episode)
    return jsonify(result)


@app.route("/api/episode/<claim>")
def api_episode(claim):
    ep_file = OUTPUT_DIR / f"episode-{claim}-{datetime.date.today().isoformat()}.md"
    # Try any date
    matches = list(OUTPUT_DIR.glob(f"episode-{claim}-*.md"))
    if not matches:
        return jsonify({"error": "Episode not found"}), 404
    content = matches[0].read_text(encoding="utf-8")
    return jsonify({"claim": claim, "content": content, "file": str(matches[0])})


@app.route("/api/escalations")
def api_escalations():
    eq_file = OUTPUT_DIR / "escalation_queue.json"
    if not eq_file.exists():
        return jsonify([])
    data = json.loads(eq_file.read_text(encoding="utf-8"))
    return jsonify(data)


@app.route("/api/upload-fax", methods=["POST"])
def api_upload_fax():
    """Receive a new fax PDF and process it live."""
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    f = request.files["file"]
    claim = f"WC-LIVE-{datetime.datetime.now().strftime('%H%M%S')}"
    folder = REFERRALS_DIR / claim
    folder.mkdir(exist_ok=True)
    f.save(str(folder / "1_referral_form.pdf"))

    # Add to queue
    with _lock:
        _state["queue"].insert(0, {
            "claim": claim, "patient": "Incoming...",
            "equipment": "", "channel": "fax",
            "priority": "", "status": "queued",
            "gaps": 0, "outreach": False,
            "icd_conflict": False, "elapsed": 0,
            "is_featured": False,
        })
        _state["total"] = _state.get("total", 0) + 1

    # Process in background
    t = threading.Thread(
        target=process_referral, args=(folder,), daemon=False
    )
    t.start()
    _log(f"New fax received — {claim} — processing now")

    return jsonify({"status": "processing", "claim": claim})


@app.route("/api/trigger-fax", methods=["POST"])
def api_trigger_fax():
    """Trigger a pre-prepared demo fax referral."""
    # Use a pre-prepared folder if it exists, otherwise use first unprocessed
    demo_fax_dir = BASE_DIR / "demo_fax"
    if demo_fax_dir.exists():
        folder = demo_fax_dir
    else:
        # Fall back to a random unprocessed referral
        folders = sorted([
            f for f in REFERRALS_DIR.iterdir()
            if f.is_dir() and f.name.startswith("WC-2026-085")
        ])
        if not folders:
            return jsonify({"error": "No demo fax prepared"}), 404
        folder = folders[0]

    # claim must match folder.name so _update_queue_item can find the row
    claim = folder.name  # "demo_fax"

    with _lock:
        # Remove any previous demo_fax row
        _state["queue"] = [q for q in _state["queue"] if q.get("claim") != claim]
        _state["queue"].insert(0, {
            "claim": claim, "patient": "Incoming fax...",
            "equipment": "", "channel": "fax",
            "priority": "", "status": "queued",
            "gaps": 0, "outreach": False,
            "icd_conflict": False, "elapsed": 0,
            "is_featured": False,
        })

    _log(f"Demo fax triggered — processing {claim}")
    t = threading.Thread(target=process_referral, args=(folder,), daemon=False)
    t.start()

    return jsonify({"status": "processing", "claim": claim})


# ── RUN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 5000))
    print(f"\nIntake Agent Demo Server")
    print(f"Open: http://localhost:{port}")
    print(f"Real agent: Claude Sonnet | 75 referrals | 20 workers\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
