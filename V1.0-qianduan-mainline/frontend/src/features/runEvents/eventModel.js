export const WORKBENCH_EVENT_KIND = {
  RUN_STATE: 'run_state',
  AGENT_MESSAGE: 'agent_message',
  TOOL_STARTED: 'tool_started',
  TOOL_FINISHED: 'tool_finished',
  QC_RESULT: 'qc_result',
  PHASE_JUMP: 'phase_jump',
  SAFETY: 'safety',
  EVIDENCE_GENERATED: 'evidence_generated',
  OTHER: 'other',
}

export const WORKBENCH_EVENT_SOURCE = {
  ORCHESTRATOR: 'orchestrator',
  PLANNER: 'planner',
  CRITIC: 'critic',
  CONTROLLER_ADAPTER: 'controller_adapter',
  ANALYSIS_AGENT: 'analysis_agent',
  ACQUISITION_AGENT: 'acquisition_agent',
  SYSTEM: 'system',
}

const TYPE_TO_KIND = {
  RUN_CREATED: WORKBENCH_EVENT_KIND.RUN_STATE,
  RUN_STARTED: WORKBENCH_EVENT_KIND.RUN_STATE,
  RUN_COMPLETED: WORKBENCH_EVENT_KIND.RUN_STATE,
  RUN_ABORTED: WORKBENCH_EVENT_KIND.RUN_STATE,
  RUN_FINISHED: WORKBENCH_EVENT_KIND.RUN_STATE,

  PLAN_PROPOSED: WORKBENCH_EVENT_KIND.AGENT_MESSAGE,
  PLANNER_SUGGESTION: WORKBENCH_EVENT_KIND.AGENT_MESSAGE,
  PLAN: WORKBENCH_EVENT_KIND.AGENT_MESSAGE,
  CRITIC_REVIEWED: WORKBENCH_EVENT_KIND.AGENT_MESSAGE,
  DECISION_CRITIQUE: WORKBENCH_EVENT_KIND.AGENT_MESSAGE,
  MEASUREMENT_CRITIQUE: WORKBENCH_EVENT_KIND.AGENT_MESSAGE,
  ACTION_EXECUTED: WORKBENCH_EVENT_KIND.AGENT_MESSAGE,
  DECISION: WORKBENCH_EVENT_KIND.AGENT_MESSAGE,
  TRIGGER_FINE_SCAN: WORKBENCH_EVENT_KIND.AGENT_MESSAGE,
  BACKTRACK: WORKBENCH_EVENT_KIND.AGENT_MESSAGE,
  RE_MEASURE: WORKBENCH_EVENT_KIND.AGENT_MESSAGE,
  RETEST: WORKBENCH_EVENT_KIND.AGENT_MESSAGE,

  SET_T: WORKBENCH_EVENT_KIND.TOOL_STARTED,
  WAIT_STABLE: WORKBENCH_EVENT_KIND.TOOL_STARTED,
  EIS_RUN: WORKBENCH_EVENT_KIND.TOOL_STARTED,
  COMMAND_SENT: WORKBENCH_EVENT_KIND.TOOL_STARTED,
  COMMAND_ACK: WORKBENCH_EVENT_KIND.TOOL_STARTED,

  EIS_PARSE: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  EIS_ACQUIRED: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  RAW_SAVED: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  RB_FIT: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  RB_FIT_DONE: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  ARRHENIUS_SEGMENT: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  ARRHENIUS_SEGMENT_DONE: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  ARRHENIUS_UPDATED: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  BREAKPOINT: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  BREAKPOINT_FOUND: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  PHASE_DETECT: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  REPORT_GENERATE: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  REPORT_DONE: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  STORE: WORKBENCH_EVENT_KIND.TOOL_FINISHED,
  COMMAND_DONE: WORKBENCH_EVENT_KIND.TOOL_FINISHED,

  QC_GRADED: WORKBENCH_EVENT_KIND.QC_RESULT,
  QC_GRADE: WORKBENCH_EVENT_KIND.QC_RESULT,

  PHASE_SCORE_UPDATED: WORKBENCH_EVENT_KIND.PHASE_JUMP,
  PHASE_SCORE: WORKBENCH_EVENT_KIND.PHASE_JUMP,

  RISK_CHECKED: WORKBENCH_EVENT_KIND.SAFETY,
  SAFETY: WORKBENCH_EVENT_KIND.SAFETY,
  SAFETY_VIOLATION: WORKBENCH_EVENT_KIND.SAFETY,
  ERROR: WORKBENCH_EVENT_KIND.SAFETY,

  EVIDENCE_PACKAGED: WORKBENCH_EVENT_KIND.EVIDENCE_GENERATED,
  EVIDENCE_PACKAGE_SAVED: WORKBENCH_EVENT_KIND.EVIDENCE_GENERATED,
  EVIDENCE_GENERATED: WORKBENCH_EVENT_KIND.EVIDENCE_GENERATED,
}

const ACTOR_TO_SOURCE = {
  orchestrator: WORKBENCH_EVENT_SOURCE.ORCHESTRATOR,
  mainagent: WORKBENCH_EVENT_SOURCE.ORCHESTRATOR,
  planner: WORKBENCH_EVENT_SOURCE.PLANNER,
  critic: WORKBENCH_EVENT_SOURCE.CRITIC,
  controlleradapter: WORKBENCH_EVENT_SOURCE.CONTROLLER_ADAPTER,
  controller_adapter: WORKBENCH_EVENT_SOURCE.CONTROLLER_ADAPTER,
  analysisagent: WORKBENCH_EVENT_SOURCE.ANALYSIS_AGENT,
  analysis_agent: WORKBENCH_EVENT_SOURCE.ANALYSIS_AGENT,
  acquisitionagent: WORKBENCH_EVENT_SOURCE.ACQUISITION_AGENT,
  acquisition_agent: WORKBENCH_EVENT_SOURCE.ACQUISITION_AGENT,
  online_analysis: WORKBENCH_EVENT_SOURCE.ANALYSIS_AGENT,
  qc_agent: WORKBENCH_EVENT_SOURCE.CRITIC,
  tools: WORKBENCH_EVENT_SOURCE.ACQUISITION_AGENT,
  evidencepack: WORKBENCH_EVENT_SOURCE.ORCHESTRATOR,
  evidence_package_agent: WORKBENCH_EVENT_SOURCE.ORCHESTRATOR,
}

const EVENT_SOURCE_HINTS = [
  { match: ['PLAN_PROPOSED', 'PLANNER_SUGGESTION', 'PLAN', 'TRIGGER_FINE_SCAN'], source: WORKBENCH_EVENT_SOURCE.PLANNER },
  { match: ['CRITIC_REVIEWED', 'QC_GRADED', 'QC_GRADE', 'RE_MEASURE', 'RETEST', 'DECISION_CRITIQUE', 'MEASUREMENT_CRITIQUE'], source: WORKBENCH_EVENT_SOURCE.CRITIC },
  { match: ['ACTION_EXECUTED', 'RISK_CHECKED', 'RUN_CREATED', 'RUN_STARTED', 'RUN_FINISHED', 'RUN_COMPLETED', 'RUN_ABORTED'], source: WORKBENCH_EVENT_SOURCE.ORCHESTRATOR },
  { match: ['SET_T', 'WAIT_STABLE', 'EIS_RUN', 'COMMAND_SENT', 'COMMAND_ACK', 'COMMAND_DONE', 'BACKTRACK'], source: WORKBENCH_EVENT_SOURCE.CONTROLLER_ADAPTER },
  { match: ['RB_FIT_DONE', 'RB_FIT', 'ARRHENIUS_UPDATED', 'ARRHENIUS_SEGMENT_DONE', 'BREAKPOINT', 'BREAKPOINT_FOUND', 'PHASE_SCORE_UPDATED', 'PHASE_SCORE'], source: WORKBENCH_EVENT_SOURCE.ANALYSIS_AGENT },
  { match: ['EIS_ACQUIRED', 'RAW_SAVED'], source: WORKBENCH_EVENT_SOURCE.ACQUISITION_AGENT },
]

function asFiniteNumber(value, fallback = null) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

export function inferEventSource(type, actor = '') {
  const actorKey = String(actor || '').trim().toLowerCase()
  if (actorKey && ACTOR_TO_SOURCE[actorKey]) {
    return ACTOR_TO_SOURCE[actorKey]
  }

  const normalizedType = String(type || '').trim().toUpperCase()
  for (const row of EVENT_SOURCE_HINTS) {
    if (row.match.includes(normalizedType)) return row.source
  }

  return WORKBENCH_EVENT_SOURCE.SYSTEM
}

export function inferEventKind(type) {
  const normalizedType = String(type || '').trim().toUpperCase()
  return TYPE_TO_KIND[normalizedType] || WORKBENCH_EVENT_KIND.OTHER
}

export function normalizeWorkbenchEvent(raw = {}, fallbackRunId = '') {
  const type = String(raw.type || raw.event_type || '').toUpperCase()
  const payload = raw.payload && typeof raw.payload === 'object' ? raw.payload : {}
  const actor = raw.source || raw.actor || raw.agent || payload.actor || payload.agent || ''
  const source = inferEventSource(type, actor)
  const seq = asFiniteNumber(raw.seq ?? raw.step_idx ?? payload.seq, 0)
  const stepIdx = asFiniteNumber(payload.step_idx ?? raw.step_idx ?? raw.seq, seq || 0)

  return {
    run_id: String(raw.run_id || payload.run_id || fallbackRunId || ''),
    seq,
    step_idx: stepIdx,
    ts: raw.ts || raw.timestamp || payload.timestamp || new Date().toISOString(),
    type,
    kind: inferEventKind(type),
    source,
    payload,
    evidence_id: raw.evidence_id || payload.evidence_id || null,
    actor: actor || source,
  }
}

export function eventDedupKey(evt) {
  return `${evt.run_id || ''}:${evt.seq || 0}:${evt.type || ''}:${evt.evidence_id || ''}`
}

export function computeAgentStatus(prevStatus, event) {
  const next = { ...prevStatus }
  const source = event.source
  const eventType = String(event.type || '').toUpperCase()

  if (event.kind === WORKBENCH_EVENT_KIND.RUN_STATE) {
    if (['RUN_COMPLETED', 'RUN_ABORTED', 'RUN_FINISHED'].includes(eventType)) {
      Object.keys(next).forEach((key) => {
        next[key] = 'idle'
      })
      return next
    }

    if (source && source !== WORKBENCH_EVENT_SOURCE.SYSTEM) {
      next[source] = 'running'
    }
    return next
  }

  if (!source || source === WORKBENCH_EVENT_SOURCE.SYSTEM) return next

  if (event.kind === WORKBENCH_EVENT_KIND.AGENT_MESSAGE) {
    next[source] = 'thinking'
    if (eventType === 'ACTION_EXECUTED' || eventType === 'DECISION') {
      next[source] = 'acting'
    }
    if (eventType === 'RETEST' || eventType === 'RE_MEASURE') {
      next[source] = 'blocked'
    }
    return next
  }

  if (event.kind === WORKBENCH_EVENT_KIND.TOOL_STARTED) {
    next[source] = 'acting'
    return next
  }

  if (event.kind === WORKBENCH_EVENT_KIND.TOOL_FINISHED) {
    next[source] = 'observing'
    return next
  }

  if (event.kind === WORKBENCH_EVENT_KIND.PHASE_JUMP) {
    next[source] = source === WORKBENCH_EVENT_SOURCE.PLANNER ? 'thinking' : 'observing'
    return next
  }

  if (event.kind === WORKBENCH_EVENT_KIND.SAFETY) {
    const decision = String(event.payload?.decision || event.payload?.result || '').toUpperCase()
    if (decision === 'DENY' || decision === 'CLAMPED' || eventType === 'SAFETY_VIOLATION') {
      next[source] = 'blocked'
      return next
    }
    next[source] = 'observing'
    return next
  }

  if (event.kind === WORKBENCH_EVENT_KIND.QC_RESULT) {
    const grade = String(event.payload?.qc_grade || event.payload?.grade || '').toUpperCase()
    const qcStatus = String(event.payload?.qc_status || '').toUpperCase()
    if (['C', 'D', 'UNKNOWN'].includes(grade) || ['QC_FAIL', 'QC_UNKNOWN'].includes(qcStatus)) {
      next[source] = 'blocked'
      return next
    }
    next[source] = 'observing'
    return next
  }

  if (event.kind === WORKBENCH_EVENT_KIND.EVIDENCE_GENERATED) {
    next[source] = 'observing'
    return next
  }

  return next
}
