"""
Quick API explorer — run sections manually to poke at the data.
NOT for production, NOT to be pushed.
"""

import time
import json
import requests

BASE_URL = "https://hackathon.prod.pulsefoundry.ai"


def get(path: str, params: dict = {}, max_retries: int = 8) -> dict | list:
    """GET with retry on 429."""
    for attempt in range(max_retries):
        r = requests.get(f"{BASE_URL}{path}", params=params)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 3))
            print(f"  429 on {path} — waiting {wait}s (attempt {attempt + 1})")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Failed after {max_retries} retries: {path}")


def pp(data):
    print(json.dumps(data, indent=2))


# ── Health check ──────────────────────────────────────────────────────────────

def check_health():
    print("=== Health ===")
    pp(get("/health"))


# ── Patients ──────────────────────────────────────────────────────────────────

def get_patients(facility_id: int = 101):
    print(f"\n=== Patients — facility {facility_id} ===")
    patients = get("/pcc/patients", {"facility_id": facility_id})
    print(f"Total: {len(patients)}")
    pp(patients[:3])  # first 3
    return patients


def show_patient_counts():
    for fid in [101, 102, 103]:
        patients = get("/pcc/patients", {"facility_id": fid})
        print(f"Facility {fid}: {len(patients)} patients")


# ── Diagnoses ─────────────────────────────────────────────────────────────────

def get_diagnoses(patient_id: str = "FA-001"):
    print(f"\n=== Diagnoses — {patient_id} ===")
    data = get("/pcc/diagnoses", {"patient_id": patient_id})
    pp(data)
    return data


# ── Coverage ──────────────────────────────────────────────────────────────────

def get_coverage(patient_id: str = "FA-001"):
    print(f"\n=== Coverage — {patient_id} ===")
    data = get("/pcc/coverage", {"patient_id": patient_id})
    pp(data)
    return data


# ── Notes ─────────────────────────────────────────────────────────────────────

def get_notes(internal_id: int = 1):
    print(f"\n=== Notes — internal id={internal_id} ===")
    data = get("/pcc/notes", {"patient_id": internal_id})
    pp(data)
    return data


def browse_notes(facility_id: int = 101, n: int = 10):
    """Show notes for the first n patients in a facility."""
    patients = get("/pcc/patients", {"facility_id": facility_id})
    for p in patients[:n]:
        notes = get("/pcc/notes", {"patient_id": p["id"]})
        if notes:
            print(f"\n--- {p['patient_id']} ({p['first_name']} {p['last_name']}) ---")
            for note in notes:
                print(f"  [{note['note_type']}] {note['effective_date']}")
                print(f"  {note['note_text'][:300]}")
                print()


# ── Assessments ───────────────────────────────────────────────────────────────

def get_assessments(internal_id: int = 1):
    print(f"\n=== Assessments — internal id={internal_id} ===")
    data = get("/pcc/assessments", {"patient_id": internal_id})
    pp(data)
    return data


def browse_assessments(facility_id: int = 101, n: int = 5):
    patients = get("/pcc/patients", {"facility_id": facility_id})
    for p in patients[:n]:
        assessments = get("/pcc/assessments", {"patient_id": p["id"]})
        if assessments:
            print(f"\n--- {p['patient_id']} ---")
            for a in assessments:
                print(f"  type={a['assessment_type']}  status={a['status']}")
                raw = json.loads(a["raw_json"]) if a.get("raw_json") else {}
                pp(raw)


# ── Payer mix overview ────────────────────────────────────────────────────────

def payer_mix(facility_id: int = 101):
    from collections import Counter
    patients = get("/pcc/patients", {"facility_id": facility_id})
    codes = Counter(p["primary_payer_code"] for p in patients)
    print(f"\nFacility {facility_id} payer mix:")
    for code, count in codes.most_common():
        print(f"  {code:5s}  {count:3d}  ({count/len(patients)*100:.0f}%)")


# ── Run whatever you want below ───────────────────────────────────────────────

if __name__ == "__main__":
    check_health()

    # Uncomment what you want to explore:

    patients = get_patients(101)
    show_patient_counts()

    # get_diagnoses("FA-001")
    # get_coverage("FA-001")

    # get_notes(1)
    # browse_notes(facility_id=101, n=5)

    # get_assessments(1)
    # browse_assessments(facility_id=101, n=5)

    # payer_mix(101)
