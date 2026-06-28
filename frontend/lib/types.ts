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
