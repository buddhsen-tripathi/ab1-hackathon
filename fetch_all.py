"""
Fetches all data from all API endpoints and saves to CSV files.
Output files:
  data/patients.csv
  data/diagnoses.csv
  data/coverage.csv
  data/notes.csv
  data/assessments.csv
"""

import time
import json
import csv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE_URL = "https://hackathon.prod.pulsefoundry.ai"
FACILITIES = [101, 102, 103]
OUT_DIR = "data"


def get(path: str, params: dict = {}, max_retries: int = 10) -> list | dict:
    for attempt in range(max_retries):
        r = requests.get(f"{BASE_URL}{path}", params=params)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 3))
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Failed after {max_retries} retries: {path} {params}")


def write_csv(path: str, rows: list[dict]):
    if not rows:
        print(f"  No data for {path}")
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved {len(rows)} rows → {path}")


def fetch_for_patient(p: dict) -> dict:
    """Fetch diagnoses, coverage, notes, assessments for one patient."""
    pid = p["patient_id"]   # string e.g. FA-001
    iid = p["id"]           # integer

    diagnoses   = get("/pcc/diagnoses",   {"patient_id": pid})
    coverage    = get("/pcc/coverage",    {"patient_id": pid})
    notes       = get("/pcc/notes",       {"patient_id": iid})
    assessments = get("/pcc/assessments", {"patient_id": iid})

    return {
        "diagnoses":   diagnoses,
        "coverage":    coverage,
        "notes":       notes,
        "assessments": assessments,
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── 1. Patients ───────────────────────────────────────────────────────────
    print("Fetching patients...")
    all_patients = []
    for fid in FACILITIES:
        patients = get("/pcc/patients", {"facility_id": fid})
        all_patients.extend(patients)
        print(f"  Facility {fid}: {len(patients)} patients")

    write_csv(f"{OUT_DIR}/patients.csv", all_patients)
    print(f"Total patients: {len(all_patients)}")

    # ── 2. Per-patient data (parallel) ────────────────────────────────────────
    print("\nFetching diagnoses, coverage, notes, assessments (parallel)...")

    all_diagnoses   = []
    all_coverage    = []
    all_notes       = []
    all_assessments = []

    done = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_for_patient, p): p for p in all_patients}
        for future in as_completed(futures):
            p = futures[future]
            try:
                result = future.result()
                all_diagnoses.extend(result["diagnoses"])
                all_coverage.extend(result["coverage"])

                # Flatten notes: add patient_id string for easy joining
                for note in result["notes"]:
                    note["patient_id_str"] = p["patient_id"]
                    # raw note_text may have newlines — keep as-is in CSV
                all_notes.extend(result["notes"])

                # Flatten assessments: parse raw_json into columns
                for a in result["assessments"]:
                    a["patient_id_str"] = p["patient_id"]
                    raw = {}
                    if a.get("raw_json"):
                        try:
                            raw = json.loads(a["raw_json"])
                        except json.JSONDecodeError:
                            pass
                    a.update({f"raw_{k}": v for k, v in raw.items()})
                    del a["raw_json"]
                all_assessments.extend(result["assessments"])

            except Exception as e:
                print(f"  ERROR for {p['patient_id']}: {e}")

            done += 1
            if done % 30 == 0:
                print(f"  {done}/{len(all_patients)} patients done...")

    # ── 3. Write CSVs ─────────────────────────────────────────────────────────
    print("\nWriting CSVs...")
    write_csv(f"{OUT_DIR}/diagnoses.csv",   all_diagnoses)
    write_csv(f"{OUT_DIR}/coverage.csv",    all_coverage)
    write_csv(f"{OUT_DIR}/notes.csv",       all_notes)
    write_csv(f"{OUT_DIR}/assessments.csv", all_assessments)

    print("\nDone.")


if __name__ == "__main__":
    start = time.time()
    main()
    print(f"Elapsed: {time.time() - start:.1f}s")
