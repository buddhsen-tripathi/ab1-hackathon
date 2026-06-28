export type RoutingDecision = 'auto_accept' | 'flag_for_review' | 'reject'

export interface ScoreBreakdownItem {
  label: string
  points: number
  earned: boolean | null
}

export interface EvidenceItem {
  field: string
  value: string | number | null
  source: string
  quote: string | null
}

export interface WoundInfo {
  wound_type: string | null
  wound_location: string | null
  wound_stage?: string | null
  length_cm?: number | null
  width_cm?: number | null
  depth_cm?: number | null
  drainage?: string | null
  wound_number?: number
}

export interface Patient {
  patient_id: string
  internal_id: number
  facility_id: number
  facility_name: string
  first_name: string | null
  last_name: string | null
  birth_date: string | null
  gender: string | null
  primary_payer_code: string | null
  is_new_admission: boolean

  has_medicare_part_b: boolean
  coverage_effective_from: string | null
  coverage_effective_to: string | null
  coverage_payer_name: string | null

  wound_type: string | null
  wound_location: string | null
  wound_stage: string | null
  length_cm: number | null
  width_cm: number | null
  depth_cm: number | null
  drainage: string | null
  is_multi_wound: boolean
  all_wounds: WoundInfo[] | null

  evidence_trace: Record<string, string> | null
  extraction_source: string | null
  extraction_confidence: number
  note_format: string | null

  claim_score: number
  routing_decision: RoutingDecision
  missing_fields: string[] | null
  score_breakdown: Record<string, ScoreBreakdownItem> | null
  biller_action: string | null
  routing_reason: string | null
  missing_doc_request: string | null
  summary_narrative: string | null
  summary_generated_by: string | null

  raw_notes: string[] | null
  processed_at: string | null
}

export interface Stats {
  total_patients: number
  auto_accept: number
  flag_for_review: number
  reject: number
  docs_gap_count: number
  medicare_b_count: number
  avg_confidence_pct: number
  last_sync: string | null
  last_sync_mode: 'full' | 'incremental' | null
  last_sync_count: number
  llm_configured: boolean
  incremental_sync_ready: boolean
  api_health: ApiHealth
}

export interface ApiHealth {
  total_requests: number
  total_429s: number
  total_retries: number
  failed_requests: number
  avg_retry_delay_s: number
}

export interface SyncStatus {
  running: boolean
  total: number
  processed: number
  errors: number
  started_at: string | null
  status: 'idle' | 'running' | 'complete'
  current_step: string
  mode: 'full' | 'incremental'
  since: string | null
  changed_patients: number
}
