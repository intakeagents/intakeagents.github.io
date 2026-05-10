"""
Generate 75 realistic DME referral packages (3 PDFs each = 225 total files).
Each package has varied patients, equipment, carriers, gaps, and some ICD conflicts.
Output: referrals/<claim_number>/1_referral_form.pdf, 2_clinical_notes.pdf, 3_prescription.pdf
"""
import os, random
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors

random.seed(42)
OUT_BASE = Path(__file__).parent / "referrals"

# ── REFERENCE DATA ────────────────────────────────────────────────────────────

PATIENTS = [
    ("James Holloway","03/14/1968"),("Maria Santos","07/22/1975"),("Robert Chen","11/05/1982"),
    ("Linda Williams","04/18/1959"),("David Okafor","09/30/1971"),("Patricia Nguyen","02/14/1966"),
    ("Michael Thompson","06/25/1978"),("Sandra Rivera","01/08/1983"),("Thomas Washington","12/17/1970"),
    ("Karen Patel","05/03/1964"),("Christopher Lee","08/11/1987"),("Barbara Martinez","03/29/1961"),
    ("Daniel Johnson","10/14/1979"),("Lisa Anderson","07/07/1973"),("Mark Taylor","11/22/1965"),
    ("Susan Brown","02/16/1969"),("Paul Harris","04/30/1985"),("Nancy Clark","09/12/1957"),
    ("Kevin Lewis","06/08/1980"),("Dorothy Walker","01/25/1963"),("Steven Hall","08/19/1976"),
    ("Betty Allen","12/04/1960"),("Edward Young","03/17/1984"),("Ruth Hernandez","05/28/1967"),
    ("Ronald King","07/13/1972"),("Sharon Wright","10/01/1958"),("Timothy Scott","02/22/1981"),
    ("Carol Green","04/15/1974"),("Jason Adams","09/07/1986"),("Deborah Baker","06/19/1962"),
    ("Jeffrey Nelson","11/30/1977"),("Anna Carter","01/11/1988"),("Gary Mitchell","08/24/1955"),
    ("Helen Perez","03/06/1971"),("Eric Roberts","05/20/1983"),("Amanda Turner","12/14/1966"),
    ("Scott Phillips","07/03/1979"),("Melissa Campbell","02/27/1961"),("Brian Parker","10/16/1986"),
    ("Rebecca Evans","04/09/1968"),("Larry Edwards","06/23/1975"),("Virginia Collins","09/18/1970"),
    ("Frank Stewart","01/14/1982"),("Kathleen Sanchez","11/07/1959"),("Raymond Morris","03/31/1984"),
    ("Catherine Rogers","07/16/1965"),("Dennis Reed","05/04/1978"),("Janet Cook","12/28/1972"),
    ("Jerry Morgan","08/10/1963"),("Judith Bell","02/03/1980"),("Walter Murphy","04/21/1957"),
    ("Diane Bailey","10/25/1974"),("Peter Rivera","06/14/1989"),("Gloria Cooper","01/30/1960"),
    ("Harold Richardson","09/22/1976"),("Rose Cox","03/08/1985"),("Wayne Howard","07/27/1969"),
    ("Cheryl Ward","11/15/1973"),("Arthur Torres","05/11/1981"),("Mildred Peterson","02/19/1956"),
    ("Albert Gray","08/06/1987"),("Brenda Ramirez","04/12/1962"),("Roy James","12/01/1978"),
    ("Evelyn Watson","06/29/1971"),("Willie Brooks","10/17/1983"),("Pamela Kelly","01/05/1967"),
    ("Ralph Sanders","09/24/1975"),("Emma Price","03/13/1990"),("Joe Bennett","07/20/1964"),
    ("Shirley Wood","11/08/1977"),("Louis Barnes","02/15/1982"),("Teresa Ross","05/26/1958"),
    ("Carl Henderson","08/03/1985"),("Alice Coleman","04/18/1969"),("Juan Jenkins","12/11/1973"),
]

DME_ITEMS = [
    ("Rollator Walker","E0143","M79.3","Myalgia","S83.209A","Tear of meniscus, right knee, initial encounter",True),
    ("Power Wheelchair","K0823","M54.5","Low back pain","M47.816","Spondylosis with radiculopathy, lumbar region",True),
    ("Hospital Bed","E0250","M19.011","Primary osteoarthritis, right shoulder","M19.011","Primary osteoarthritis, right shoulder",False),
    ("CPAP Machine","E0601","G47.33","Obstructive sleep apnea","G47.33","Obstructive sleep apnea",False),
    ("Knee Brace","L1820","M23.201","Derangement of medial meniscus, right knee","S83.005A","Unspecified tear of medial meniscus, right knee",True),
    ("Forearm Crutches","E0110","S72.001A","Fracture of unspecified part of neck of right femur","S72.001A","Fracture of neck of right femur, initial encounter",False),
    ("Transcutaneous Electrical Nerve Stimulation (TENS)","E0730","M54.4","Lumbago with sciatica","M51.16","Intervertebral disc degeneration, lumbar region",True),
    ("Commode Chair","E0163","G35","Multiple sclerosis","G35","Multiple sclerosis",False),
    ("Cervical Collar","L0174","S14.109A","Unspecified injury at C4 level of cervical spinal cord","S13.4XXA","Sprain of ligaments of cervical spine",True),
    ("Lumbar Orthosis","L0625","M54.5","Low back pain","M47.22","Anterior spinal artery compression syndromes, cervical region",True),
    ("Nebulizer","E0570","J45.51","Severe persistent asthma with acute exacerbation","J45.51","Severe persistent asthma with acute exacerbation",False),
    ("Ankle Foot Orthosis","L1906","S82.001A","Fracture of right patella","S82.892A","Other fracture of left lower leg",True),
    ("Manual Wheelchair","E1161","G12.21","Amyotrophic lateral sclerosis","G12.21","Amyotrophic lateral sclerosis",False),
    ("Continuous Glucose Monitor","A9276","E11.9","Type 2 diabetes mellitus without complications","E11.65","Type 2 diabetes mellitus with hyperglycemia",True),
    ("Shoulder Immobilizer","L3670","S40.011A","Contusion of right shoulder","S43.004A","Unspecified dislocation of right shoulder joint",True),
]

CARRIERS = [
    ("Pacific Mutual Workers Comp","Linda Torres","l.torres@pacificmutual.com","(714) 555-0182"),
    ("Zenith National Insurance","Robert Campos","r.campos@zenithnational.com","(800) 555-0234"),
    ("ICW Group","Jennifer Walsh","j.walsh@icwgroup.com","(619) 555-0156"),
    ("State Compensation Insurance Fund","Marcus Webb","m.webb@statefund.com","(415) 555-0298"),
    ("Travelers Workers Comp","Sarah Mitchell","s.mitchell@travelers.com","(312) 555-0177"),
    ("Liberty Mutual Workers Comp","James Archer","j.archer@libertymutual.com","(617) 555-0211"),
    ("Hartford Financial Services","Diana Cruz","d.cruz@hartford.com","(860) 555-0143"),
    ("AmTrust Financial","Kevin Osei","k.osei@amtrust.com","(216) 555-0189"),
]

PHYSICIANS = [
    ("Dr. Sarah Chen, MD","1234567890","South Bay Orthopedic Group","(310) 555-0244","(310) 555-0245"),
    ("Dr. Marcus Johnson, MD","2345678901","Valley Spine Institute","(818) 555-0167","(818) 555-0168"),
    ("Dr. Priya Sharma, MD","3456789012","Pacific Neurology Associates","(310) 555-0322","(310) 555-0323"),
    ("Dr. Robert Williams, MD","4567890123","Desert Orthopedics","(760) 555-0211","(760) 555-0212"),
    ("Dr. Lisa Park, MD","5678901234","Bay Area Physical Medicine","(415) 555-0188","(415) 555-0189"),
    ("Dr. Carlos Mendez, MD","6789012345","Southern California Spine Center","(949) 555-0244","(949) 555-0245"),
]

ADDRESSES = [
    "4821 Magnolia Drive, Torrance, CA 90503",
    "1247 Ocean View Blvd, Long Beach, CA 90802",
    "892 Sunset Ridge Road, Pasadena, CA 91101",
    "3341 Harbor Light Lane, San Pedro, CA 90731",
    "567 Maple Street Apt 4B, Compton, CA 90220",
    "2198 Hillcrest Avenue, Inglewood, CA 90301",
    "445 Pacific Coast Highway, Redondo Beach, CA 90277",
    "1089 Valley View Drive, Burbank, CA 91505",
    "3756 Cherry Blossom Court, Gardena, CA 90247",
    "621 Westwood Boulevard, Los Angeles, CA 90024",
    "1834 Foothill Boulevard, Monrovia, CA 91016",
    "492 Harbor Drive, Wilmington, CA 90744",
    "2677 Rosemead Avenue, El Monte, CA 91731",
    "813 Sunset Canyon Drive, Azusa, CA 91702",
    "1456 Florence Avenue, Hawthorne, CA 90250",
]

LANGUAGES = ["English","English","English","English","Spanish","Spanish","Vietnamese","Tagalog","Korean","Mandarin","Armenian","English","English","English","English"]

GAP_FIELDS = ["auth_ref","appt_window","transportation","language","special_requirements","physician_npi"]


# ── HELPERS ───────────────────────────────────────────────────────────────────

def h2(text):
    return Paragraph(text, ParagraphStyle("h2",fontSize=10,fontName="Helvetica-Bold",spaceAfter=3,textColor=colors.HexColor("#1e3a5f")))

def body(text):
    return Paragraph(text, ParagraphStyle("body",fontSize=9,fontName="Helvetica",spaceAfter=2,leading=13))

def field_table(rows):
    data=[[Paragraph(f"<b>{k}</b>",ParagraphStyle("k",fontSize=9,fontName="Helvetica")),
           Paragraph(str(v),ParagraphStyle("v",fontSize=9,fontName="Helvetica"))] for k,v in rows]
    t=Table(data,colWidths=[2.2*inch,4.3*inch])
    t.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.HexColor("#f8fafc"),colors.white]),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#e2e8f0")),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    return t

def header_block(doc_type):
    data=[[Paragraph("<b>COASTAL DME SERVICES</b>",ParagraphStyle("o",fontSize=14,fontName="Helvetica-Bold",textColor=colors.white)),
           Paragraph(f"<b>{doc_type}</b>",ParagraphStyle("d",fontSize=11,fontName="Helvetica-Bold",textColor=colors.white))]]
    t=Table(data,colWidths=[3.75*inch,2.75*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#1e3a5f")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
        ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
    ]))
    return t

def make_doc(path, margin=0.75):
    return SimpleDocTemplate(path, pagesize=letter,
        leftMargin=margin*inch, rightMargin=margin*inch,
        topMargin=0.6*inch, bottomMargin=0.6*inch)


# ── PDF BUILDERS ──────────────────────────────────────────────────────────────

def build_referral_form(path, p):
    doc = make_doc(path)
    story = [header_block("DME REFERRAL FORM"), Spacer(1,14)]

    story += [h2("PATIENT INFORMATION"), field_table([
        ("Patient Name", p["name"]), ("Date of Birth", p["dob"]),
        ("Claim Number", p["claim"]), ("Injury Date", p["injury_date"]),
    ])]
    story.append(Spacer(1,10))

    story += [h2("INSURANCE & AUTHORIZATION"), field_table([
        ("Insurance Carrier", p["carrier"]),
        ("Adjuster Name", p["adjuster_name"]),
        ("Adjuster Phone", p["adjuster_phone"]),
        ("Adjuster Email", p["adjuster_email"]),
        ("Authorization Ref #", p["auth_ref"]),
        ("Policy Number", p["policy"]),
    ])]
    story.append(Spacer(1,10))

    # Use conflicting ICD on form if applicable
    icd_on_form = p["icd_form"]
    story += [h2("EQUIPMENT REQUESTED"), field_table([
        ("DME Item", p["dme_item"]),
        ("HCPCS Code", p["hcpcs"]),
        ("Quantity", "1"),
        ("Diagnosis Code (ICD-10)", icd_on_form),
        ("Diagnosis Description", p["icd_form_desc"]),
        ("Special Requirements", p["special_req"]),
    ])]
    story.append(Spacer(1,10))

    story += [h2("DELIVERY"), field_table([
        ("Delivery Address", p["address"]),
        ("Preferred Appt Window", p["appt_window"]),
        ("Transportation Required", p["transportation"]),
        ("Language / Interpreter", p["language"]),
    ])]
    story.append(Spacer(1,10))

    story += [h2("REFERRING PROVIDER"), field_table([
        ("Physician Name", p["physician"]),
        ("Practice", p["practice"]),
        ("NPI", p["npi"]),
        ("Phone", p["phys_phone"]),
        ("Fax", p["phys_fax"]),
    ])]
    story.append(Spacer(1,14))
    story += [HRFlowable(width="100%",thickness=0.5,color=colors.HexColor("#cbd5e1")),
              Spacer(1,6), body(f"<i>Referral submitted: {p['ref_date']} · Case Manager: {p['adjuster_name']}</i>")]
    doc.build(story)


def build_clinical_notes(path, p):
    doc = make_doc(path)
    story = [header_block("CLINICAL NOTES"), Spacer(1,14)]

    story += [h2("PATIENT"), field_table([
        ("Name", f"{p['name']}  |  DOB: {p['dob']}"),
        ("Claim", p["claim"]),
        ("Visit Date", p["visit_date"]),
        ("Attending Physician", f"{p['physician']} — {p['practice']}"),
    ])]
    story.append(Spacer(1,10))

    story += [h2("DIAGNOSIS & HISTORY"), field_table([
        ("Primary Diagnosis", p["icd_correct"]),
        ("Diagnosis Description", p["icd_correct_desc"]),
        ("Injury Date", p["injury_date"]),
        ("Treatment", p["treatment_note"]),
    ])]
    story.append(Spacer(1,10))

    story += [h2("FUNCTIONAL ASSESSMENT")]
    story.append(body(p["clinical_note"]))
    story.append(Spacer(1,10))

    story += [h2("DME RECOMMENDATION"), field_table([
        ("Recommended Equipment", p["dme_item"]),
        ("Medical Justification", p["justification"]),
        ("Expected Duration", p["duration"]),
        ("Patient Height/Weight", p["hw"]),
    ])]
    story.append(Spacer(1,14))
    story += [HRFlowable(width="100%",thickness=0.5,color=colors.HexColor("#cbd5e1")),
              Spacer(1,6), body(f"<i>Electronically signed: {p['physician']} · NPI {p['npi']} · {p['visit_date']}</i>")]
    doc.build(story)


def build_prescription(path, p):
    doc = make_doc(path)
    story = [header_block("DME PRESCRIPTION"), Spacer(1,14)]

    story += [h2("PRESCRIBING PHYSICIAN"), field_table([
        ("Name", p["physician"]),
        ("Practice", p["practice"]),
        ("NPI", p["npi"]),
        ("Phone", p["phys_phone"]),
    ])]
    story.append(Spacer(1,10))

    story += [h2("PATIENT"), field_table([
        ("Name", p["name"]), ("DOB", p["dob"]),
        ("Claim", p["claim"]), ("Address", p["address"]),
    ])]
    story.append(Spacer(1,10))

    story += [h2("EQUIPMENT ORDER"), field_table([
        ("Item Description", p["dme_item"]),
        ("HCPCS Code", p["hcpcs"]),
        ("Quantity", "1"),
        ("ICD-10 Diagnosis", p["icd_correct"]),
        ("Diagnosis", p["icd_correct_desc"]),
        ("Medical Necessity", p["justification"]),
        ("Duration of Need", p["duration"]),
    ])]
    story.append(Spacer(1,14))
    story += [HRFlowable(width="100%",thickness=0.5,color=colors.HexColor("#cbd5e1")),
              Spacer(1,6), body(f"<b>Physician Signature:</b> {p['physician']}"),
              Spacer(1,4), body(f"<b>Date:</b> {p['ref_date']}"),
              Spacer(1,4), body("<i>This prescription is valid for 90 days from the date of signing.</i>")]
    doc.build(story)


# ── DATA BUILDER ──────────────────────────────────────────────────────────────

CLINICAL_NOTES = [
    "Patient presents with significant functional limitations following workplace injury. Pain level 5/10 at rest, 8/10 with activity. Range of motion restricted. Physical therapy initiated with gradual improvement noted.",
    "Post-operative assessment shows wound healing within normal parameters. Patient reports difficulty with activities of daily living. Occupational therapy recommended in conjunction with DME provision.",
    "Chronic condition exacerbating following workplace incident. Conservative treatment ongoing. Patient demonstrates need for assistive equipment to maintain safe ambulation in home environment.",
    "Work-related injury resulting in mobility impairment. Patient is compliant with treatment protocol. DME required to facilitate return to baseline functional status.",
    "Patient presents with pain and reduced mobility secondary to occupational injury. Current assistive devices insufficient for safe home ambulation. Equipment upgrade medically necessary.",
]

TREATMENTS = [
    "Conservative management with physical therapy 3x/week. Pain management consult completed.",
    "Post-surgical rehabilitation protocol initiated. Patient progressing appropriately.",
    "Multimodal pain management approach. Medication optimised. PT ongoing.",
    "Injection therapy completed with partial relief. Physical therapy continuing.",
    "Surgical repair completed. Post-operative protocol in progress. PT initiated.",
]

JUSTIFICATIONS = [
    "Medically necessary to support safe ambulation and prevent falls in home environment. Patient unable to safely navigate living space without assistive device.",
    "Required to maintain functional independence and facilitate recovery. Without this equipment, patient at significant risk of re-injury or clinical deterioration.",
    "Essential for activities of daily living. Patient's condition prevents safe self-care without this equipment. Alternatives have been considered and deemed insufficient.",
    "Necessary to support return-to-baseline functional status. Equipment will reduce caregiver burden and support patient's rehabilitation goals.",
]


def build_patient_record(i, name, dob):
    dme = random.choice(DME_ITEMS)
    carrier = random.choice(CARRIERS)
    physician = random.choice(PHYSICIANS)
    address = random.choice(ADDRESSES)
    language = random.choice(LANGUAGES)

    # Decide which gaps to introduce (0-4 gaps per referral)
    num_gaps = random.choices([0,1,2,3,4], weights=[10,25,30,25,10])[0]
    gap_fields = random.sample(GAP_FIELDS, min(num_gaps, len(GAP_FIELDS)))

    dme_item, hcpcs, icd_form_code, icd_form_desc, icd_correct_code, icd_correct_desc, has_conflict = dme
    # Only show conflict if the DME item actually has one
    icd_on_form = icd_form_code if has_conflict else icd_correct_code
    icd_on_form_desc = icd_form_desc if has_conflict else icd_correct_desc

    carrier_name, adj_name, adj_email, adj_phone = carrier
    phys_name, npi, practice, phys_phone, phys_fax = physician

    month = random.randint(1,12)
    day = random.randint(1,28)
    injury_date = f"{month:02d}/{day:02d}/2026"
    visit_offset = random.randint(5,14)
    visit_month = min(12, month + (1 if day+visit_offset>28 else 0))
    visit_day = ((day+visit_offset-1) % 28) + 1
    visit_date = f"{visit_month:02d}/{visit_day:02d}/2026"
    ref_date = f"{visit_month:02d}/{min(28,visit_day+2):02d}/2026"

    height = random.randint(60,76)
    weight = random.randint(130,280)
    hw_str = f"{height//12}'{height%12}\" / {weight} lbs"

    claim = f"WC-2026-{84431+i:06d}"
    policy = f"PM-WC-2026-{44319+i:05d}"

    p = {
        "name": name, "dob": dob, "claim": claim, "policy": policy,
        "injury_date": injury_date, "visit_date": visit_date, "ref_date": ref_date,
        "carrier": carrier_name,
        "adjuster_name": adj_name, "adjuster_email": adj_email, "adjuster_phone": adj_phone,
        "auth_ref": "" if "auth_ref" in gap_fields else f"AUTH-{random.randint(100000,999999)}",
        "dme_item": dme_item, "hcpcs": hcpcs,
        "icd_form": icd_on_form, "icd_form_desc": icd_on_form_desc,
        "icd_correct": icd_correct_code, "icd_correct_desc": icd_correct_desc,
        "special_req": "" if "special_requirements" in gap_fields else "Standard",
        "address": address,
        "appt_window": "" if "appt_window" in gap_fields else f"Weekdays {random.choice(['8-10 AM','9-11 AM','1-3 PM','2-4 PM'])}",
        "transportation": "" if "transportation" in gap_fields else random.choice(["Not required","Arranged","Patient self-transports"]),
        "language": "" if "language" in gap_fields else language,
        "physician": phys_name, "npi": "" if "physician_npi" in gap_fields else npi,
        "practice": practice, "phys_phone": phys_phone, "phys_fax": phys_fax,
        "hw": hw_str,
        "clinical_note": random.choice(CLINICAL_NOTES),
        "treatment_note": random.choice(TREATMENTS),
        "justification": random.choice(JUSTIFICATIONS),
        "duration": random.choice(["3 months","6 months","12 months","Indefinite — chronic condition"]),
        "gap_fields": gap_fields,
        "has_icd_conflict": has_conflict,
    }
    return p


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Generating 75 referral packages (225 PDFs)...")
    print(f"Output: {OUT_BASE}\n")

    for i, (name, dob) in enumerate(PATIENTS):
        p = build_patient_record(i, name, dob)
        folder = OUT_BASE / p["claim"]
        folder.mkdir(parents=True, exist_ok=True)

        build_referral_form(str(folder / "1_referral_form.pdf"), p)
        build_clinical_notes(str(folder / "2_clinical_notes.pdf"), p)
        build_prescription(str(folder / "3_prescription.pdf"), p)

        gaps = p["gap_fields"]
        conflict = " | ICD CONFLICT" if p["has_icd_conflict"] else ""
        print(f"  [{i+1:02d}/75] {p['claim']} · {name:<22} · {p['dme_item']:<35} · Gaps: {len(gaps)}{conflict}")

    print(f"\nDone. 225 PDFs saved to {OUT_BASE}")
