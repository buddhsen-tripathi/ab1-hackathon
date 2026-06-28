export type RoutingDecision = "auto_accept" | "flag_for_review" | "reject";

export type MissingField =
  | "wound_type"
  | "length_cm"
  | "width_cm"
  | "depth_cm"
  | "drainage_amount"
  | "medicare_part_b"
  | "wound_documentation";

export interface Patient {
  patient_id: string;
  internal_id: number;
  facility_id: number;
  facility_name?: string;
  first_name: string | null;
  last_name: string | null;
  is_new_admission: boolean;
  has_active_mcb: boolean;
  submission_eligible: boolean;
  wound_type: string | null;
  stage: string | null;
  location: string | null;
  length_cm: number | null;
  width_cm: number | null;
  depth_cm: number | null;
  drainage_amount: string | null;
  extraction_source: string;
  extraction_confidence: number;
  routing_decision: RoutingDecision;
  reason: string;
  missing_fields: MissingField[];
  llm_check?: string | null;
  llm_check_note?: string | null;
}

export interface PatientDetail extends Patient {
  notes: Record<string, unknown>[];
  assessments: Record<string, unknown>[];
  coverage: Record<string, unknown>[];
  diagnoses: Record<string, unknown>[];
  note_html: string | null;
  note_text: string | null;
}

export interface Filters {
  facilityId: number | null;
  routing: RoutingDecision[];
  submissionEligible: "all" | "eligible" | "not_eligible";
  missingFields: MissingField[];
  newAdmissionOnly: boolean;
  search: string;
}

export interface Stats {
  total: number;
  filtered: number;
  submission_eligible: number;
  routing: Record<RoutingDecision, number>;
  missing_field_counts: Record<string, number>;
  llm_suggestions: number;
}

export interface Meta {
  facilities: { id: number; name: string }[];
  field_labels: Record<string, string>;
  wound_fields: string[];
  routing_labels: Record<RoutingDecision, string>;
  pipeline: Record<string, unknown> | null;
  last_sync: string | null;
}
