import {
  WORKBENCH_EVENT_KIND,
  WORKBENCH_EVENT_SOURCE,
  computeAgentStatus,
  eventDedupKey,
  normalizeWorkbenchEvent,
} from './eventModel.js'
import { initialSchedulerState, reduceSchedulerState } from './schedulerReducer.js'

const MAX_EVENTS = 5000
const MAX_AGENT_MESSAGES = 600
const MAX_TIMELINE_ITEMS = 3000
const MAX_MEASUREMENTS = 3000
const MAX_PHASE_POINTS = 3000
const MAX_EVIDENCE = 1000

function asFiniteNumber(value, fallback = null) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function pushBounded(arr, item, maxLen) {
  if (!Array.isArray(arr)) return [item]
  if (arr.length < maxLen) return [...arr, item]
  return [...arr.slice(arr.length - maxLen + 1), item]
}

function upsertMeasurement(points, patch) {
  const step = Number(patch?.step_idx || 0)
  if (!Number.isFinite(step) || step <= 0) {
    return pushBounded(points, patch, MAX_MEASUREMENTS)
  }

  const idx = points.findIndex((row) => Number(row?.step_idx || 0) === step)
  if (idx < 0) {
    return pushBounded(points, patch, MAX_MEASUREMENTS)
  }

  const next = points.slice()
  next[idx] = { ...next[idx], ...patch }
  return next
}

function updateRunStatus(current, event) {
  switch (event.type) {
    case 'RUN_CREATED':
    case 'RUN_STARTED':
      return 'running'
    case 'RUN_COMPLETED':
    case 'RUN_FINISHED':
      return 'completed'
    case 'RUN_ABORTED':
      return 'aborted'
    default:
      return current || 'idle'
  }
}

function formatAgentMessage(event) {
  const payload = event.payload || {}
  return {
    id: `${event.seq || 0}-${event.type}-${event.source}`,
    seq: event.seq,
    step_idx: event.step_idx,
    ts: event.ts,
    source: event.source,
    type: event.type,
    evidence_id: event.evidence_id,
    text:
      payload.summary ||
      payload.reason ||
      payload.rationale ||
      payload.comment ||
      payload.message ||
      event.type,
    payload,
  }
}

export const initialRunEventsState = {
  run_id: '',
  run_status: 'idle',
  last_seq: 0,
  telemetry: {
    current_temperature_c: null,
    target_temperature_c: null,
    stable: null,
    updated_at: null,
  },
  measurement_points: [],
  arrhenius_state: {
    segments: [],
    breakpoints: [],
    aic_records: [],
    updated_at: null,
  },
  phase_state: {
    threshold: 0.2,
    latest_score: null,
    points: [],
  },
  qc_state: {
    fit_method_code: null,
    rb_ohm: null,
    r2: null,
    qc_grade: 'UNKNOWN',
    qc_status: 'QC_UNKNOWN',
    reason_code: null,
    retest_recommended: false,
    updated_at: null,
  },
  risk_state: {
    decision: null,
    reason_code: null,
    clamped_target_c: null,
    note: null,
    updated_at: null,
  },
  negotiation: {
    planner: null,
    critic: null,
    orchestrator: null,
  },
  agent_status: {
    [WORKBENCH_EVENT_SOURCE.ORCHESTRATOR]: 'idle',
    [WORKBENCH_EVENT_SOURCE.PLANNER]: 'idle',
    [WORKBENCH_EVENT_SOURCE.CRITIC]: 'idle',
    [WORKBENCH_EVENT_SOURCE.CONTROLLER_ADAPTER]: 'idle',
    [WORKBENCH_EVENT_SOURCE.ANALYSIS_AGENT]: 'idle',
    [WORKBENCH_EVENT_SOURCE.ACQUISITION_AGENT]: 'idle',
  },
  agent_messages: [],
  tool_timeline: [],
  events: [],
  evidence_index: [],
  evidence_by_id: {},
  active_evidence_id: null,
  seen_keys: {},
  scheduler: initialSchedulerState,
}

export function runEventsReducer(state = initialRunEventsState, rawEvent, options = {}) {
  const event = normalizeWorkbenchEvent(rawEvent, options.run_id || state.run_id)

  if (!event.type) return state

  const dedupKey = eventDedupKey(event)
  if (state.seen_keys[dedupKey]) {
    return state
  }

  const payload = event.payload || {}
  const seen_keys = { ...state.seen_keys, [dedupKey]: true }

  const next = {
    ...state,
    run_id: event.run_id || state.run_id,
    run_status: updateRunStatus(state.run_status, event),
    last_seq: Math.max(Number(state.last_seq || 0), Number(event.seq || 0)),
    seen_keys,
    events: pushBounded(state.events, event, MAX_EVENTS),
    agent_status: computeAgentStatus(state.agent_status, event),
  }

  if (event.kind === WORKBENCH_EVENT_KIND.TOOL_STARTED || event.kind === WORKBENCH_EVENT_KIND.TOOL_FINISHED) {
    next.tool_timeline = pushBounded(
      state.tool_timeline,
      {
        id: `${event.seq || 0}-${event.type}-${event.source}`,
        seq: event.seq,
        step_idx: event.step_idx,
        ts: event.ts,
        source: event.source,
        type: event.type,
        kind: event.kind,
        evidence_id: event.evidence_id,
        payload,
      },
      MAX_TIMELINE_ITEMS
    )
  }

  if (event.kind === WORKBENCH_EVENT_KIND.RUN_STATE || event.type === 'TELEMETRY_T' || event.type === 'WAIT_STABLE' || event.type === 'SET_T') {
    const current = asFiniteNumber(
      payload.current_temperature_c ?? payload.current_temperature_C ?? payload.current_temperature ?? payload.actual_temperature_C,
      next.telemetry.current_temperature_c
    )
    const target = asFiniteNumber(
      payload.target_temperature_c ?? payload.target_temperature_C ?? payload.target_temperature,
      next.telemetry.target_temperature_c
    )
    const stable = payload.stable ?? payload.stability_ok ?? next.telemetry.stable

    next.telemetry = {
      current_temperature_c: current,
      target_temperature_c: target,
      stable: stable === null || stable === undefined ? null : Boolean(stable),
      updated_at: event.ts,
    }
  }

  if (
    event.type === 'EIS_ACQUIRED' ||
    event.type === 'RB_FIT_DONE' ||
    event.type === 'RB_FIT' ||
    event.type === 'QC_GRADED' ||
    event.type === 'QC_GRADE'
  ) {
    const measurementPatch = {
      step_idx: event.step_idx,
      ts: event.ts,
      t_c: asFiniteNumber(
        payload.temperature_c ?? payload.temperature_C ?? payload.t_actual_c ?? payload.t_actual ?? payload.temp,
        null
      ),
      rb_ohm: asFiniteNumber(payload.rb_ohm, null),
      sigma_s_cm: asFiniteNumber(payload.sigma_s_cm ?? payload.conductivity_S_per_cm ?? payload.conductivity ?? payload.sigma_s_cm1 ?? payload.sigma, null),
      r2:
        payload.r2 === null || payload.r_squared === null
          ? null
          : asFiniteNumber(payload.r2 ?? payload.r_squared, null),
      qc_grade: payload.qc_grade ?? payload.grade ?? null,
      qc_status: payload.qc_status ?? null,
      fit_method_code: payload.fit_method_code ?? payload.fit_method ?? payload.rb_method ?? null,
      evidence_id: event.evidence_id,
    }
    next.measurement_points = upsertMeasurement(state.measurement_points, measurementPatch)
  }

  if (event.kind === WORKBENCH_EVENT_KIND.QC_RESULT) {
    next.qc_state = {
      fit_method_code: payload.fit_method_code ?? payload.fit_method ?? payload.rb_method ?? state.qc_state.fit_method_code,
      rb_ohm: asFiniteNumber(payload.rb_ohm, state.qc_state.rb_ohm),
      r2:
        payload.r2 === null || payload.r_squared === null
          ? null
          : asFiniteNumber(payload.r2 ?? payload.r_squared, state.qc_state.r2),
      qc_grade: payload.qc_grade ?? payload.grade ?? state.qc_state.qc_grade,
      qc_status: payload.qc_status ?? state.qc_state.qc_status,
      reason_code: payload.reason_code ?? payload.qc_reason_code ?? state.qc_state.reason_code,
      retest_recommended: Boolean(payload.retest_recommended ?? payload.retest ?? payload.re_measure ?? state.qc_state.retest_recommended),
      updated_at: event.ts,
    }

    if (state.qc_state.r2 !== null && (payload.r2 === null || payload.r_squared === null)) {
      next.qc_state.r2 = null
    }
  }

  if (event.kind === WORKBENCH_EVENT_KIND.PHASE_JUMP) {
    const score = asFiniteNumber(payload.phase_jump_score ?? payload.score, null)
    const threshold = asFiniteNumber(payload.threshold, state.phase_state.threshold)

    next.phase_state = {
      threshold,
      latest_score: score,
      points: score === null
        ? state.phase_state.points
        : pushBounded(
            state.phase_state.points,
            {
              seq: event.seq,
              step_idx: event.step_idx,
              ts: event.ts,
              score,
              threshold,
              delta_t: asFiniteNumber(payload.delta_t ?? payload.delta_T ?? payload.step_size ?? payload.step_k, null),
              evidence_id: event.evidence_id,
            },
            MAX_PHASE_POINTS
          ),
    }
  }

  if (event.kind === WORKBENCH_EVENT_KIND.SAFETY) {
    next.risk_state = {
      decision: payload.decision ?? payload.result ?? state.risk_state.decision,
      reason_code: payload.reason_code ?? state.risk_state.reason_code,
      clamped_target_c: asFiniteNumber(payload.clamped_target ?? payload.clamped_target_c, state.risk_state.clamped_target_c),
      note: payload.note ?? payload.message ?? state.risk_state.note,
      updated_at: event.ts,
    }
  }

  if (event.type === 'ARRHENIUS_UPDATED' || event.type === 'ARRHENIUS_SEGMENT_DONE' || event.type === 'BREAKPOINT_FOUND' || event.type === 'BREAKPOINT') {
    next.arrhenius_state = {
      segments: Array.isArray(payload.segments) ? payload.segments : state.arrhenius_state.segments,
      breakpoints: Array.isArray(payload.breakpoints)
        ? payload.breakpoints
        : Array.isArray(payload.breakpoint_candidates)
          ? payload.breakpoint_candidates
          : state.arrhenius_state.breakpoints,
      aic_records: Array.isArray(payload.aic_records)
        ? payload.aic_records
        : Array.isArray(payload.aic_table)
          ? payload.aic_table
          : state.arrhenius_state.aic_records,
      updated_at: event.ts,
    }
  }

  if (event.kind === WORKBENCH_EVENT_KIND.AGENT_MESSAGE || event.kind === WORKBENCH_EVENT_KIND.SAFETY || event.type === 'QC_GRADED' || event.type === 'QC_GRADE') {
    const message = formatAgentMessage(event)
    next.agent_messages = pushBounded(state.agent_messages, message, MAX_AGENT_MESSAGES)

    if (event.source === WORKBENCH_EVENT_SOURCE.PLANNER || event.type === 'PLAN_PROPOSED') {
      next.negotiation = { ...next.negotiation, planner: message }
    } else if (event.source === WORKBENCH_EVENT_SOURCE.CRITIC || event.type === 'CRITIC_REVIEWED' || event.type === 'QC_GRADED' || event.type === 'QC_GRADE') {
      next.negotiation = { ...next.negotiation, critic: message }
    } else if (event.source === WORKBENCH_EVENT_SOURCE.ORCHESTRATOR || event.type === 'ACTION_EXECUTED') {
      next.negotiation = { ...next.negotiation, orchestrator: message }
    }
  }

  if (event.kind === WORKBENCH_EVENT_KIND.EVIDENCE_GENERATED || event.evidence_id) {
    const evidence_id = String(event.evidence_id || payload.evidence_id || '').trim()
    if (evidence_id) {
      if (!state.evidence_index.includes(evidence_id)) {
        next.evidence_index = pushBounded(state.evidence_index, evidence_id, MAX_EVIDENCE)
      }
      next.active_evidence_id = evidence_id
    }
  }

  next.scheduler = reduceSchedulerState(state.scheduler || initialSchedulerState, event, next)

  return next
}

export default runEventsReducer







