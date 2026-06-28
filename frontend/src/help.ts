/** Plain-language tooltips for biller-facing UI */

export const HELP = {
  new_admission:
    "Recently admitted to the facility (flagged in PCC data). New admissions are often prioritized because wound documentation may still be incoming.",

  part_b_eligible:
    "Patient has active Medicare Part B coverage — the insurance type required for outpatient wound care billing.",

  not_part_b:
    "Patient does not have active Medicare Part B (may have Medicaid, Medicare Part A, or HMO). Cannot submit Part B wound care claims.",

  ready_to_bill:
    "All required wound fields were extracted with high confidence. Safe for a biller to route to claims.",

  needs_review:
    "Something is missing or ambiguous in the chart (e.g. no depth measurement). A clinician or biller should verify before billing.",

  do_not_route:
    "Wrong insurance or wound data could not be reliably extracted. Do not send to billing without more documentation.",

  confidence:
    "How confident the pipeline is in the extracted wound fields (0–100%). Low confidence means a human should double-check the note.",

  llm_suggestions:
    "Needs Review cases where GPT added an advisory suggestion (billable, needs documentation, or unclear). Does not change routing.",

  llm_verify:
    "Optional final step: GPT reads ambiguous cases in Needs Review (batched, ~17 API calls) and adds a suggestion for the biller. Check the box, then Run pipeline.",

  missing_medicare_part_b:
    "No active Medicare Part B on file — not eligible for this billing workflow.",

  missing_wound_documentation:
    "No usable wound note or assessment found — nothing to extract.",

  missing_wound_type:
    "Could not determine wound type (pressure ulcer, diabetic ulcer, etc.) from the note.",

  missing_length_cm:
    "Length measurement (cm) not found in clinical notes.",

  missing_width_cm:
    "Width measurement (cm) not found in clinical notes.",

  missing_depth_cm:
    "Depth measurement (cm) not found. Common with Envive notes that only list length × width.",

  missing_drainage_amount:
    "Drainage level (none / light / moderate / heavy) not documented or not parsed.",

  part_b_filter:
    "Filter by whether the patient can be considered for Medicare Part B wound care submission.",

  doc_status_filter:
    "Filter by documentation routing: ready to bill, needs human review, or do not route.",

  missing_filter:
    "Show only patients missing specific documentation fields or insurance requirements.",

  new_admission_filter:
    "Show only patients flagged as new admissions in the facility.",

  shown_metric: "Number of patients matching your current filters.",

  part_b_metric: "Of filtered patients, how many have active Medicare Part B.",

  ready_metric: "Filtered patients with complete documentation — ready for billing.",

  review_metric: "Filtered patients with incomplete or ambiguous documentation.",

  reject_metric: "Filtered patients not eligible or lacking reliable wound data.",

  pipeline_run:
    "Re-processes cached chart data locally: extract wounds, route patients, optionally run LLM suggestions. Fast (~0.2s without LLM). LLM does NOT require a fresh API fetch.",

  pipeline_fresh:
    "Clears cache and re-downloads all 300 patients from the PCC API (~3 min). Use when you need new chart data — not required for LLM.",

  openai_badge:
    "OpenAI API key detected. Check “LLM suggest for review” before running the pipeline to add AI notes on ambiguous cases.",
} as const;

export function missingFieldHelp(field: string): string {
  const key = `missing_${field}` as keyof typeof HELP;
  return HELP[key] ?? `Required field "${field}" is missing from extracted documentation.`;
}
