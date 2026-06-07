export type RunStatus = 'created' | 'running' | 'finished' | 'aborted' | 'idle' | string

export interface TempProgram {
  unit?: 'K' | 'C'
  start: number
  end: number
}

export interface SafetyLimits {
  T_min: number
  T_max: number
  max_step: number
  stable_band?: number
  stable_hold_time?: number
  retry_limit?: number
}

export interface EISParams {
  freq_min_Hz?: number
  freq_max_Hz?: number
  amplitude_mV?: number
  equil_time_s?: number
  instrument?: string
}

export interface RunCreateConfig {
  temp_program: TempProgram
  phase_jump_threshold: number
  step_coarse_k: number
  step_fine_k: number
  safety_limits: SafetyLimits
  eis_params: EISParams
}

export interface RunCreateRequest {
  sample_id: string
  sample_geometry?: {
    length?: number | null
    area?: number | null
  }
  config: RunCreateConfig
}

export interface RunCreateResponse {
  run_id: string
  status: RunStatus
}

export interface RunStateResponse {
  status: RunStatus
  current_state?: Record<string, unknown>
  last_seq?: number
}

export interface RunEventEnvelope<T = Record<string, unknown>> {
  run_id: string
  seq: number
  ts: string
  type: string
  payload: T
  actor?: string
  code_version?: string
  schema_version?: string
}

export interface EvidenceItem {
  evidence_id: string
  evidence_type?: string
  step_idx?: number
  timestamp?: string
  summary?: string
  path?: string
  schema_version?: string
  code_version?: string
}

export interface EvidenceDetail {
  evidence_id: string
  payload: Record<string, unknown>
  schema_version?: string
  code_version?: string
  [key: string]: unknown
}
