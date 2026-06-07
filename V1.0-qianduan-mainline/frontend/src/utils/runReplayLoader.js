import runsAuditApi from '../api/runsAudit'

/**
 * Read-only load for Run Replay skeleton.
 * Uses GET /runs/:id/manifest (required), GET /runs/:id/events (required call),
 * GET /runs/:id/evidence (optional; failure yields empty list + note).
 *
 * @param {string} runId
 * @returns {Promise<{
 *   ok: boolean,
 *   phase: string,
 *   message?: string,
 *   manifest: object|null,
 *   events: object[],
 *   eventsLoadError: string|null,
 *   evidenceList: object[]|null,
 *   evidenceIndexError: string|null,
 * }>}
 */
export async function loadRunReplay(runId) {
  const id = String(runId ?? '').trim()
  if (!id) {
    return {
      ok: false,
      phase: 'missing_id',
      message: 'Missing run id in the URL.',
      manifest: null,
      events: [],
      eventsLoadError: null,
      evidenceList: null,
      evidenceIndexError: null,
    }
  }

  try {
    const mRes = await runsAuditApi.getManifest(id)
    const manifest = mRes?.data && typeof mRes.data === 'object' ? mRes.data : {}

    let events = []
    let eventsLoadError = null
    try {
      const eRes = await runsAuditApi.getEvents(id)
      events = Array.isArray(eRes?.data?.events) ? eRes.data.events : []
    } catch (err) {
      eventsLoadError =
        err.response?.data?.detail || err.response?.data?.message || err.message || 'Failed to load events.'
    }

    let evidenceList = []
    let evidenceIndexError = null
    try {
      const evRes = await runsAuditApi.listEvidence(id)
      evidenceList = Array.isArray(evRes?.data?.evidence) ? evRes.data.evidence : []
    } catch (err) {
      evidenceIndexError =
        err.response?.data?.detail || err.response?.data?.message || err.message || 'Evidence index request failed.'
    }

    return {
      ok: true,
      phase: 'ready',
      manifest,
      events,
      eventsLoadError,
      evidenceList,
      evidenceIndexError,
    }
  } catch (err) {
    const status = err.response?.status
    const detail = err.response?.data?.detail || err.response?.data?.message
    if (status === 404) {
      return {
        ok: false,
        phase: 'manifest_404',
        message: detail || 'Run manifest not found. The id may be invalid or the run was removed.',
        manifest: null,
        events: [],
        eventsLoadError: null,
        evidenceList: null,
        evidenceIndexError: null,
      }
    }
    if (status === 400) {
      return {
        ok: false,
        phase: 'invalid_id',
        message: detail || 'Invalid run id.',
        manifest: null,
        events: [],
        eventsLoadError: null,
        evidenceList: null,
        evidenceIndexError: null,
      }
    }
    return {
      ok: false,
      phase: 'manifest_error',
      message: detail || err.message || 'Failed to load run manifest (API unreachable or server error).',
      manifest: null,
      events: [],
      eventsLoadError: null,
      evidenceList: null,
      evidenceIndexError: null,
    }
  }
}

/** Map raw event to display fields + coarse category for filters. */
export function normalizeRunEventForReplay(raw, index) {
  const type = raw?.type || raw?.event_type || 'UNKNOWN'
  const seq = raw?.seq ?? raw?.step_idx ?? index
  const ts = raw?.timestamp || raw?.ts || raw?.time || null
  const payload = raw?.payload && typeof raw.payload === 'object' ? raw.payload : {}
  const summary =
    payload.message ||
    payload.summary ||
    payload.reason ||
    payload.action ||
    (payload.target_temperature_C != null ? `Target T ${payload.target_temperature_C} °C` : null) ||
    (payload.rb_ohm != null ? `Rb ${payload.rb_ohm} Ω` : null) ||
    '—'

  const t = String(type).toUpperCase()
  const physical = new Set([
    'EXPERIMENT_STARTED',
    'SET_T',
    'WAIT_STABLE',
    'MEASUREMENT_COMPLETED',
    'TEMPERATURE_REACHED',
    'PHASE_TRANSITION',
    'PHASE_TRANSITION_DETECTED',
    'Rb_FIT',
    'RB_FIT',
    'QC_GRADE',
    'MEASURE',
  ])
  const agent = new Set([
    'PLAN_PROPOSED',
    'CRITIC_REVIEWED',
    'ACTION_EXECUTED',
    'AGENT_DECISION',
    'ORCHESTRATOR',
    'PLANNER',
    'THOUGHT_CHAIN',
  ])
  let category = 'science'
  if (physical.has(t) || t.includes('TEMP') || t.includes('MEASURE')) category = 'physical'
  else if (agent.has(t) || t.includes('PLAN') || t.includes('CRITIC') || t.includes('AGENT')) category = 'agent'

  return {
    raw,
    type,
    seq,
    ts,
    summary: String(summary),
    category,
    evidenceId: raw?.evidence_id || payload.evidence_id || payload.evidence_ref || null,
  }
}
