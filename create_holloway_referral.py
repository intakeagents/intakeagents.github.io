"""
Create the Holloway demo referral package (WC-2026-084431).
Generates 3 PDFs with 3 deliberate ICD-10 conflicts baked into the documents
so the extraction agent discovers them naturally — no hardcoding in code.

Conflicts embedded:
  1. Primary Diagnosis   — Form: M23.611  |  Notes+Rx: S83.209A  → resolves to S83.209A (94%)
  2. Pain Classification — Form: G89.11   |  Notes+Rx: G89.18   → resolves to G89.18 (86%)
  3. Knee Laterality     — Form+Rx: M25.361 | Notes: M25.362    → escalated (split evidence, 71%)
"""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors

OUT_DIR = Path(__file__).parent / "referrals" / "WC-2026-084431"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def h2(text):
    return Paragraph(text, ParagraphStyle("h2", fontSize=10, fontName="Helvetica-Bold",
                                          spaceAfter=3, textColor=colors.HexColor("#1e3a5f")))

def body(text):
    return Paragraph(text, ParagraphStyle("body", fontSize=9, fontName="Helvetica",
                                          spaceAfter=2, leading=13))

def field_table(rows):
    data = [[Paragraph(f"<b>{k}</b>", ParagraphStyle("k", fontSize=9, fontName="Helvetica")),
             Paragraph(str(v),        ParagraphStyle("v", fontSize=9, fontName="Helvetica"))]
            for k, v in rows]
    t = Table(data, colWidths=[2.2*inch, 4.3*inch])
    t.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS",(0,0), (-1,-1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID",          (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    return t

def header_block(doc_type):
    data = [[Paragraph("<b>COASTAL DME SERVICES</b>",
                        ParagraphStyle("o", fontSize=14, fontName="Helvetica-Bold", textColor=colors.white)),
             Paragraph(f"<b>{doc_type}</b>",
                        ParagraphStyle("d", fontSize=11, fontName="Helvetica-Bold", textColor=colors.white))]]
    t = Table(data, colWidths=[3.75*inch, 2.75*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#1e3a5f")),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
    ]))
    return t

def make_doc(path):
    return SimpleDocTemplate(str(path), pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.6*inch, bottomMargin=0.6*inch)


# ── DOCUMENT 1: REFERRAL FORM (submitted by case manager — contains errors) ────
# Form has: M23.611 (pre-surgical code), G89.11 (trauma pain), M25.361 (right knee stiffness)

def build_referral_form():
    doc = make_doc(OUT_DIR / "1_referral_form.pdf")
    story = [header_block("DME REFERRAL FORM"), Spacer(1, 14)]

    story += [h2("PATIENT INFORMATION"), field_table([
        ("Patient Name",          "James Holloway"),
        ("Date of Birth",         "03/14/1968"),
        ("Claim Number",          "WC-2026-084431"),
        ("Injury Date",           "03/14/2026"),
    ])]
    story.append(Spacer(1, 10))

    story += [h2("INSURANCE & AUTHORIZATION"), field_table([
        ("Insurance Carrier",     "Pacific Mutual Workers Comp"),
        ("Adjuster Name",         "Linda Torres"),
        ("Adjuster Phone",        "(714) 555-0182"),
        ("Adjuster Email",        "l.torres@pacificmutual.com"),
        ("Authorization Ref #",   ""),
        ("Policy Number",         "PM-WC-2026-44319"),
    ])]
    story.append(Spacer(1, 10))

    # Conflict 1: Form uses M23.611 (pre-surgical spontaneous ACL disruption — wrong after surgery)
    # Conflict 2: Form uses G89.11 (acute pain due to trauma — should be G89.18 post-procedural)
    # Conflict 3: Form uses M25.361 (RIGHT knee stiffness)
    story += [h2("EQUIPMENT REQUESTED"), field_table([
        ("DME Item",                    "Rollator Walker — Standard 4-Wheel"),
        ("HCPCS Code",                  "E0143"),
        ("Quantity",                    "1"),
        ("Primary Diagnosis (ICD-10)",  "M23.611"),
        ("Diagnosis Description",       "Spontaneous disruption of anterior cruciate ligament, right knee"),
        ("Secondary Diagnosis",         "G89.11 — Acute pain due to trauma"),
        ("Additional Code",             "M25.361 — Stiffness of right knee, not elsewhere classified"),
        ("Special Requirements",        ""),
    ])]
    story.append(Spacer(1, 10))

    story += [h2("DELIVERY"), field_table([
        ("Delivery Address",        "4821 Magnolia Drive, Torrance, CA 90503"),
        ("Preferred Appt Window",   ""),
        ("Transportation Required", ""),
        ("Language / Interpreter",  "English"),
    ])]
    story.append(Spacer(1, 10))

    story += [h2("REFERRING PROVIDER"), field_table([
        ("Physician Name", "Dr. Sarah Chen, MD"),
        ("Practice",       "South Bay Orthopedic Group"),
        ("NPI",            "1234567890"),
        ("Phone",          "(310) 555-0244"),
        ("Fax",            "(310) 555-0245"),
    ])]
    story.append(Spacer(1, 14))
    story += [HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")),
              Spacer(1, 6),
              body("<i>Referral submitted: 03/30/2026 · Case Manager: Linda Torres</i>")]
    doc.build(story)
    print("  Created: 1_referral_form.pdf")


# ── DOCUMENT 2: CLINICAL NOTES (physician record — authoritative source) ───────
# Notes have: S83.209A (correct post-surgical), G89.18 (correct post-procedural), M25.362 (LEFT knee — laterality conflict)

def build_clinical_notes():
    doc = make_doc(OUT_DIR / "2_clinical_notes.pdf")
    story = [header_block("CLINICAL NOTES"), Spacer(1, 14)]

    story += [h2("PATIENT"), field_table([
        ("Name",                "James Holloway  |  DOB: 03/14/1968"),
        ("Claim",               "WC-2026-084431"),
        ("Visit Date",          "03/28/2026"),
        ("Attending Physician", "Dr. Sarah Chen, MD — South Bay Orthopedic Group"),
    ])]
    story.append(Spacer(1, 10))

    # Conflict 1 resolved: Notes use S83.209A (post-surgical meniscus tear — correct)
    # Conflict 2 resolved: Notes use G89.18 (post-procedural pain — correct)
    # Conflict 3 introduced: Notes say LEFT knee (M25.362) — disagrees with form and prescription
    story += [h2("DIAGNOSIS & SURGICAL HISTORY"), field_table([
        ("Primary Diagnosis (ICD-10)",    "S83.209A"),
        ("Diagnosis Description",         "Tear of unspecified meniscus, right knee, initial encounter"),
        ("Post-Procedural Pain (ICD-10)", "G89.18 — Other acute postprocedural pain"),
        ("Knee Stiffness (ICD-10)",       "M25.362 — Stiffness of left knee, not elsewhere classified"),
        ("Injury Date",                   "03/14/2026"),
        ("Surgical Procedure",            "ACL Reconstruction — Right Knee (completed 03/28/2026)"),
    ])]
    story.append(Spacer(1, 10))

    story += [h2("FUNCTIONAL ASSESSMENT")]
    story.append(body(
        "Patient James Holloway presents for post-operative assessment following ACL reconstruction "
        "of the right knee performed on 03/28/2026. Patient reports significant pain and limited "
        "range of motion. Pain level 7/10 at rest, 9/10 with weight-bearing activity. "
        "Ambulation is unsafe without assistive device. Patient is 5'11\" / 285 lbs."
    ))
    story.append(Spacer(1, 6))
    story.append(body(
        "Note: Patient weight (285 lbs) approaches upper limit of standard rollator capacity. "
        "Bariatric rollator (400 lb capacity) should be confirmed with case manager prior to dispatch."
    ))
    story.append(Spacer(1, 10))

    story += [h2("DME RECOMMENDATION"), field_table([
        ("Recommended Equipment",  "Rollator Walker"),
        ("Medical Justification",  "Medically necessary to support safe post-surgical ambulation. "
                                   "Patient cannot safely navigate home environment without assistive device."),
        ("Expected Duration",      "6 months"),
        ("Patient Height/Weight",  "5'11\" / 285 lbs"),
    ])]
    story.append(Spacer(1, 14))
    story += [HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")),
              Spacer(1, 6),
              body("<i>Electronically signed: Dr. Sarah Chen, MD · NPI 1234567890 · 03/28/2026</i>")]
    doc.build(story)
    print("  Created: 2_clinical_notes.pdf")


# ── DOCUMENT 3: PRESCRIPTION (physician Rx — agrees with notes on diagnosis, form on laterality) ──
# Rx has: S83.209A (correct), G89.18 (correct), M25.361 (RIGHT knee — agrees with form, not notes)

def build_prescription():
    doc = make_doc(OUT_DIR / "3_prescription.pdf")
    story = [header_block("DME PRESCRIPTION"), Spacer(1, 14)]

    story += [h2("PRESCRIBING PHYSICIAN"), field_table([
        ("Name",    "Dr. Sarah Chen, MD"),
        ("Practice","South Bay Orthopedic Group"),
        ("NPI",     "1234567890"),
        ("Phone",   "(310) 555-0244"),
    ])]
    story.append(Spacer(1, 10))

    story += [h2("PATIENT"), field_table([
        ("Name",    "James Holloway"),
        ("DOB",     "03/14/1968"),
        ("Claim",   "WC-2026-084431"),
        ("Address", "4821 Magnolia Drive, Torrance, CA 90503"),
    ])]
    story.append(Spacer(1, 10))

    # Conflict 1 resolved: Rx uses S83.209A (agrees with clinical notes)
    # Conflict 2 resolved: Rx uses G89.18 (agrees with clinical notes)
    # Conflict 3 unresolved: Rx uses M25.361 RIGHT knee (agrees with form, not notes → laterality escalated)
    story += [h2("EQUIPMENT ORDER"), field_table([
        ("Item Description",      "Rollator Walker — 4-Wheel"),
        ("HCPCS Code",            "E0143"),
        ("Quantity",              "1"),
        ("Primary Diagnosis",     "S83.209A — Tear of unspecified meniscus, right knee, initial encounter"),
        ("Secondary Diagnosis",   "G89.18 — Other acute postprocedural pain"),
        ("Additional Code",       "M25.361 — Stiffness of right knee, not elsewhere classified"),
        ("Medical Necessity",     "Post-surgical ambulation support following ACL reconstruction. "
                                  "Standard rollator prescribed. Weight capacity to be confirmed."),
        ("Duration of Need",      "6 months"),
    ])]
    story.append(Spacer(1, 14))
    story += [HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")),
              Spacer(1, 6),
              body("<b>Physician Signature:</b> Dr. Sarah Chen, MD"),
              Spacer(1, 4),
              body("<b>Date:</b> 03/30/2026"),
              Spacer(1, 4),
              body("<i>This prescription is valid for 90 days from the date of signing.</i>")]
    doc.build(story)
    print("  Created: 3_prescription.pdf")


if __name__ == "__main__":
    print(f"Creating Holloway referral package -> {OUT_DIR}\n")
    build_referral_form()
    build_clinical_notes()
    build_prescription()
    print(f"\nDone. 3 PDFs with embedded ICD conflicts ready for agent processing.")
    print("Conflicts baked in:")
    print("  1. Primary Diagnosis:    Form=M23.611 | Notes+Rx=S83.209A  → agent resolves to S83.209A")
    print("  2. Pain Classification:  Form=G89.11  | Notes+Rx=G89.18   → agent resolves to G89.18")
    print("  3. Knee Laterality:      Form+Rx=M25.361 | Notes=M25.362  → agent escalates (split evidence)")
