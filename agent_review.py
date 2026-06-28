"""
LLM-assisted advisory review of flag_for_review patients.

For each flagged MCB patient, sends clinical notes and assessment text to an LLM
to extract missing wound fields. The LLM output is recorded as an advisory annotation
only — it does NOT change the routing decision. All routing changes require a human
clinician to update the source documentation, which then re-runs through eligibility.py.

Usage:
    python3 agent_review.py
"""

import os
import json
import ast
import time
import requests
import pandas as pd
from eligibility import has_active_wound_dx, build_eligibility_table

# ── Config ────────────────────────────────────────────────────────────────────

def _load_env(path=".env"):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass

_load_env()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL = "google/gemini-3.5-flash"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

EXTRACTION_PROMPT = """You are a clinical data extraction assistant. A patient's wound care documentation is provided below.

Extract the following fields as a JSON object. Use null if genuinely absent — do not guess.

Fields to extract:
- wound_type: one of ["Pressure Ulcer", "Diabetic Foot Ulcer", "Venous Ulcer", "Arterial Ulcer", "Abscess", "Burn", "Surgical Site Infection"] or null
- stage: e.g. "Stage 2", "Stage 3", "Stage 4", "Unstageable" — only for pressure ulcers, else null
- location: anatomical location string, e.g. "Sacrum", "Left heel", "Right foot" or null
- length_cm: numeric or null
- width_cm: numeric or null
- depth_cm: numeric or null
- drainage: one of ["none", "light", "moderate", "heavy"] or null
- confidence: one of ["high", "medium", "low"] — how confident you are in the extraction

Respond ONLY with a valid JSON object. No explanation.

--- CLINICAL DOCUMENTATION ---
{clinical_text}
"""


def call_llm(clinical_text: str) -> dict:
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": EXTRACTION_PROMPT.format(clinical_text=clinical_text),
            }
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/buddhsen-tripathi/ab1-hackathon",
        "X-Title": "Wound Care Billing Pipeline",
    }
    for attempt in range(3):
        try:
            r = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            if attempt == 2:
                print(f"    LLM error: {e}")
                return {}
            time.sleep(2)
    return {}


def build_clinical_text(patient_id: str, patient_int_id: int, notes_df: pd.DataFrame, assessments_df: pd.DataFrame) -> str:
    """Concatenate all notes and assessment text for a patient."""
    parts = []

    patient_notes = notes_df[notes_df["patient_id_str"] == patient_id]
    for _, n in patient_notes.iterrows():
        if pd.notna(n.get("note_text")):
            parts.append(f"=== Progress Note ({n.get('note_type','')}, {n.get('effective_date','')}) ===\n{n['note_text']}")

    patient_assessments = assessments_df[assessments_df["patient_id_str"] == patient_id]
    for _, a in patient_assessments.iterrows():
        raw = a.get("raw_sections", "")
        if pd.notna(raw):
            try:
                sections = ast.literal_eval(raw)
                lines = []
                for sec in sections:
                    for q in sec.get("questions", []):
                        ans = q.get("answer")
                        if ans and str(ans).strip() not in ("", "N/A", "None"):
                            lines.append(f"{q['question']}: {ans}")
                parts.append(f"=== Assessment ({a.get('assessment_type','')}) ===\n" + "\n".join(lines))
            except Exception:
                parts.append(f"=== Assessment raw ===\n{raw[:500]}")

    return "\n\n".join(parts) if parts else "No clinical documentation found."


def main():
    print("Loading data...")
    patients    = pd.read_csv("data/patients.csv")
    notes       = pd.read_csv("data/notes.csv")
    assessments = pd.read_csv("data/assessments.csv")
    eligibility = pd.read_csv("data/eligibility_output.csv")

    # Only annotate MCB flag_for_review patients
    flagged = eligibility[
        (eligibility["routing"] == "flag_for_review") &
        (eligibility["payer_code"] == "MCB")
    ].copy()
    print(f"Found {len(flagged)} flag_for_review MCB patients for LLM advisory review\n")

    id_map = patients.set_index("patient_id")["id"].to_dict()
    results = []

    for i, (_, row) in enumerate(flagged.iterrows()):
        pid = row["patient_id"]
        iid = id_map.get(pid)
        print(f"[{i+1}/{len(flagged)}] {pid} — flagged reason: {row['reason'][:60]}")

        clinical_text = build_clinical_text(pid, iid, notes, assessments)
        llm_result = call_llm(clinical_text)
        llm_confidence = llm_result.pop("confidence", "unknown")
        print(f"    LLM advisory: {llm_result}  (llm_confidence: {llm_confidence})\n")

        # LLM output is advisory only — routing decision stays flag_for_review.
        # A clinician must review, update source documentation, and re-run
        # eligibility.py to produce a new routing decision.
        results.append({
            "patient_id":         pid,
            "routing":            row["routing"],   # unchanged
            "original_reason":    row["reason"],    # unchanged
            "llm_wound_type":     llm_result.get("wound_type"),
            "llm_drainage":       llm_result.get("drainage"),
            "llm_stage":          llm_result.get("stage"),
            "llm_location":       llm_result.get("location"),
            "llm_length_cm":      llm_result.get("length_cm"),
            "llm_width_cm":       llm_result.get("width_cm"),
            "llm_depth_cm":       llm_result.get("depth_cm"),
            "llm_confidence":     llm_confidence,
            "action_required":    "Clinician must verify LLM suggestions and update source chart before re-routing.",
        })

    results_df = pd.DataFrame(results)
    results_df.to_csv("data/agent_review_results.csv", index=False)

    print("\n=== LLM Advisory Review Summary ===")
    print(f"Flagged patients reviewed: {len(results_df)}")
    print("Routing decisions: unchanged (LLM output is advisory only)")

    # Annotate eligibility output with LLM suggestions — routing column is NOT modified.
    updated = pd.read_csv("data/eligibility_output.csv")
    for col in ["llm_wound_type", "llm_drainage", "llm_stage", "llm_confidence", "action_required"]:
        updated[col] = None

    for _, res in results_df.iterrows():
        mask = updated["patient_id"] == res["patient_id"]
        for col in ["llm_wound_type", "llm_drainage", "llm_stage", "llm_confidence", "action_required"]:
            updated.loc[mask, col] = res.get(col)

    updated.to_csv("data/eligibility_output_final.csv", index=False)
    json_str = updated.to_json(orient="records")
    with open("dashboard/public/eligibility_data.json", "w") as f:
        f.write(json_str)
    print("Saved advisory annotations → data/eligibility_output_final.csv")
    print("Updated dashboard/public/eligibility_data.json")


if __name__ == "__main__":
    main()
