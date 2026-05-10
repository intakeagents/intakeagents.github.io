"""
DME Knowledge Graph Validator
Deterministic ICD-10 / HCPCS rule engine sourced from CMS guidelines.

Loads rules.json (sourced from CMS ICD-10-CM Official Guidelines FY2026
and CMS LCD/NCD documents). Each validation result cites the specific
rule ID and CMS source — no AI probability, 100% deterministic per rule.
"""
import json
from pathlib import Path

RULES_PATH = Path(__file__).parent / "rules.json"

_rules_cache = None


def _load_rules() -> list[dict]:
    global _rules_cache
    if _rules_cache is None:
        _rules_cache = json.loads(RULES_PATH.read_text(encoding="utf-8"))["rules"]
    return _rules_cache


def validate(fields: dict) -> dict:
    """
    Run all applicable rules against extracted episode fields.
    Returns a validation report with fired rules, citations, and actions.
    """
    rules = _load_rules()
    icd_primary    = fields.get("icd_code", "")
    icd_conflicts  = fields.get("icd_conflicts", [])
    hcpcs          = fields.get("hcpcs", "")
    claim_type     = "workers_comp"  # all referrals in this system are WC
    patient_weight = _parse_weight(fields.get("patient_weight", "") or fields.get("notes", ""))
    is_post_surgical = _detect_post_surgical(fields)

    fired   = []   # rules that triggered an action
    checked = []   # all rules evaluated

    for rule in rules:
        result = _evaluate_rule(rule, icd_primary, icd_conflicts, hcpcs,
                                claim_type, patient_weight, is_post_surgical, fields)
        checked.append(rule["rule_id"])
        if result:
            fired.append(result)

    # Derive overall validation status
    has_rejection  = any(f["action"] == "reject"   for f in fired)
    has_escalation = any(f["action"] == "escalate" for f in fired)
    has_flags      = any(f["action"] == "flag"     for f in fired)
    confirmations  = [f for f in fired if f["action"] == "confirm"]

    if has_rejection:
        status = "REJECTED"
    elif has_escalation:
        status = "ESCALATED"
    elif has_flags:
        status = "FLAGGED"
    else:
        status = "VALIDATED"

    meta = json.loads(RULES_PATH.read_text(encoding="utf-8"))["metadata"]

    return {
        "status":          status,
        "rules_checked":   len(checked),
        "rules_fired":     len(fired),
        "confirmations":   len(confirmations),
        "fired_rules":     fired,
        "source":          meta["source"],
        "source_url":      meta["source_url"],
        "rule_set_date":   meta["last_updated"],
        "is_post_surgical": is_post_surgical,
    }


def _evaluate_rule(rule, icd_primary, icd_conflicts, hcpcs,
                   claim_type, patient_weight, is_post_surgical, fields) -> dict | None:
    rid      = rule["rule_id"]
    category = rule["category"]
    action   = rule["action"]
    cond     = rule.get("condition", {})

    # ── POST-SURGICAL ICD REJECT (M23 after surgery) ──────────────────────────
    if category == "post_surgical_coding" and action == "reject":
        invalid_patterns = cond.get("invalid_code_pattern") or cond.get("invalid_code_pattern", "")
        invalid_list = cond.get("invalid_post_surgical_patterns", [])
        if isinstance(invalid_patterns, str) and invalid_patterns:
            invalid_list = [invalid_patterns]
        if is_post_surgical and any(icd_primary.startswith(p) for p in invalid_list):
            replacement = cond.get("valid_replacement_pattern", "")
            return _fired(rule, action,
                f"{icd_primary} rejected — {rule['rejection_reason']}",
                replacement_suggestion=replacement if replacement else None)

    # ── POST-SURGICAL CONFIRM (S83.209A after ACL) ────────────────────────────
    if category == "post_surgical_coding" and action == "confirm":
        valid = cond.get("valid_code", "")
        if valid and icd_primary.startswith(valid[:5]):
            return _fired(rule, "confirm", rule.get("confirmation_reason", ""))

    # ── PAIN CLASSIFICATION REJECT (G89.11 post-surgical) ─────────────────────
    if category == "pain_classification" and action == "reject":
        invalid = cond.get("invalid_code", "")
        # Check primary ICD and all conflict codes
        all_codes = [icd_primary] + [c.get("form_code","") for c in icd_conflicts]
        if is_post_surgical and invalid and any(c == invalid for c in all_codes if c):
            replacement = cond.get("valid_replacement", "")
            return _fired(rule, "reject",
                f"{invalid} rejected — {rule['rejection_reason']}",
                replacement_suggestion=replacement)

    # ── PAIN CLASSIFICATION CONFIRM (G89.18) ──────────────────────────────────
    if category == "pain_classification" and action == "confirm":
        valid = cond.get("valid_code", "")
        secondary_codes = [c.get("resolved_code","") for c in icd_conflicts] + [icd_primary]
        if valid and any(c == valid for c in secondary_codes if c):
            return _fired(rule, "confirm", rule.get("confirmation_reason", ""))

    # ── LATERALITY ESCALATE ────────────────────────────────────────────────────
    if category == "laterality" and action == "escalate":
        lat_conflicts = [c for c in icd_conflicts if c.get("escalate") is True]
        if lat_conflicts:
            codes = [f"{c.get('form_code','')} vs {c.get('notes_code','')}" for c in lat_conflicts]
            return _fired(rule, "escalate",
                f"Laterality conflict detected: {', '.join(codes)} — {rule['escalation_reason']}")

    # ── LATERALITY FLAG (right surgery / left code) ───────────────────────────
    if category == "laterality" and action == "flag":
        conflict_code = cond.get("conflict_code", "")
        all_codes = [icd_primary] + [c.get("form_code","") or c.get("notes_code","") for c in icd_conflicts]
        if conflict_code and any(c == conflict_code for c in all_codes if c):
            return _fired(rule, "flag", rule["flag_reason"])

    # ── HCPCS COVERAGE CONFIRM ────────────────────────────────────────────────
    if category == "hcpcs_coverage" and action == "confirm":
        rule_hcpcs = cond.get("hcpcs", "")
        qualifying = cond.get("qualifying_icd_patterns", [])
        if rule_hcpcs == hcpcs and qualifying:
            if any(icd_primary.startswith(p) for p in qualifying):
                return _fired(rule, "confirm", rule.get("confirmation_reason", ""))

    # ── WEIGHT / BARIATRIC FLAG ────────────────────────────────────────────────
    if category in ("equipment_specification", "hcpcs_coverage") and action == "flag":
        threshold = cond.get("patient_weight_threshold_lbs") or cond.get("patient_weight_lbs_max")
        if threshold and patient_weight and patient_weight >= threshold:
            return _fired(rule, "flag",
                f"Patient weight {patient_weight} lbs — {rule['flag_reason']}")

    # ── WORKERS COMP VALIDATION ───────────────────────────────────────────────
    if category == "workers_comp" and action == "validate":
        required = cond.get("required_fields", [])
        missing = [f for f in required if not fields.get(f)]
        if missing:
            return _fired(rule, "flag",
                f"Workers comp required fields missing: {', '.join(missing)} — {rule['validation_note']}")

    # ── AUTH REF FLAG ─────────────────────────────────────────────────────────
    if category == "authorization" and action == "flag":
        if claim_type == "workers_comp" and not fields.get("auth_ref"):
            return _fired(rule, "flag", rule["flag_reason"])

    # ── WC INJURY CODE REJECT (M-code primary on WC claim) ───────────────────
    if category == "workers_comp" and action == "reject":
        invalid_primary = cond.get("invalid_primary_patterns", [])
        if any(icd_primary.startswith(p) for p in invalid_primary):
            return _fired(rule, "reject",
                f"{icd_primary} — {rule['rejection_reason']}")

    return None


def _fired(rule, action, message, replacement_suggestion=None) -> dict:
    result = {
        "rule_id":    rule["rule_id"],
        "source":     rule["source"],
        "action":     action,
        "message":    message,
        "confidence": rule["confidence"],
        "deterministic": rule.get("deterministic", True),
    }
    if replacement_suggestion:
        result["replacement_suggestion"] = replacement_suggestion
    return result


def _detect_post_surgical(fields: dict) -> bool:
    indicators = [
        fields.get("icd_code", "").startswith("S"),
        "reconstruction" in (fields.get("icd_description") or "").lower(),
        "post" in (fields.get("icd_description") or "").lower(),
        "surgical" in str(fields).lower(),
        "reconstruction" in str(fields).lower(),
    ]
    return sum(indicators) >= 1


def _parse_weight(text: str) -> int | None:
    """Extract patient weight in lbs from a string like '285 lbs' or '285'."""
    import re
    if not text:
        return None
    m = re.search(r"(\d{2,3})\s*(?:lbs?|pounds?)", str(text), re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def format_report(report: dict) -> str:
    """Human-readable validation summary for logging."""
    lines = [
        f"Knowledge Graph Validation — {report['status']}",
        f"Rules checked: {report['rules_checked']} | Fired: {report['rules_fired']} | Confirmations: {report['confirmations']}",
        f"Source: {report['source']}",
        "",
    ]
    for r in report["fired_rules"]:
        icon = {"confirm": "[OK]", "reject": "[REJECT]", "flag": "[FLAG]", "escalate": "[ESC]", "validate": "[CHK]"}.get(r["action"], "[-]")
        det = "DETERMINISTIC" if r.get("deterministic") else "AI-assisted"
        lines.append(f"  {icon} [{r['rule_id']}] {r['action'].upper()} — {r['message']}")
        lines.append(f"     Source: {r['source']} | {det} | Confidence: {r['confidence']}%")
        if r.get("replacement_suggestion"):
            lines.append(f"     Replacement: {r['replacement_suggestion']}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    # Quick smoke test with Holloway's fields
    test_fields = {
        "patient_name": "James Holloway",
        "claim_number": "WC-2026-084431",
        "icd_code": "S83.209A",
        "icd_description": "Tear of unspecified meniscus, right knee, initial encounter — post ACL reconstruction",
        "hcpcs": "E0143",
        "auth_ref": "",
        "insurance_carrier": "Pacific Mutual Workers Comp",
        "adjuster_name": "Linda Torres",
        "patient_weight": "285 lbs",
        "icd_conflicts": [
            {"conflict_id": 1, "label": "Primary Diagnosis", "form_code": "M23.611", "notes_code": "S83.209A", "resolved_code": "S83.209A", "confidence": 94, "escalate": False},
            {"conflict_id": 2, "label": "Pain Classification", "form_code": "G89.11", "notes_code": "G89.18", "resolved_code": "G89.18", "confidence": 90, "escalate": False},
            {"conflict_id": 3, "label": "Knee Laterality", "form_code": "M25.361", "notes_code": "M25.362", "resolved_code": None, "confidence": 71, "escalate": True},
        ],
    }
    report = validate(test_fields)
    print(format_report(report))
