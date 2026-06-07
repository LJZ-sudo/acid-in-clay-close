import { create } from 'zustand'

const toNumber = (value, fallback = null) => {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

const kToC = (value) => {
  const n = toNumber(value)
  return n === null ? null : n - 273.15
}

const toBool = (value, fallback = null) => {
  if (value === null || value === undefined) return fallback
  if (typeof value === 'boolean') return value
  const text = String(value).trim().toLowerCase()
  if (['true', '1', 'yes', 'y', 'on'].includes(text)) return true
  if (['false', '0', 'no', 'n', 'off'].includes(text)) return false
  return fallback
}

const extractR2 = (payload = {}) => {
  if (payload.r2 === null || payload.r_squared === null) return null
  return toNumber(payload.r2 ?? payload.r_squared)
}

const extractTemperatureC = (payload = {}) => {
  const candidatesC = [
    payload.temperature_C,
    payload.temperature_c,
    payload.t_actual_c,
    payload.t_actual,
    payload.actual_temperature_C,
    payload.actual_temperature,
    payload.current_temperature_C,
    payload.current_temperature_c,
    payload.current_temperature,
  ]
  for (const item of candidatesC) {
    const n = toNumber(item)
    if (n !== null) return n
  }

  const candidatesK = [
    payload.t_k,
    payload.temperature_k,
    payload.current_t_k,
    payload.t_actual_k,
  ]
  for (const item of candidatesK) {
    const n = kToC(item)
    if (n !== null) return n
  }
  return null
}

const extractTargetTemperatureC = (payload = {}) => {
  const candidatesC = [
    payload.target_temperature_C,
    payload.target_temperature_c,
    payload.target_temperature,
    payload.target_c,
    payload.setpoint_C,
  ]
  for (const item of candidatesC) {
    const n = toNumber(item)
    if (n !== null) return n
  }

  const candidatesK = [
    payload.target_t_k,
    payload.setpoint_K,
    payload.target_k,
  ]
  for (const item of candidatesK) {
    const n = kToC(item)
    if (n !== null) return n
  }
  return null
}

const extractConductivity = (payload = {}) => {
  const keys = [
    payload.conductivity_S_per_cm,
    payload.conductivity_s_per_cm,
    payload.conductivity,
    payload.sigma_s_cm,
    payload.sigma_s_cm1,
    payload.sigma,
  ]
  for (const item of keys) {
    const n = toNumber(item)
    if (n !== null) return n
  }
  return null
}

const normalizeBreakpoint = (row) => {
  if (row === null || row === undefined) return null

  if (typeof row === 'number' || typeof row === 'string') {
    const n = toNumber(row)
    if (n === null) return null
    if (n > 170) {
      return { t_k: n, temperature_C: n - 273.15 }
    }
    return { t_k: n + 273.15, temperature_C: n }
  }

  if (typeof row !== 'object') return null

  const tempC = toNumber(row.temperature_C ?? row.temperature_c ?? row.t_c)
  const tempK = toNumber(row.t_k ?? row.temperature_k)
  const finalK = tempK ?? (tempC === null ? null : tempC + 273.15)
  const finalC = tempC ?? (tempK === null ? null : tempK - 273.15)

  if (finalK === null && finalC === null) return null
  return {
    ...row,
    t_k: finalK,
    temperature_C: finalC,
  }
}

const normalizeSegment = (segment) => {
  if (!segment || typeof segment !== 'object') return null

  let rangeC = null
  if (Array.isArray(segment.temperature_range_C) && segment.temperature_range_C.length >= 2) {
    const a = toNumber(segment.temperature_range_C[0])
    const b = toNumber(segment.temperature_range_C[1])
    if (a !== null && b !== null) {
      rangeC = [Math.max(a, b), Math.min(a, b)]
    }
  }

  if (!rangeC && Array.isArray(segment.t_range_k) && segment.t_range_k.length >= 2) {
    const aK = toNumber(segment.t_range_k[0])
    const bK = toNumber(segment.t_range_k[1])
    if (aK !== null && bK !== null) {
      const aC = aK - 273.15
      const bC = bK - 273.15
      rangeC = [Math.max(aC, bC), Math.min(aC, bC)]
    }
  }

  return {
    ...segment,
    temperature_range_C: rangeC || segment.temperature_range_C || null,
  }
}

const normalizeMessageRole = (type = '') => {
  const t = String(type || '').toUpperCase()
  if (t === 'PLAN_PROPOSED' || t === 'TRIGGER_FINE_SCAN') return 'planner'
  if (t === 'RISK_CHECKED' || t === 'CRITIC_REVIEWED' || t === 'QC_GRADED' || t === 'QC_GRADE') return 'critic'
  if (t === 'ACTION_EXECUTED' || t === 'BACKTRACK' || t === 'RE_MEASURE' || t === 'SET_T') return 'orchestrator'
  return 'system'
}

const initialState = {
  runId: null,
  runStatus: 'idle',
  connectionStatus: 'disconnected',
  lastSeq: 0,
  telemetry: {
    current_temperature: null,
    target_temperature: null,
    stable: null,
    ts: null,
  },
  measurementPoints: [],
  arrheniusState: {
    segments: [],
    breakpoints: [],
    f_test_records: [],
    aic_records: [],
  },
  phaseScores: [],
  stepSizes: [],
  agentMessages: [],
  evidenceIndex: [],
  evidenceById: {},
  events: [],
  qcLatest: {
    fit_method: null,
    rb_ohm: null,
    r2: null,
    qc_grade: null,
    critic_score: null,
    qc_reason_code: null,
    retest_recommended: false,
    residual: null,
  },
  riskControl: {
    decision: null,
    reason_code: null,
    clamped_target: null,
    note: null,
  },
  commandState: {
    action: null,
    reason: null,
    seq: null,
  },
}

function upsertByStep(arr, point) {
  const step = Number(point?.step_idx || 0)
  if (!Number.isFinite(step) || step <= 0) {
    return [...arr, point]
  }
  const idx = arr.findIndex((it) => Number(it?.step_idx || 0) === step)
  if (idx < 0) return [...arr, point]
  const next = arr.slice()
  next[idx] = { ...next[idx], ...point }
  return next
}

function eventSignature(evt) {
  return `${Number(evt?.seq || 0)}:${String(evt?.type || '').toUpperCase()}:${String(evt?.evidence_id || '')}`
}

export const useArrheniusRunStore = create((set, get) => ({
  ...initialState,

  reset() {
    set({ ...initialState })
  },

  setRunMeta(runId, status = 'created') {
    set({ runId, runStatus: status || 'created' })
  },

  setConnectionStatus(status) {
    set({ connectionStatus: status })
  },

  setEvidenceIndex(index = []) {
    set({ evidenceIndex: Array.isArray(index) ? index : [] })
  },

  setEvidenceDetail(evidence) {
    if (!evidence?.evidence_id) return
    set((state) => ({
      evidenceById: {
        ...state.evidenceById,
        [evidence.evidence_id]: evidence,
      },
    }))
  },

  upsertMeasurementFromEvidence(evidence) {
    const payload = evidence?.payload || {}
    const measurementEvidence = payload.measurement_evidence || {}
    const analysisEvidence = payload.analysis_evidence || {}
    const processingFit = payload.processing?.rb_fit || {}
    const processingPhase = payload.processing?.phase_jump || {}
    const temperaturePack = payload.temperature || {}

    const point = {
      evidence_id: evidence?.evidence_id,
      step_idx: Number(evidence?.step_idx || payload.step_idx || 0),
      ts: evidence?.timestamp,
      temperature_C: extractTemperatureC({
        ...payload,
        temperature_C: payload.temperature_C ?? kToC(temperaturePack.measured_K) ?? kToC(measurementEvidence?.stability_logs?.actual_t_k),
      }),
      target_temperature_C: extractTargetTemperatureC({
        ...payload,
        target_temperature_C: payload.target_temperature_C ?? kToC(temperaturePack.setpoint_K) ?? kToC(measurementEvidence?.stability_logs?.target_t_k),
      }),
      rb_ohm: toNumber(payload.rb_ohm ?? analysisEvidence.rb_ohm ?? processingFit.rb_ohm),
      conductivity_S_per_cm: extractConductivity(payload),
      r2: (() => {
        if (payload.r_squared === null || payload.r2 === null) return null
        return toNumber(
          payload.r_squared ?? payload.r2 ?? analysisEvidence.r2 ?? processingFit.r2,
          null
        )
      })(),
      qc_grade: payload.qc_grade || analysisEvidence?.qc?.qc_grade || processingFit.qc_grade || null,
      fit_method: payload.rb_method || payload.fit_method || analysisEvidence.fit_method || processingFit.method_selected || null,
      residual: toNumber(payload.residual ?? analysisEvidence?.residuals?.residual_norm ?? processingFit.residual_norm),
      phase_jump_score: toNumber(payload.phase_jump_score ?? processingPhase.score),
      nyquist_preview: Array.isArray(payload.nyquist_preview) ? payload.nyquist_preview : [],
      bode_preview: Array.isArray(payload.bode_preview) ? payload.bode_preview : [],
      re_measure_triggered: Boolean(payload.re_measure_triggered ?? analysisEvidence?.qc?.retest_recommended ?? processingFit.retest_recommended),
    }

    set((state) => ({
      measurementPoints: upsertByStep(state.measurementPoints, point),
      qcLatest: {
        ...state.qcLatest,
        rb_ohm: point.rb_ohm ?? state.qcLatest.rb_ohm,
        r2: point.r2 === null ? null : (point.r2 ?? state.qcLatest.r2),
        qc_grade: point.qc_grade || state.qcLatest.qc_grade,
        fit_method: point.fit_method || state.qcLatest.fit_method,
        residual: point.residual ?? state.qcLatest.residual,
        retest_recommended: Boolean(point.re_measure_triggered || state.qcLatest.retest_recommended),
      },
      phaseScores: point.phase_jump_score === null || point.phase_jump_score === undefined
        ? state.phaseScores
        : upsertByStep(state.phaseScores, {
            step_idx: point.step_idx,
            ts: point.ts,
            score: point.phase_jump_score,
            threshold: null,
          }),
    }))
  },

  applyEvent(evt) {
    const seq = Number(evt?.seq || 0)
    const type = String(evt?.type || '').toUpperCase()
    const payload = (evt?.payload && typeof evt.payload === 'object') ? evt.payload : {}
    const eventTs = evt?.ts || evt?.timestamp || new Date().toISOString()

    const state = get()
    if (seq > 0 && seq < Number(state.lastSeq || 0)) {
      return
    }

    const signature = eventSignature({ ...evt, type })
    if (seq > 0 && seq === Number(state.lastSeq || 0)) {
      const duplicated = state.events.slice(-24).some((row) => eventSignature(row) === signature)
      if (duplicated) return
    }

    const step_idx = Number(payload.step_idx ?? evt.step_idx ?? evt.seq ?? 0)
    const nextEvent = {
      ...evt,
      ts: eventTs,
      payload,
      step_idx,
      type,
    }

    const next = {
      lastSeq: seq > 0 ? Math.max(seq, Number(state.lastSeq || 0)) : state.lastSeq,
      events: [...state.events, nextEvent].slice(-2000),
      commandState: {
        ...state.commandState,
        action: type,
        reason: payload.reason || payload.trigger_reason || null,
        seq,
      },
    }

    if (type === 'RUN_CREATED') {
      next.runStatus = state.runStatus === 'idle' ? 'running' : state.runStatus
    }
    if (type === 'RUN_COMPLETED' || type === 'RUN_FINISHED') {
      next.runStatus = 'completed'
    }
    if (type === 'RUN_ABORTED') {
      next.runStatus = 'aborted'
    }

    if (type === 'TELEMETRY_T' || type === 'WAIT_STABLE' || type === 'SET_T') {
      next.telemetry = {
        ...state.telemetry,
        current_temperature: extractTemperatureC(payload) ?? state.telemetry.current_temperature,
        target_temperature: extractTargetTemperatureC(payload) ?? state.telemetry.target_temperature,
        stable: toBool(payload.stability_ok ?? payload.stable, state.telemetry.stable),
        ts: eventTs,
      }
    }

    if (type === 'SET_T') {
      const delta = toNumber(payload.delta_T ?? payload.step_size ?? payload.step_k)
      if (delta !== null) {
        next.stepSizes = upsertByStep(state.stepSizes, {
          step_idx,
          ts: eventTs,
          value: delta,
        })
      }
    }

    if (type === 'PHASE_SCORE_UPDATED' || type === 'PHASE_SCORE') {
      const score = toNumber(payload.phase_jump_score ?? payload.score)
      const threshold = toNumber(payload.threshold)
      if (score !== null) {
        next.phaseScores = upsertByStep(state.phaseScores, {
          step_idx,
          ts: eventTs,
          score,
          threshold,
          reason: payload.reason || null,
        })
      }
      if (payload.delta_T !== undefined || payload.step_k !== undefined) {
        next.stepSizes = upsertByStep(state.stepSizes, {
          step_idx,
          ts: eventTs,
          value: toNumber(payload.delta_T ?? payload.step_k),
        })
      }
    }

    if (type === 'RB_FIT_DONE' || type === 'RB_FIT') {
      const measurementPatch = {
        step_idx,
        ts: eventTs,
        temperature_C: extractTemperatureC(payload),
        target_temperature_C: extractTargetTemperatureC(payload),
        rb_ohm: toNumber(payload.rb_ohm),
        conductivity_S_per_cm: extractConductivity(payload),
        r2: extractR2(payload),
        fit_method: payload.fit_method || payload.rb_method || payload.fit_method_code || null,
        residual: toNumber(payload.residual ?? payload.residual_norm),
        evidence_id: evt.evidence_id || payload.evidence_id || null,
      }

      next.measurementPoints = upsertByStep(state.measurementPoints, measurementPatch)
      next.qcLatest = {
        ...state.qcLatest,
        fit_method: measurementPatch.fit_method || state.qcLatest.fit_method,
        rb_ohm: measurementPatch.rb_ohm ?? state.qcLatest.rb_ohm,
        r2: measurementPatch.r2 === null ? null : (measurementPatch.r2 ?? state.qcLatest.r2),
        residual: measurementPatch.residual ?? state.qcLatest.residual,
      }
    }

    if (type === 'QC_GRADED' || type === 'QC_GRADE') {
      const qcPatch = {
        step_idx,
        ts: eventTs,
        r2: extractR2(payload),
        qc_grade: payload.qc_grade || payload.grade || payload.critic_grade || null,
      }

      next.measurementPoints = upsertByStep(state.measurementPoints, qcPatch)
      next.qcLatest = {
        ...state.qcLatest,
        r2: qcPatch.r2 === null ? null : (qcPatch.r2 ?? state.qcLatest.r2),
        qc_grade: qcPatch.qc_grade || state.qcLatest.qc_grade,
        critic_score: toNumber(payload.critic_score, state.qcLatest.critic_score),
        qc_reason_code: payload.qc_reason_code || payload.reason_code || state.qcLatest.qc_reason_code,
        retest_recommended: Boolean(payload.retest_recommendation ?? payload.retest_recommended ?? payload.re_measure ?? state.qcLatest.retest_recommended),
      }
    }

    if (type === 'COMMAND_DONE') {
      const measurement = payload.result?.measurement || payload.measurement
      if (measurement && typeof measurement === 'object') {
        const command = String(payload.command || '').toUpperCase()
        const measurementPatch = {
          step_idx,
          ts: eventTs,
          temperature_C: extractTemperatureC(measurement),
          target_temperature_C: extractTargetTemperatureC(measurement),
          rb_ohm: toNumber(measurement.rb_ohm ?? measurement.rb),
          conductivity_S_per_cm: extractConductivity(measurement),
          r2: extractR2(measurement),
          fit_method: measurement.fit_method || measurement.rb_method || null,
          evidence_id: evt.evidence_id || payload.evidence_id || null,
        }
        next.measurementPoints = upsertByStep(state.measurementPoints, measurementPatch)

        if (command === 'ANALYZE_EIS' || command === 'EIS_RUN') {
          next.qcLatest = {
            ...state.qcLatest,
            fit_method: measurementPatch.fit_method || state.qcLatest.fit_method,
            rb_ohm: measurementPatch.rb_ohm ?? state.qcLatest.rb_ohm,
            r2: measurementPatch.r2 === null ? null : (measurementPatch.r2 ?? state.qcLatest.r2),
          }
        }
      }
    }

    if (type === 'RISK_CHECKED') {
      const result = payload.result && typeof payload.result === 'object' ? payload.result : payload
      const reasonCode =
        payload.reason_code ||
        result.reason_code ||
        result.reason?.code ||
        null

      next.riskControl = {
        decision: payload.decision || result.decision || result.result || null,
        reason_code: reasonCode,
        clamped_target: extractTargetTemperatureC({
          target_temperature_C: payload.clamped_target,
          target_t_k: payload.clamped_target,
        }) ?? extractTargetTemperatureC(result.action?.params || {}),
        note: payload.note || payload.message || result.reason?.message_en || result.reason?.code || null,
      }
    }

    if (type === 'ARRHENIUS_UPDATED' || type === 'BREAKPOINT_FOUND' || type === 'BREAKPOINT' || type === 'ARRHENIUS_SEGMENT_DONE') {
      const rawSegments = Array.isArray(payload.segments) ? payload.segments : state.arrheniusState.segments
      const rawBreakpoints = Array.isArray(payload.breakpoints)
        ? payload.breakpoints
        : Array.isArray(payload.breakpoint_candidates)
          ? payload.breakpoint_candidates
          : Array.isArray(payload.breakpoints_k)
            ? payload.breakpoints_k
            : state.arrheniusState.breakpoints

      const modelSelection = payload.model_selection && typeof payload.model_selection === 'object'
        ? payload.model_selection
        : {}

      next.arrheniusState = {
        segments: rawSegments.map(normalizeSegment).filter(Boolean),
        breakpoints: rawBreakpoints.map(normalizeBreakpoint).filter(Boolean),
        f_test_records: payload.f_test_records || payload.ftest_p_values || modelSelection.ftest_p_values || state.arrheniusState.f_test_records,
        aic_records: payload.aic_records || payload.aic_bic_records || payload.aic_table || modelSelection.aic_table || state.arrheniusState.aic_records,
      }
    }

    if (type === 'EVIDENCE_PACKAGED') {
      const evidence = payload.evidence && typeof payload.evidence === 'object'
        ? payload.evidence
        : (payload.evidence_id ? { evidence_id: payload.evidence_id, ...payload } : null)
      if (evidence?.evidence_id) {
        next.evidenceById = {
          ...state.evidenceById,
          [evidence.evidence_id]: evidence,
        }
      }
    }

    if (
      type === 'PLAN_PROPOSED' ||
      type === 'CRITIC_REVIEWED' ||
      type === 'RISK_CHECKED' ||
      type === 'ACTION_EXECUTED' ||
      type === 'TRIGGER_FINE_SCAN' ||
      type === 'BACKTRACK' ||
      type === 'RE_MEASURE'
    ) {
      next.agentMessages = [
        ...state.agentMessages,
        {
          seq,
          step_idx,
          ts: eventTs,
          role: normalizeMessageRole(type),
          type,
          payload,
        },
      ].slice(-600)
    }

    set(next)
  },
}))

export default useArrheniusRunStore
