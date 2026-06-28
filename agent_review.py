"""
Agentic re-review of flag_for_review patients.

For each flagged patient, sends raw clinical notes + assessment text to an LLM
via OpenRouter to extract missing wound fields (wound_type, drainage, stage, etc.)
Then re-runs eligibility routing and reports which patients changed decision.

Usage:
    python3 agent_review.py
"""

import os
import json
import ast
import time
import requests
import pandas as pd
from eligibility import route, has_active_wound_dx, build_eligibility_table

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


def merge_llm_fields(original: dict, llm: dict) -> dict:
    """Fill missing fields in original with LLM results."""
    merged = dict(original)
    for field in ["wound_type", "stage", "location", "length_cm", "width_cm", "depth_cm", "drainage"]:
        if not merged.get(field) and llm.get(field) is not None:
            merged[field] = llm[field]
    return merged


def main():
    print("Loading data...")
    patients    = pd.read_csv("data/patients.csv")
    diagnoses   = pd.read_csv("data/diagnoses.csv")
    notes       = pd.read_csv("data/notes.csv")
    assessments = pd.read_csv("data/assessments.csv")
    eligibility = pd.read_csv("data/eligibility_output.csv")

    # Only process MCB flag_for_review patients
    flagged = eligibility[
        (eligibility["routing"] == "flag_for_review") &
        (eligibility["payer_code"] == "MCB")
    ].copy()
    print(f"Found {len(flagged)} flag_for_review MCB patients to re-review\n")

    # Build patient_id -> internal id map
    id_map = patients.set_index("patient_id")["id"].to_dict()

    results = []

    for i, (_, row) in enumerate(flagged.iterrows()):
        pid = row["patient_id"]
        iid = id_map.get(pid)
        print(f"[{i+1}/{len(flagged)}] {pid} — missing: {row['reason'][:60]}")

        # Build clinical text for LLM
        clinical_text = build_clinical_text(pid, iid, notes, assessments)

        # Call LLM
        llm_result = call_llm(clinical_text)
        confidence = llm_result.pop("confidence", "unknown")
        print(f"    LLM extracted: {llm_result}  (confidence: {confidence})")

        # Merge LLM fields into existing wound data
        original_fields = {
            "wound_type": row.get("wound_type"),
            "stage":      row.get("stage"),
            "location":   row.get("location"),
            "length_cm":  row.get("length_cm"),
            "width_cm":   row.get("width_cm"),
            "depth_cm":   row.get("depth_cm"),
            "drainage":   row.get("drainage"),
        }
        enriched = merge_llm_fields(original_fields, llm_result)

        # Re-run routing with enriched fields
        pat_row = patients[patients["patient_id"] == pid].iloc[0].to_dict()
        has_dx = has_active_wound_dx(pid, diagnoses)
        new_decision, new_reason = route(pat_row, enriched, has_dx)

        changed = new_decision != "flag_for_review"
        print(f"    {'CHANGED -> ' + new_decision.upper() if changed else 'still flag_for_review'}\n")

        results.append({
            "patient_id":       pid,
            "original_routing": "flag_for_review",
            "original_reason":  row["reason"],
            "llm_wound_type":   llm_result.get("wound_type"),
            "llm_drainage":     llm_result.get("drainage"),
            "llm_stage":        llm_result.get("stage"),
            "llm_location":     llm_result.get("location"),
            "llm_length_cm":    llm_result.get("length_cm"),
            "llm_width_cm":     llm_result.get("width_cm"),
            "llm_depth_cm":     llm_result.get("depth_cm"),
            "llm_confidence":   confidence,
            "new_routing":      new_decision,
            "new_reason":       new_reason,
            "changed":          changed,
        })

    results_df = pd.DataFrame(results)
    results_df.to_csv("data/agent_review_results.csv", index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n=== Agent Review Summary ===")
    print(f"Total flagged reviewed: {len(results_df)}")
    print(f"Changed decision:       {results_df['changed'].sum()}")
    print(f"  -> auto_accept:       {(results_df['new_routing'] == 'auto_accept').sum()}")
    print(f"  -> reject:            {(results_df['new_routing'] == 'reject').sum()}")
    print(f"Still flag_for_review:  {(results_df['new_routing'] == 'flag_for_review').sum()}")

    print("\n=== Patients upgraded to auto_accept ===")
    upgraded = results_df[results_df["new_routing"] == "auto_accept"]
    if len(upgraded):
        print(upgraded[["patient_id", "llm_wound_type", "llm_drainage", "llm_confidence", "new_reason"]].to_string(index=False))
    else:
        print("None")

    print("\n=== Saved to data/agent_review_results.csv ===")

    # Build updated full eligibility output
    updated_eligibility = pd.read_csv("data/eligibility_output.csv")
    updated_eligibility["promoted_by_agent"] = False  # default

    for _, res in results_df.iterrows():
        mask = updated_eligibility["patient_id"] == res["patient_id"]
        updated_eligibility.loc[mask, "routing"] = res["new_routing"]
        updated_eligibility.loc[mask, "reason"]  = res["new_reason"]
        # Mark records that were promoted from flag_for_review -> auto_accept
        if res["new_routing"] == "auto_accept":
            updated_eligibility.loc[mask, "promoted_by_agent"] = True
        for f in ["wound_type", "stage", "location", "length_cm", "width_cm", "depth_cm", "drainage"]:
            llm_val = res.get(f"llm_{f}")
            if pd.notna(llm_val) and llm_val is not None:
                current = updated_eligibility.loc[mask, f].values[0]
                if pd.isna(current) or current is None:
                    updated_eligibility.loc[mask, f] = llm_val

    updated_eligibility.to_csv("data/eligibility_output_final.csv", index=False)
    json_str = updated_eligibility.to_json(orient="records")
    with open("dashboard/public/eligibility_data.json", "w") as f:
        f.write(json_str)
    print("Updated dashboard/public/eligibility_data.json with final routing decisions.")


if __name__ == "__main__":
    main()
