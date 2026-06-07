import client from './client'
import { API_BASE_URL } from '../utils/constants'

const enc = (v) => encodeURIComponent(String(v || '').trim())

const is404 = (err) => Number(err?.response?.status) === 404

async function withFallback(primary, fallback) {
  try {
    return await primary()
  } catch (err) {
    if (!is404(err) || !fallback) throw err
    return fallback()
  }
}

function toCelsius(value, unit) {
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  if (String(unit || 'K').toUpperCase() === 'C') return n
  return n - 273.15
}

function toKelvin(value, unit) {
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  if (String(unit || 'K').toUpperCase() === 'C') return n + 273.15
  return n
}

function normalizeV1CreatePayload(payload = {}) {
  const src = { ...(payload || {}) }
  if (!src.config || typeof src.config !== 'object') {
    return src
  }

  const cfg = { ...src.config }
  const temp = (cfg.temp_program && typeof cfg.temp_program === 'object')
    ? { ...cfg.temp_program }
    : {}

  const tempUnit = String(temp.unit || 'K').toUpperCase()
  const startK = temp.t_start_k ?? toKelvin(temp.start, tempUnit)
  const endK = temp.t_end_k ?? toKelvin(temp.end, tempUnit)

  if (startK !== null && startK !== undefined) temp.t_start_k = startK
  if (endK !== null && endK !== undefined) temp.t_end_k = endK
  if (temp.step_coarse_k === undefined && cfg.step_coarse_k !== undefined) temp.step_coarse_k = cfg.step_coarse_k
  if (temp.step_fine_k === undefined && cfg.step_fine_k !== undefined) temp.step_fine_k = cfg.step_fine_k
  if (temp.mode === undefined && Number.isFinite(Number(startK)) && Number.isFinite(Number(endK))) {
    temp.mode = Number(startK) >= Number(endK) ? 'cooling' : 'heating'
  }
  if (temp.backtrack === undefined) temp.backtrack = true
  cfg.temp_program = temp

  const safety = (cfg.safety_limits && typeof cfg.safety_limits === 'object')
    ? { ...cfg.safety_limits }
    : {}
  cfg.safety_limits = {
    ...safety,
    t_min_c: safety.t_min_c ?? safety.T_min ?? safety.min_C ?? -120,
    t_max_c: safety.t_max_c ?? safety.T_max ?? safety.max_C ?? 100,
    max_step_c: safety.max_step_c ?? safety.max_step ?? safety.max_step_C ?? 10,
    stable_band_c: safety.stable_band_c ?? safety.stable_band ?? 0.6,
    stable_hold_s: safety.stable_hold_s ?? safety.stable_hold_time ?? 6,
    max_retries_per_point: safety.max_retries_per_point ?? safety.retry_limit ?? 2,
  }

  const eis = (cfg.eis_params && typeof cfg.eis_params === 'object')
    ? { ...cfg.eis_params }
    : {}
  cfg.eis_params = {
    ...eis,
    freq_min_hz: eis.freq_min_hz ?? eis.freq_min_Hz ?? 0.1,
    freq_max_hz: eis.freq_max_hz ?? eis.freq_max_Hz ?? 1_000_000,
    ac_amplitude_mv: eis.ac_amplitude_mv ?? eis.amplitude_mV ?? 10,
    settle_s: eis.settle_s ?? eis.equil_time_s ?? 6,
  }

  const geometry = (cfg.geometry && typeof cfg.geometry === 'object')
    ? { ...cfg.geometry }
    : {}
  const sampleGeometry = (src.sample_geometry && typeof src.sample_geometry === 'object')
    ? src.sample_geometry
    : {}
  cfg.geometry = {
    ...geometry,
    thickness_cm: geometry.thickness_cm ?? sampleGeometry.length ?? 0.1,
    area_cm2: geometry.area_cm2 ?? sampleGeometry.area ?? 1.0,
  }

  return {
    ...src,
    config: cfg,
  }
}

function normalizeRunResponse(data = {}) {
  if (data?.run_id) {
    return {
      run_id: data.run_id,
      status: data.status || 'created',
    }
  }
  if (data?.run) {
    return {
      run_id: data.run.run_id,
      status: data.run.status || 'created',
      current_state: data.run,
      last_seq: Number(data.run.latest_step_idx || 0),
    }
  }
  return {
    run_id: '',
    status: 'idle',
  }
}

function toLegacyCreatePayload(payload = {}) {
  const cfg = (payload.config && typeof payload.config === 'object') ? payload.config : {}
  const temp = (cfg.temp_program && typeof cfg.temp_program === 'object') ? cfg.temp_program : {}
  const strategy = (payload.strategy && typeof payload.strategy === 'object') ? payload.strategy : {}
  const tempRange = (payload.temp_range && typeof payload.temp_range === 'object') ? payload.temp_range : {}
  const eisParams = (cfg.eis_params && typeof cfg.eis_params === 'object') ? cfg.eis_params : (payload.eis_params || {})
  const safetyLimits = (cfg.safety_limits && typeof cfg.safety_limits === 'object') ? cfg.safety_limits : (payload.safety || {})
  const unit = String(temp.unit || 'K').toUpperCase()

  const startRaw = temp.start ?? temp.t_start_k ?? tempRange.start_K
  const endRaw = temp.end ?? temp.t_end_k ?? tempRange.end_K
  const startC = toCelsius(startRaw, unit)
  const endC = toCelsius(endRaw, unit)

  const coarseStep = Number(cfg.step_coarse_k ?? temp.step_coarse_k ?? strategy.coarse_step_K ?? 3)
  const fineStep = Number(cfg.step_fine_k ?? temp.step_fine_k ?? strategy.fine_step_K ?? 1)
  const phaseJumpThreshold = cfg.phase_jump_threshold ?? strategy.phase_jump_threshold ?? payload.phase_jump_threshold

  return {
    mode: payload.mode || 'simulation',
    auto_start: payload.auto_start ?? true,
    profile: {
      phase_jump_threshold: phaseJumpThreshold,
      eis_params: {
        T_start: startC,
        T_end: endC,
        coarse_step: coarseStep,
        fine_step: fineStep,
        freq_min_Hz: eisParams?.freq_min_Hz ?? eisParams?.freq_min_hz,
        freq_max_Hz: eisParams?.freq_max_Hz ?? eisParams?.freq_max_hz,
      },
      safety_limits: safetyLimits,
      sample_id: payload.sample_id || cfg.sample_id,
      sample_geometry: payload.sample_geometry || null,
      eis_settings: eisParams || {},
    },
  }
}

export function normalizeRunEvent(raw = {}) {
  const seq = Number(raw.seq ?? raw.step_idx ?? 0)
  return {
    run_id: String(raw.run_id || ''),
    seq: Number.isFinite(seq) ? seq : 0,
    ts: raw.ts || raw.timestamp || new Date().toISOString(),
    type: String(raw.type || raw.event_type || '').toUpperCase(),
    kind: raw.kind || null,
    source: raw.source || raw.actor || raw.agent || null,
    payload: (raw.payload && typeof raw.payload === 'object') ? raw.payload : {},
    actor: raw.actor || raw.agent || null,
    evidence_id: raw.evidence_id || raw?.payload?.evidence_id || null,
    code_version: raw.code_version,
    schema_version: raw.schema_version,
  }
}

function buildQuery(params = {}) {
  const q = new URLSearchParams()
  if (params.since !== undefined) q.set('since', String(params.since))
  if (params.last_seq !== undefined) q.set('last_seq', String(params.last_seq))
  if (params.from_step !== undefined) q.set('from_step', String(params.from_step))
  if (params.replay_speed !== undefined) q.set('replay_speed', String(params.replay_speed))
  return q.toString() ? `?${q.toString()}` : ''
}

export const runV1Api = {
  async listRuns() {
    const resp = await withFallback(
      () => client.get('/v1/runs'),
      () => client.get('/runs')
    )
    const rows = resp?.data?.runs || []
    return {
      ...resp,
      data: {
        ...resp.data,
        runs: rows,
      },
    }
  },

  async createRun(payload) {
    const normalizedPayload = normalizeV1CreatePayload(payload)
    const resp = await withFallback(
      () => client.post('/v1/runs', normalizedPayload),
      () => client.post('/runs', toLegacyCreatePayload(normalizedPayload))
    )

    return {
      ...resp,
      data: {
        ...resp.data,
        ...normalizeRunResponse(resp?.data),
      },
    }
  },

  async getRun(runId) {
    const rid = enc(runId)
    const resp = await withFallback(
      () => client.get(`/v1/runs/${rid}`),
      () => client.get(`/runs/${rid}`)
    )

    const normalized = normalizeRunResponse(resp?.data)
    return {
      ...resp,
      data: {
        ...resp.data,
        ...normalized,
      },
    }
  },

  async controlRun(runId, payload = {}) {
    const rid = enc(runId)
    const command = String(payload.command || '').trim().toLowerCase()
    const reason = payload.reason

    return withFallback(
      () => client.post(`/v1/runs/${rid}/control`, { command, reason }),
      () => withFallback(
        () => client.post(`/runs/${rid}/control`, { command, reason }),
        () => {
          if (command === 'pause') return client.post('/control/pause')
          if (command === 'resume') return client.post('/control/resume')
          if (command === 'stop') return client.post('/control/stop')
          if (command === 'manual_override') return client.post('/control/autonomous/stop')
          return client.get('/control/status')
        }
      )
    )
  },


  async setAutonomous(enabled, options = {}) {
    const active = Boolean(enabled)
    const runId = options?.runId
    const rid = enc(runId)
    const reason = String(options?.reason || (active ? 'ui_auto_enabled' : 'ui_auto_disabled'))

    if (active) {
      return withFallback(
        () => client.post('/control/autonomous/start', runId ? { run_id: runId } : {}),
        () => runId
          ? withFallback(
              () => client.post(`/v1/runs/${rid}/control`, { command: 'resume', reason }),
              () => client.post(`/runs/${rid}/control`, { command: 'resume', reason })
            )
          : client.get('/control/status')
      )
    }

    return withFallback(
      () => client.post('/control/autonomous/stop'),
      () => runId
        ? withFallback(
            () => client.post(`/v1/runs/${rid}/control`, { command: 'pause', reason }),
            () => client.post(`/runs/${rid}/control`, { command: 'pause', reason })
          )
        : client.get('/control/status')
    )
  },

  async cancelRun(runId) {
    const rid = enc(runId)
    return withFallback(
      () => client.post(`/v1/runs/${rid}/cancel`),
      () => withFallback(
        () => client.post(`/runs/${rid}/cancel`),
        () => client.post('/control/stop')
      )
    )
  },

  async getEvents(runId, params = {}) {
    const rid = enc(runId)
    const resp = await withFallback(
      () => client.get(`/v1/runs/${rid}/events`, { params }),
      () => client.get(`/runs/${rid}/events`, { params })
    )

    const rawRows = resp?.data?.items || resp?.data?.events || []
    const events = (Array.isArray(rawRows) ? rawRows : []).map(normalizeRunEvent)
    return {
      ...resp,
      data: {
        ...resp.data,
        items: events,
        events,
      },
    }
  },

  getEventsStreamCandidates(runId, params = {}) {
    const rid = enc(runId)
    const suffix = buildQuery(params)
    return [
      `${API_BASE_URL}/v1/runs/${rid}/events/stream${suffix}`,
      `${API_BASE_URL}/sse/runs/${rid}${suffix}`,
      `${API_BASE_URL}/runs/${rid}/events/stream${suffix}`,
    ]
  },

  async listEvidence(runId) {
    const rid = enc(runId)
    const resp = await withFallback(
      () => client.get(`/v1/runs/${rid}/evidence`),
      () => client.get(`/runs/${rid}/evidence`)
    )

    const evidence = resp?.data?.evidence || resp?.data?.items || []
    return {
      ...resp,
      data: {
        ...resp.data,
        evidence,
        items: evidence,
      },
    }
  },

  async getEvidence(runId, evidenceId) {
    const rid = enc(runId)
    const eid = enc(evidenceId)
    const resp = await withFallback(
      () => client.get(`/v1/runs/${rid}/evidence/${eid}`),
      () => client.get(`/evidence/${eid}`)
    )
    const evidence = resp?.data?.evidence || resp?.data || null
    return {
      ...resp,
      data: {
        ...(resp?.data && typeof resp.data === 'object' ? resp.data : {}),
        evidence,
      },
    }
  },
  async downloadEvidence(runId, evidenceId) {
    const rid = enc(runId)
    const eid = enc(evidenceId)
    return withFallback(
      () => client.get(`/v1/runs/${rid}/evidence/${eid}`, { params: { download: 1 }, responseType: 'blob' }),
      () => client.get(`/evidence/${eid}`, { params: { download: 1 }, responseType: 'blob' })
    )
  },

  async exportRun(runId) {
    const rid = enc(runId)
    return withFallback(
      () => client.get(`/v1/runs/${rid}/export`, { responseType: 'blob' }),
      () => client.get(`/runs/${rid}/export`, { responseType: 'blob' })
    )
  },

  calculateArrhenius(payload = {}) {
    return client.post('/calculate_arrhenius', payload)
  },

  runArrheniusFromEis(payload = {}) {
    return client.post('/run_arrhenius_from_eis', payload)
  },

  runArrheniusAdvanced(payload = {}) {
    return client.post('/run_arrhenius_advanced', payload)
  },

  evidenceDownloadUrl(runId, evidenceId) {
    const rid = enc(runId)
    const eid = enc(evidenceId)
    return `${API_BASE_URL}/v1/runs/${rid}/evidence/${eid}?download=1`
  },

  exportRunUrl(runId) {
    const rid = enc(runId)
    return `${API_BASE_URL}/v1/runs/${rid}/export`
  },
}

export default runV1Api








