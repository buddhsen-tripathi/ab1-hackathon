// Shapes mirror the FastAPI backend: pcc_client.STATS.snapshot() and
// characterize.report(), plus the /patients raw rows.

export interface RequestStats {
  total_requests: number;
  ok: number;
  rate_limited_429: number;
  server_5xx: number;
  net_errors: number;
  observed_429_rate: number;
  calls_per_success: number;
  retry_after_distribution: Record<string, number>;
}

export interface MeasurementDims {
  three_LxWxD: number;
  two_LxW_no_depth: number;
  none_found: number;
}

export interface DataReport {
  table_counts: Record<string, number>;
  patients: {
    total: number;
    by_facility: Record<string, number>;
    primary_payer_mix: Record<string, number>;
    billable_MCB: number;
    billable_MCB_pct: number;
  };
  coverage: {
    payer_code_distribution: Record<string, number>;
    payer_type_distribution: Record<string, number>;
    patients_with_active_MCB: number;
    note: string;
  };
  diagnoses: {
    clinical_status: Record<string, number>;
  };
  notes: {
    total: number;
    note_type_distribution: Record<string, number>;
    format_family: Record<string, number>;
    format_by_note_type: Record<string, Record<string, number>>;
    measurement_dims: MeasurementDims;
    drainage_keyword_found: number;
    doubled_word_trap: number;
    samples_by_format: Record<string, string>;
  };
  assessments: {
    total: number;
    assessment_type_distribution: Record<string, number>;
    raw_json_shape: Record<string, number>;
    section_names: Record<string, number>;
    measurement_dims: MeasurementDims;
    laterality_conflict_trap: number;
    samples_by_shape: Record<string, string>;
  };
}

export interface StatsResponse {
  request_stats: RequestStats;
  data: DataReport;
}

export interface ExtractionSummary {
  total_wound_rows: number;
  primary_wounds: number;
  billing_ready: number;
  billing_ready_pct: number;
  by_source_format: Record<string, number>;
  field_coverage_pct: Record<string, number>;
  flag_distribution: Record<string, number>;
}

export interface EligibilitySummary {
  total_patients: number;
  active_mcb: number;
  decisions: Record<string, number>;
  by_facility: Record<string, { auto: number; flag: number; reject: number }>;
  review_flags: Record<string, number>;
}

export interface EligibilityResult {
  internal_id: number;
  patient_id: string;
  facility_id: number;
  first_name: string | null;
  last_name: string | null;
  is_new_admission: boolean;
  has_active_mcb: boolean;
  submission_eligible: boolean;
  wound_type: string | null;
  stage: string | null;
  location: string | null;
  laterality: string | null;
  length_cm: number | null;
  width_cm: number | null;
  depth_cm: number | null;
  area_cm2: number | null;
  drainage_amount: string | null;
  extraction_source: string;
  extraction_confidence: number;
  routing_decision: string;
  reason: string;
  missing_fields: string[];
  flags: string[];
  secondary_wound_count: number;
}

export interface LlmStats {
  calls: number;
  errors: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  avg_latency_s: number;
}

export interface LlmObservability {
  config: {
    enabled: boolean;
    model: string;
    hard_formats: string[];
    stats: LlmStats;
  };
  cascade: {
    cache_hits?: number;
    parsed?: number;
    escalated?: number;
    llm_enriched?: number;
    errors?: number;
    total?: number;
  };
  method_distribution: Record<string, number>;
  avg_confidence: number;
  total_wound_rows: number;
}

export interface DbColumn {
  name: string;
  type: string;
}

export interface DbTablePage {
  table: string;
  total: number;
  limit: number;
  offset: number;
  columns: DbColumn[];
  rows: Record<string, unknown>[];
}

export interface Patient {
  id: number;
  facility_id: number;
  patient_id: string;
  first_name: string | null;
  last_name: string | null;
  birth_date: string | null;
  gender: string | null;
  primary_payer_code: string | null;
  last_modified_at: string | null;
  is_new_admission: boolean;
}
