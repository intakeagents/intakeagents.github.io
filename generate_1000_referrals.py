"""
Generate 1,000 synthetic referral PDF packages for benchmark.
Each package: referral_form.pdf + clinical_notes.pdf + prescription.pdf
Run: python generate_1000_referrals.py
"""
import random
import datetime
from pathlib import Path
from fpdf import FPDF

random.seed(42)

OUTPUT_DIR = Path(__file__).parent / "referrals" / "benchmark_1000"

FIRST = ["James","Maria","Robert","Linda","Michael","Barbara","William","Patricia",
         "David","Jennifer","Richard","Sandra","Joseph","Dorothy","Thomas","Ashley",
         "Charles","Emily","Christopher","Donna","Daniel","Carol","Matthew","Amanda",
         "Anthony","Jessica","Mark","Sarah","Paul","Betty","Steven","Helen","Kevin",
         "Nancy","Edward","Margaret","Brian","Lisa","Ronald","Ruth","Timothy","Sharon",
         "Jason","Michelle","Jeffrey","Laura","Ryan","Kimberly","Jacob","Deborah"]

LAST  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
         "Rodriguez","Wilson","Martinez","Anderson","Taylor","Thomas","Hernandez",
         "Moore","Martin","Jackson","Thompson","White","Lopez","Lee","Gonzalez",
         "Harris","Clark","Lewis","Robinson","Walker","Hall","Young","Allen","King",
         "Wright","Scott","Torres","Nguyen","Hill","Adams","Baker","Nelson","Carter",
         "Mitchell","Perez","Roberts","Turner","Phillips","Campbell","Parker","Evans","Edwards"]

CARRIERS = [
    "Coastal Insurance Group", "Pacific Workers Comp", "Allied Benefit Systems",
    "Zenith National Insurance", "ICW Group", "Employers Holdings Inc",
    "Liberty Mutual WC", "Travelers Indemnity", "Hartford Financial Services",
    "State Compensation Insurance Fund",
]

ADJUSTERS = [
    ("Linda Torres","l.torres@coastalins.com"),("Maria Santos","m.santos@pacificwc.com"),
    ("James Wright","j.wright@alliedbenefits.com"),("Susan Chen","s.chen@zenithnat.com"),
    ("Robert Kim","r.kim@icwgroup.com"),("Patricia Diaz","p.diaz@employershold.com"),
    ("Michael Nguyen","m.nguyen@libertywc.com"),("Karen Patel","k.patel@travelers.com"),
    ("David Okafor","d.okafor@hartfordwc.com"),("Angela Reeves","a.reeves@scif.com"),
]

PHYSICIANS = [
    ("Kevin Marsh MD","1234567890","Pacific Orthopedic Associates"),
    ("Aisha Patel MD","2345678901","Western Spine Center"),
    ("Carlos Ruiz MD","3456789012","Bay Area Neurology"),
    ("Sandra Bloom MD","4567890123","Harbor Physical Medicine"),
    ("James Okonkwo MD","5678901234","Valley Orthopedics"),
    ("Mei Lin MD","6789012345","Coastal Rehab Group"),
    ("David Stern MD","7890123456","Summit Sports Medicine"),
    ("Priya Nair MD","8901234567","Central Occupational Health"),
]

DME_ITEMS = [
    ("Rollator Walker 4-Wheel","E0143","Ambulatory Aid","Standard 250lb"),
    ("Power Wheelchair","K0823","Power Mobility","18\" seat width"),
    ("CPAP Machine","E0601","Respiratory","Auto-titrating"),
    ("Knee Orthosis","L1851","Orthotic","Custom-fit hinged"),
    ("Hospital Bed Electric","E0265","Home Care","Full electric w/ rails"),
    ("Cane Quad","E0105","Ambulatory Aid","Large base"),
    ("Ankle Foot Orthosis","L1900","Orthotic","Solid ankle"),
    ("Nebulizer","E0570","Respiratory","Compressor w/ kit"),
    ("Manual Wheelchair","K0001","Mobility","Standard hemi"),
    ("TENS Unit","E0730","Pain Mgmt","4-lead portable"),
]

# ICD-10 pairs: (code, description, sometimes_conflicting_code)
DIAGNOSES = [
    ("S83.209A","Unspecified tear of unspecified meniscus, current injury, right knee, initial encounter","M23.611"),
    ("M54.5","Low back pain","M51.16"),
    ("G89.29","Other chronic pain","G89.4"),
    ("S72.001A","Fracture of unspecified part of neck of right femur, initial encounter","M16.11"),
    ("M17.11","Primary osteoarthritis, right knee","M17.31"),
    ("S52.501A","Unspecified fracture of the lower end of the right radius, initial encounter","M19.031"),
    ("M48.06","Spinal stenosis, lumbar region","M47.816"),
    ("G35","Multiple sclerosis","G37.3"),
    ("S13.4XXA","Sprain of ligaments of cervical spine, initial encounter","M54.2"),
    ("M19.011","Primary osteoarthritis, right shoulder","M75.101"),
]

STATES = ["CA","TX","FL","NY","IL","PA","OH","GA","NC","MI","NJ","WA","AZ","MA","TN"]
CITIES = ["Los Angeles","Houston","Miami","Chicago","Phoenix","Philadelphia","San Antonio",
          "San Diego","Dallas","Jacksonville","Austin","Fort Worth","Columbus","Charlotte",
          "Seattle","Denver","Portland","Las Vegas","Nashville","Baltimore"]

def random_dob():
    year = random.randint(1955, 1995)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{month:02d}/{day:02d}/{year}"

def random_address():
    num = random.randint(100, 9999)
    streets = ["Oak St","Elm Ave","Maple Dr","Pine Rd","Cedar Ln","Birch Blvd",
               "Walnut St","Cherry Ave","Willow Dr","Ash Rd","Hickory Ln","Spruce Way"]
    city = random.choice(CITIES)
    state = random.choice(STATES)
    zip_ = f"{random.randint(10000, 99999)}"
    return f"{num} {random.choice(streets)}, {city} {state} {zip_}"

def gap_profile():
    """Returns a dict of which fields to intentionally omit."""
    return {
        "auth_ref":     random.random() < 0.38,
        "appt_window":  random.random() < 0.28,
        "transportation": random.random() < 0.22,
        "language":     random.random() < 0.45,
    }

def _safe(text: str) -> str:
    return (text.replace("—", "-").replace("–", "-")
                .replace("’", "'").replace("‘", "'")
                .replace("“", '"').replace("”", '"')
                .encode("latin-1", errors="replace").decode("latin-1"))

def make_pdf_text(lines: list[str]) -> "FPDF":
    from fpdf.enums import XPos, YPos
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(18, 18, 18)
    pdf.set_font("Helvetica", size=9)
    for line in lines:
        line = _safe(line)
        if line.startswith("##"):
            pdf.set_font("Helvetica", style="B", size=9)
            pdf.cell(0, 5, line.lstrip("#").strip(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", size=9)
        elif line == "---":
            pdf.ln(2)
            pdf.line(18, pdf.get_y(), 192, pdf.get_y())
            pdf.ln(2)
        elif line == "":
            pdf.ln(3)
        else:
            pdf.set_x(18)
            pdf.multi_cell(174, 4.5, line)
    return pdf


def generate_referral(idx: int):
    first = random.choice(FIRST)
    last  = random.choice(LAST)
    name  = f"{first} {last}"
    dob   = random_dob()
    claim = f"WC-2026-{100000 + idx:06d}"
    addr  = random_address()

    carrier = random.choice(CARRIERS)
    adj_name, adj_email = random.choice(ADJUSTERS)
    adj_phone = f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}"

    phys_name, phys_npi, phys_practice = random.choice(PHYSICIANS)
    dme_item, hcpcs, dme_cat, dme_spec = random.choice(DME_ITEMS)

    icd_code, icd_desc, conflict_code = random.choice(DIAGNOSES)
    has_conflict = random.random() < 0.08  # 8% have ICD conflict

    gaps = gap_profile()
    auth_ref    = "" if gaps["auth_ref"]    else f"AUTH-{random.randint(100000,999999)}"
    appt_window = "" if gaps["appt_window"] else f"05/{random.randint(10,31)}/2026 {random.randint(8,14):02d}:00–{random.randint(15,17):02d}:00"
    transport   = "" if gaps["transportation"] else random.choice(["Confirmed","Not required","Arranged via Uber Health"])
    language    = "" if gaps["language"]    else random.choice(["English","Spanish","Spanish - interpreter required","Mandarin - interpreter required","English"])

    today = datetime.date.today().strftime("%m/%d/%Y")
    injury_date = f"{random.randint(1,4):02d}/{random.randint(1,28):02d}/2026"
    surgery_date = f"0{random.randint(2,4)}/{random.randint(1,28):02d}/2026"
    weight = random.randint(140, 310)

    folder = OUTPUT_DIR / claim
    folder.mkdir(parents=True, exist_ok=True)

    # ── REFERRAL FORM PDF ──────────────────────────────────────────────────────
    form_icd = conflict_code if has_conflict else icd_code
    form_lines = [
        "## COASTAL WORKERS COMP — DME REFERRAL FORM",
        f"Date: {today}   Fax: (800) 555-0100",
        "---",
        "## PATIENT INFORMATION",
        f"Name: {name}",
        f"DOB: {dob}",
        f"Address: {addr}",
        f"Language: {language}" if language else "Language: ",
        "",
        "## INSURANCE / CLAIM",
        f"Carrier: {carrier}",
        f"Claim #: {claim}",
        f"Date of Injury: {injury_date}",
        f"Auth Reference #: {auth_ref}" if auth_ref else "Auth Reference #: ",
        "",
        "## CASE MANAGER / ADJUSTER",
        f"Adjuster: {adj_name}",
        f"Email: {adj_email}",
        f"Phone: {adj_phone}",
        "",
        "## EQUIPMENT ORDERED",
        f"Item: {dme_item}",
        f"HCPCS: {hcpcs}",
        f"Category: {dme_cat}",
        f"Specifications: {dme_spec}",
        f"Diagnosis ICD-10: {form_icd}",
        f"Delivery Address: {addr}",
        "",
        "## APPOINTMENT",
        f"Preferred Window: {appt_window}" if appt_window else "Preferred Window: ",
        f"Transportation: {transport}" if transport else "Transportation: ",
        "",
        "## REFERRING PROVIDER",
        f"Physician: {phys_name}",
        f"NPI: {phys_npi}",
        f"Practice: {phys_practice}",
    ]

    # ── CLINICAL NOTES PDF ─────────────────────────────────────────────────────
    clinical_lines = [
        f"## {phys_practice.upper()} — CLINICAL NOTES",
        f"Patient: {name}   DOB: {dob}   Date: {today}",
        "---",
        "## DIAGNOSIS",
        f"Primary: {icd_code} — {icd_desc}",
        "",
        "## CLINICAL SUMMARY",
        f"Patient presents following work-related injury on {injury_date}.",
        f"Surgical intervention performed {surgery_date}. Post-operative rehabilitation",
        f"ongoing. Patient weight: {weight} lbs. Functional limitations consistent with",
        f"prescribed DME requirement.",
        "",
        "## TREATMENT PLAN",
        f"DME ordered: {dme_item} ({hcpcs}). Patient requires {dme_cat.lower()} support",
        f"for mobility and recovery. Specifications: {dme_spec}.",
        "",
        "## PROVIDER",
        f"Signed: {phys_name}   NPI: {phys_npi}",
        f"Date: {today}",
    ]

    # ── PRESCRIPTION PDF ───────────────────────────────────────────────────────
    rx_lines = [
        f"## {phys_practice.upper()} — DME PRESCRIPTION",
        f"Physician: {phys_name}   NPI: {phys_npi}   Date: {today}",
        "---",
        "## PATIENT",
        f"Name: {name}",
        f"DOB: {dob}",
        f"Diagnosis ICD-10: {icd_code}",
        "",
        "## EQUIPMENT PRESCRIBED",
        f"Item: {dme_item}",
        f"HCPCS: {hcpcs}",
        f"Specifications: {dme_spec}",
        f"Quantity: 1   Duration: 90 days",
        f"No Substitution: YES",
        "",
        "## NOTES",
        f"Patient weight {weight} lbs. Ensure spec compliance.",
        f"Delivery to: {addr}",
        "",
        f"Signed: {phys_name}   Date: {today}",
    ]

    for filename, lines in [
        (f"{claim}_ReferralForm.pdf", form_lines),
        (f"{claim}_ClinicalNotes.pdf", clinical_lines),
        (f"{claim}_Prescription.pdf", rx_lines),
    ]:
        pdf = make_pdf_text(lines)
        pdf.output(str(folder / filename))

    return claim, gaps, has_conflict


if __name__ == "__main__":
    import sys

    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    print(f"Generating {count} referral packages -> {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with_gaps = 0
    with_conflict = 0
    for i in range(1, count + 1):
        claim, gaps, conflict = generate_referral(i)
        if any(gaps.values()):
            with_gaps += 1
        if conflict:
            with_conflict += 1
        if i % 100 == 0:
            print(f"  {i}/{count} generated...")

    print(f"\nDone.")
    print(f"  {count} referral packages in {OUTPUT_DIR}")
    print(f"  ~{with_gaps} with at least one gap ({100*with_gaps//count}%)")
    print(f"  ~{with_conflict} with ICD conflict ({100*with_conflict//count}%)")
    print(f"\nNext: python benchmark_1000.py")
