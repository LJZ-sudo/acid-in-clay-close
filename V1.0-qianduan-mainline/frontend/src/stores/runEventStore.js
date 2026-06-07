import { create } from 'zustand'
import { initialRunEventsState, runEventsReducer } from '../features/runEvents/reducer'

const cloneInitial = () => ({
  ...initialRunEventsState,
  telemetry: { ...initialRunEventsState.telemetry },
  arrhenius_state: { ...initialRunEventsState.arrhenius_state },
  phase_state: { ...initialRunEventsState.phase_state, points: [] },
  qc_state: { ...initialRunEventsState.qc_state },
  risk_state: { ...initialRunEventsState.risk_state },
  negotiation: { ...initialRunEventsState.negotiation },
  agent_status: { ...initialRunEventsState.agent_status },
  measurement_points: [],
  agent_messages: [],
  tool_timeline: [],
  events: [],
  evidence_index: [],
  evidence_by_id: {},
  seen_keys: {},
  scheduler: {
    ...initialRunEventsState.scheduler,
    nodes: Object.fromEntries(Object.entries(initialRunEventsState.scheduler?.nodes || {}).map(([k, v]) => [k, { ...v }]))
  },
})

const useRunEventStore = create((set, get) => ({
  ...cloneInitial(),

  reset(runId = '') {
    const next = cloneInitial()
    next.run_id = runId || ''
    set(next)
  },

  bindRun(runId = '') {
    set((state) => ({ ...state, run_id: String(runId || '') }))
  },

  applyEvent(rawEvent) {
    set((state) => runEventsReducer(state, rawEvent, { run_id: state.run_id }))
  },

  applyEvents(events = []) {
    if (!Array.isArray(events) || events.length === 0) return
    set((state) => {
      let next = state
      for (const row of events) {
        next = runEventsReducer(next, row, { run_id: next.run_id })
      }
      return next
    })
  },

  setEvidenceDetail(evidence = {}) {
    const evidenceId = String(evidence?.evidence_id || '').trim()
    if (!evidenceId) return

    set((state) => ({
      evidence_by_id: {
        ...state.evidence_by_id,
        [evidenceId]: evidence,
      },
      evidence_index: state.evidence_index.includes(evidenceId)
        ? state.evidence_index
        : [...state.evidence_index, evidenceId],
      active_evidence_id: evidenceId,
    }))
  },

  setActiveEvidence(evidenceId) {
    set({ active_evidence_id: evidenceId || null })
  },

  clearSeenEvents() {
    set({ seen_keys: {} })
  },

  getLatestEventByType(type) {
    const normalized = String(type || '').toUpperCase()
    const events = get().events
    for (let i = events.length - 1; i >= 0; i -= 1) {
      if (String(events[i]?.type || '').toUpperCase() === normalized) return events[i]
    }
    return null
  },
}))

export default useRunEventStore

