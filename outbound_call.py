"""
Outbound Voice Outreach — DME Intake Agent
Places an outbound call via Vapi to the case manager
when email outreach has not been responded to.
"""
import os, json, httpx, datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

VAPI_KEY        = os.environ.get("VAPI_API_Key", "")
ASSISTANT_ID    = "50709c92-4768-4571-ae17-40176aa72989"
PHONE_NUMBER_ID = "9613a479-df90-40a7-a9bb-b9cddadd20a5"
FALLBACK_PHONE  = os.environ.get("OUTBOUND_FALLBACK_PHONE", "+12012148911")

HEADERS = {
    "Authorization": f"Bearer {VAPI_KEY}",
    "Content-Type": "application/json",
}


def normalize_phone(phone: str) -> str:
    """Convert any US phone format to E.164 (+1XXXXXXXXXX)."""
    import re
    if not phone:
        return ""
    if phone.startswith("+"):
        return phone
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits[0] == "1":
        return f"+{digits}"
    return ""


def place_outbound_call(episode: dict) -> dict:
    """
    Place an outbound call to the case manager to collect missing fields.
    episode must contain: adjuster_name, adjuster_phone, patient_name,
                          claim_number, gaps (list of missing field names)
    """
    adjuster_name  = episode.get("adjuster_name", "Case Manager")
    adjuster_phone = FALLBACK_PHONE  # always ring demo number
    patient_name   = episode.get("patient_name", "the patient")
    claim_number   = episode.get("claim_number", "unknown")
    gaps           = episode.get("gaps", [])

    # Build a dynamic first message so the AI leads with context
    gap_str = ", ".join(gaps) if gaps else "some missing information"
    first_message = (
        f"Hello, may I speak with {adjuster_name}? "
        f"This is the Coastal DME intake system calling regarding "
        f"a referral for {patient_name}, claim number {claim_number}. "
        f"We sent an email earlier about some missing information we need "
        f"to process this referral — specifically {gap_str}. "
        f"Could you help us with those details now?"
    )

    payload = {
        "assistantId": ASSISTANT_ID,
        "phoneNumberId": PHONE_NUMBER_ID,
        "customer": {
            "number": adjuster_phone,
            "name": adjuster_name,
        },
        "assistantOverrides": {
            "firstMessage": first_message,
            "variableValues": {
                "patient_name": patient_name,
                "claim_number": claim_number,
                "missing_fields": gap_str,
            }
        }
    }

    print(f"  [OUTBOUND] Calling {adjuster_name} at {adjuster_phone}...")
    print(f"  [OUTBOUND] Claim: {claim_number} | Missing: {gap_str}")

    r = httpx.post("https://api.vapi.ai/call", headers=HEADERS, json=payload)

    if r.status_code in (200, 201):
        call = r.json()
        call_id = call.get("id", "unknown")
        print(f"  [OUTBOUND] Call placed. ID: {call_id}")
        return {"success": True, "call_id": call_id, "status": call.get("status")}
    else:
        print(f"  [OUTBOUND] Failed: {r.status_code} — {r.text[:200]}")
        return {"success": False, "reason": r.text[:200]}


def check_and_call(episode_path: str):
    """
    Read a saved episode file, check if still pending, place outbound call if so.
    Call this after 24 hours from a scheduler or manually.
    """
    path = Path(episode_path)
    if not path.exists():
        print(f"Episode not found: {episode_path}")
        return

    content = path.read_text(encoding="utf-8")

    # Only call if still pending
    if "PENDING_CM_RESPONSE" not in content:
        print("  Episode already resolved — no call needed")
        return

    # Parse key fields from the markdown episode record
    episode = {}
    for line in content.splitlines():
        if "**Name:**" in line:
            episode["patient_name"] = line.split("**Name:**")[-1].strip()
        elif "**Claim #:**" in line:
            episode["claim_number"] = line.split("**Claim #:**")[-1].strip()
        elif "**Adjuster:**" in line:
            parts = line.split("**Adjuster:**")[-1].strip().split("·")
            episode["adjuster_name"] = parts[0].strip()
            episode["adjuster_email"] = parts[1].strip() if len(parts) > 1 else ""
        elif line.startswith("- `") and "HARD BLOCK" in line or "REQUIRED" in line:
            field = line.split("`")[1]
            episode.setdefault("gaps", []).append(field)

    # Adjuster phone not stored in markdown — pass it in or look it up
    episode["adjuster_phone"] = episode.get("adjuster_phone", "")

    print(f"\nPlacing outbound call for episode: {path.name}")
    result = place_outbound_call(episode)
    print(f"  Result: {result}")


# ── STANDALONE TEST ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Pass an episode file path to trigger outbound call
        check_and_call(sys.argv[1])
    else:
        # Quick test with sample data
        print("Testing outbound call with sample episode...")
        test_episode = {
            "patient_name":   "James Holloway",
            "claim_number":   "WC-2026-084431",
            "adjuster_name":  "Linda Torres",
            "adjuster_phone": "+12012148911",
            "adjuster_email": "l.torres@pacificmutual.com",
            "gaps": ["auth_ref", "appt_window", "transportation"],
        }
        result = place_outbound_call(test_episode)
        print(f"\nResult: {result}")
