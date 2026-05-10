from intake_agent import load_pdfs, extract_fields
import traceback

for claim, folder in [
    ("WC-2026-084432", "referrals/WC-2026-084432"),
    ("WC-2026-084438", "referrals/WC-2026-084438"),
]:
    print(f"\n--- {claim} ---")
    try:
        docs = load_pdfs(folder)
        fields = extract_fields(docs, claim)
        print(f"OK: {fields.get('patient_name')} | {fields.get('dme_item')}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
