"""
Generate a realistic 3-document DME referral package for James Holloway.
Outputs to referrals/WC-2026-084431/
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "referrals", "WC-2026-084431")
os.makedirs(OUT_DIR, exist_ok=True)

styles = getSampleStyleSheet()

def h1(text):
    return Paragraph(text, ParagraphStyle("h1", fontSize=13, fontName="Helvetica-Bold", spaceAfter=4))

def h2(text):
    return Paragraph(text, ParagraphStyle("h2", fontSize=10, fontName="Helvetica-Bold", spaceAfter=3, textColor=colors.HexColor("#1e3a5f")))

def body(text):
    return Paragraph(text, ParagraphStyle("body", fontSize=9, fontName="Helvetica", spaceAfter=2, leading=13))

def field_table(rows):
    data = [[Paragraph(f"<b>{k}</b>", ParagraphStyle("k", fontSize=9, fontName="Helvetica")),
             Paragraph(str(v), ParagraphStyle("v", fontSize=9, fontName="Helvetica"))]
            for k, v in rows]
    t = Table(data, colWidths=[2.2*inch, 4.3*inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    return t

def header_block(doc_type):
    data = [[
        Paragraph("<b>COASTAL DME SERVICES</b>", ParagraphStyle("org", fontSize=14, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)),
        Paragraph(f"<b>{doc_type}</b>", ParagraphStyle("dt", fontSize=11, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)),
    ]]
    t = Table(data, colWidths=[3.75*inch, 2.75*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#1e3a5f")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
    ]))
    return t


# ── DOC 1: REFERRAL FORM ─────────────────────────────────────────────────────

def build_referral_form():
    path = os.path.join(OUT_DIR, "1_referral_form.pdf")
    doc = SimpleDocTemplate(path, pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.6*inch, bottomMargin=0.6*inch)
    story = []

    story.append(header_block("DME REFERRAL FORM"))
    story.append(Spacer(1, 14))

    story.append(h2("PATIENT INFORMATION"))
    story.append(field_table([
        ("Patient Name", "James Holloway"),
        ("Date of Birth", "03/14/1968"),
        ("Claim Number", "WC-2026-084431"),
        ("Injury Date", "03/28/2026"),
        ("Gender", "Male"),
    ]))
    story.append(Spacer(1, 10))

    story.append(h2("INSURANCE & AUTHORIZATION"))
    story.append(field_table([
        ("Insurance Carrier", "Pacific Mutual Workers Comp"),
        ("Adjuster Name", "Linda Torres"),
        ("Adjuster Phone", "(714) 555-0182"),
        ("Adjuster Email", "l.torres@pacificmutual.com"),
        ("Authorization Ref #", ""),          # intentionally blank — gap
        ("Policy Number", "PM-WC-2026-44319"),
    ]))
    story.append(Spacer(1, 10))

    story.append(h2("EQUIPMENT REQUESTED"))
    story.append(field_table([
        ("DME Item", "Rollator Walker"),
        ("HCPCS Code", "E0143"),
        ("Quantity", "1"),
        ("Diagnosis Code (ICD-10)", "M23.611"),   # conflict — wrong code
        ("Diagnosis Description", "Derangement of medial meniscus, right knee"),
        ("Special Requirements", ""),              # intentionally blank — gap
    ]))
    story.append(Spacer(1, 10))

    story.append(h2("DELIVERY"))
    story.append(field_table([
        ("Delivery Address", "4821 Magnolia Drive, Torrance, CA 90503"),
        ("Preferred Appt Window", ""),             # intentionally blank — gap
        ("Transportation Required", ""),           # intentionally blank — gap
        ("Language / Interpreter", "English"),
    ]))
    story.append(Spacer(1, 10))

    story.append(h2("REFERRING PROVIDER"))
    story.append(field_table([
        ("Physician Name", "Dr. Sarah Chen"),
        ("Practice", "South Bay Orthopedic Group"),
        ("NPI", "1234567890"),
        ("Phone", "(310) 555-0244"),
        ("Fax", "(310) 555-0245"),
    ]))
    story.append(Spacer(1, 14))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
    story.append(Spacer(1, 6))
    story.append(body("<i>Referral submitted: 04/07/2026 · Case Manager: Rachel Kim · Pacific Mutual WC</i>"))

    doc.build(story)
    print(f"  Created: {path}")


# ── DOC 2: CLINICAL NOTES ────────────────────────────────────────────────────

def build_clinical_notes():
    path = os.path.join(OUT_DIR, "2_clinical_notes.pdf")
    doc = SimpleDocTemplate(path, pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.6*inch, bottomMargin=0.6*inch)
    story = []

    story.append(header_block("CLINICAL NOTES"))
    story.append(Spacer(1, 14))

    story.append(h2("PATIENT"))
    story.append(field_table([
        ("Name", "James Holloway  |  DOB: 03/14/1968"),
        ("Claim", "WC-2026-084431"),
        ("Visit Date", "04/05/2026"),
        ("Attending Physician", "Dr. Sarah Chen, MD — South Bay Orthopedic Group"),
    ]))
    story.append(Spacer(1, 10))

    story.append(h2("SURGICAL HISTORY"))
    story.append(field_table([
        ("Procedure", "Right knee ACL reconstruction + medial meniscus repair"),
        ("Date of Surgery", "03/28/2026"),
        ("Facility", "Torrance Memorial Medical Center"),
        ("Surgeon", "Dr. Sarah Chen, MD"),
        ("Diagnosis (Post-Op)", "S83.209A — Unspecified tear of unspecified meniscus, right knee, initial encounter"),
    ]))
    story.append(Spacer(1, 10))

    story.append(h2("POST-OPERATIVE ASSESSMENT — 04/05/2026"))
    story.append(body(
        "Patient is 8 days post right knee ACL reconstruction with concurrent medial meniscus repair. "
        "Wound healing is progressing within normal parameters. Patient reports pain level 4/10 at rest, "
        "7/10 with weight-bearing. Limited ROM — flexion to 45 degrees. Extension full. "
        "Significant swelling persists over the medial compartment."
    ))
    story.append(Spacer(1, 8))
    story.append(body(
        "Patient is currently non-weight-bearing on right lower extremity per post-op protocol. "
        "Physical therapy initiated 04/03/2026 — 3x per week. Patient is ambulatory with axillary "
        "crutches but demonstrating difficulty with stairs and uneven surfaces. "
        "Home environment assessment indicates patient resides in a two-story dwelling."
    ))
    story.append(Spacer(1, 10))

    story.append(h2("FUNCTIONAL LIMITATIONS"))
    story.append(field_table([
        ("Weight Bearing Status", "Non-weight-bearing right lower extremity"),
        ("Mobility Aid — Current", "Axillary crutches"),
        ("Mobility Aid — Recommended", "Rollator Walker (4-wheeled) with seat — improved stability for home use"),
        ("Expected Duration of Need", "8–12 weeks post-operative"),
        ("Height / Weight", "5'11\" / 195 lbs"),
    ]))
    story.append(Spacer(1, 10))

    story.append(h2("PLAN"))
    story.append(body(
        "Continue non-weight-bearing protocol for 3 additional weeks. "
        "DME order for rollator walker to support home ambulation and stair navigation. "
        "Standard rollator walker appropriate — patient weight within standard equipment limits. "
        "Follow-up scheduled 04/21/2026."
    ))
    story.append(Spacer(1, 14))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
    story.append(Spacer(1, 6))
    story.append(body("<i>Electronically signed: Dr. Sarah Chen, MD · NPI 1234567890 · 04/05/2026</i>"))

    doc.build(story)
    print(f"  Created: {path}")


# ── DOC 3: PRESCRIPTION ──────────────────────────────────────────────────────

def build_prescription():
    path = os.path.join(OUT_DIR, "3_prescription.pdf")
    doc = SimpleDocTemplate(path, pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.6*inch, bottomMargin=0.6*inch)
    story = []

    story.append(header_block("DME PRESCRIPTION"))
    story.append(Spacer(1, 14))

    story.append(h2("PRESCRIBING PHYSICIAN"))
    story.append(field_table([
        ("Name", "Dr. Sarah Chen, MD"),
        ("Practice", "South Bay Orthopedic Group"),
        ("Address", "3200 Lomita Blvd, Suite 400, Torrance, CA 90505"),
        ("Phone", "(310) 555-0244"),
        ("NPI", "1234567890"),
        ("DEA / License", "CA-MD-78234"),
    ]))
    story.append(Spacer(1, 10))

    story.append(h2("PATIENT"))
    story.append(field_table([
        ("Name", "James Holloway"),
        ("DOB", "03/14/1968"),
        ("Claim", "WC-2026-084431"),
        ("Address", "4821 Magnolia Drive, Torrance, CA 90503"),
    ]))
    story.append(Spacer(1, 10))

    story.append(h2("EQUIPMENT ORDER"))
    story.append(field_table([
        ("Item Description", "Rollator Walker, 4-wheeled, with hand brakes and padded seat"),
        ("HCPCS Code", "E0143"),
        ("Quantity", "1"),
        ("ICD-10 Diagnosis", "S83.209A — Tear of meniscus, right knee, initial encounter"),
        ("Medical Necessity", "Post-operative ambulation support following right knee ACL reconstruction and medial meniscus repair (03/28/2026). Patient non-weight-bearing. Standard crutches insufficient for home stair navigation."),
        ("Duration of Need", "3 months"),
        ("Refills", "None"),
    ]))
    story.append(Spacer(1, 14))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
    story.append(Spacer(1, 6))
    story.append(body("<b>Physician Signature:</b> Dr. Sarah Chen, MD"))
    story.append(Spacer(1, 4))
    story.append(body("<b>Date:</b> 04/07/2026"))
    story.append(Spacer(1, 4))
    story.append(body("<i>This prescription is valid for 90 days from the date of signing.</i>"))

    doc.build(story)
    print(f"  Created: {path}")


if __name__ == "__main__":
    print("Generating sample referral package — WC-2026-084431 (James Holloway)...")
    build_referral_form()
    build_clinical_notes()
    build_prescription()
    print("\nDone. 3 PDFs saved to referrals/WC-2026-084431/")
    print("Gaps built in: Authorization Ref #, Appointment Window, Transportation, Special Requirements")
    print("ICD conflict built in: Form says M23.611, Notes + Prescription say S83.209A")
