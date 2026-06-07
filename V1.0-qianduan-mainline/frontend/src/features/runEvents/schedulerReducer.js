import { WORKBENCH_EVENT_KIND } from './eventModel.js'

export const SCHEDULER_NODE_IDS = {
  MEASUREMENT: 'measurement',
  QC_RB: 'qc_rb',
  TRANSITION: 'transition',
  ARRHENIUS: 'arrhenius',
  EVIDENCE: 'evidence',
  REPORT: 'report',
}

export const SCHEDULER_NODE_ORDER = [
  SCHEDULER_NODE_IDS.MEASUREMENT,
  SCHEDULER_NODE_IDS.QC_RB,
  SCHEDULER_NODE_IDS.TRANSITION,
  SCHEDULER_NODE_IDS.ARRHENIUS,
  SCHEDULER_NODE_IDS.EVIDENCE,
  SCHEDULER_NODE_IDS.REPORT,
]

export const SCHEDULER_NODE_META = {
  [SCHEDULER_NODE_IDS.MEASUREMENT]: {
    titleKey: 'workbench.pipeline.measurement.title',
    opsKey: 'workbench.pipeline.measurement.ops',
  },
  [SCHEDULER_NODE_IDS.QC_RB]: {
    titleKey: 'workbench.pipeline.qcRb.title',
    opsKey: 'workbench.pipeline.qcRb.ops',
  },
  [SCHEDULER_NODE_IDS.TRANSITION]: {
    titleKey: 'workbench.pipeline.transition.title',
    opsKey: 'workbench.pipeline.transition.ops',
  },
  [SCHEDULER_NODE_IDS.ARRHENIUS]: {
    titleKey: 'workbench.pipeline.arrhenius.title',
    opsKey: 'workbench.pipeline.arrhenius.ops',
  },
  [SCHEDULER_NODE_IDS.EVIDENCE]: {
    titleKey: 'workbench.pipeline.evidence.title',
    opsKey: 'workbench.pipeline.evidence.ops',
  },
  [SCHEDULER_NODE_IDS.REPORT]: {
    titleKey: 'workbench.pipeline.report.title',
    opsKey: 'workbench.pipeline.report.ops',
  },
}

function buildInitialNodes() {
  return SCHEDULER_NODE_ORDER.reduce((acc, id) => {
    acc[id] = {
      id,
      status: 'idle',
      last_ts: null,
      last_seq: 0,
      last_event_type: null,
      step_idx: null,
      responsible_agent: null,
      evidence_id: null,
      warning_key: null,
      recommendation_key: null,
    }
    return acc
  }, {})
}

export const initialSchedulerState = {
  nodes: buildInitialNodes(),
  active_node_id: null,
  last_updated_at: null,
  warning_key: null,
  recommendation_key: null,
}

function asNumber(value, fallback = null) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function inferNodeId(event) {
  const type = String(event?.type || '').toUpperCase()
  const payload = event?.payload || {}
  const command = String(payload?.command || '').toUpperCase()

  if (['SET_T', 'WAIT_STABLE', 'EIS_RUN', 'EIS_ACQUIRED'].includes(type)) {
    return SCHEDULER_NODE_IDS.MEASUREMENT
  }

  if (type === 'ACTION_EXECUTED' && ['SET_T', 'WAIT_STABLE', 'EIS_RUN'].includes(command)) {
    return SCHEDULER_NODE_IDS.MEASUREMENT
  }

  if (type === 'COMMAND_SENT' || type === 'COMMAND_ACK' || type === 'COMMAND_DONE') {
    if (['SET_T', 'WAIT_STABLE', 'EIS_RUN'].includes(command)) return SCHEDULER_NODE_IDS.MEASUREMENT
    if (['ANALYZE_EIS', 'RB_FIT', 'QC_GRADE'].includes(command)) return SCHEDULER_NODE_IDS.QC_RB
  }

  if (['RAW_SAVED'].includes(type)) {
    return SCHEDULER_NODE_IDS.MEASUREMENT
  }

  if (['RB_FIT_DONE', 'RB_FIT', 'QC_GRADED', 'QC_GRADE', 'RISK_CHECKED', 'SAFETY', 'SAFETY_VIOLATION'].includes(type)) {
    return SCHEDULER_NODE_IDS.QC_RB
  }

  if (['PHASE_SCORE_UPDATED', 'PHASE_SCORE', 'PHASE_DETECT', 'TRIGGER_FINE_SCAN', 'BACKTRACK', 'RE_MEASURE', 'RETEST'].includes(type)) {
    return SCHEDULER_NODE_IDS.TRANSITION
  }

  if (['ARRHENIUS_UPDATED', 'ARRHENIUS_SEGMENT', 'ARRHENIUS_SEGMENT_DONE', 'BREAKPOINT_FOUND', 'BREAKPOINT'].includes(type)) {
    return SCHEDULER_NODE_IDS.ARRHENIUS
  }

  if (['EVIDENCE_PACKAGED', 'EVIDENCE_GENERATED', 'EVIDENCE_PACKAGE_SAVED', 'STORE'].includes(type)) {
    return SCHEDULER_NODE_IDS.EVIDENCE
  }

  if (['REPORT_GENERATE', 'REPORT_DONE'].includes(type)) {
    return SCHEDULER_NODE_IDS.REPORT
  }

  if (type === 'RUN_COMPLETED' || type === 'RUN_FINISHED') {
    return SCHEDULER_NODE_IDS.REPORT
  }

  return null
}

function updateNode(nextState, nodeId, patch) {
  if (!nodeId) return
  const prev = nextState.nodes[nodeId] || {}
  nextState.nodes = {
    ...nextState.nodes,
    [nodeId]: {
      ...prev,
      ...patch,
    },
  }
}

function evaluateQcRecommendation(qcState = {}) {
  const grade = String(qcState?.qc_grade || '').toUpperCase()
  const status = String(qcState?.qc_status || '').toUpperCase()

  if (status === 'QC_UNKNOWN' || grade === 'UNKNOWN') {
    return {
      warning_key: 'workbench.alert.qcUnknown',
      recommendation_key: qcState?.retest_recommended
        ? 'workbench.alert.retestScheduled'
        : 'workbench.alert.blockedAwaitingManualOverride',
      status: 'blocked',
    }
  }

  if (status === 'QC_FAIL' || ['C', 'D'].includes(grade)) {
    return {
      warning_key: 'workbench.alert.qcRiskFlagged',
      recommendation_key: qcState?.retest_recommended
        ? 'workbench.alert.retestScheduled'
        : 'workbench.alert.blockedAwaitingManualOverride',
      status: qcState?.retest_recommended ? 'running' : 'blocked',
    }
  }

  return {
    warning_key: null,
    recommendation_key: null,
    status: 'success',
  }
}

export function reduceSchedulerState(prev = initialSchedulerState, event, snapshot = {}) {
  const payload = event?.payload || {}
  const next = {
    ...prev,
    nodes: { ...(prev?.nodes || buildInitialNodes()) },
  }

  const nodeId = inferNodeId(event)
  const seq = asNumber(event?.seq, 0) || 0
  const step_idx = asNumber(event?.step_idx ?? payload?.step_idx, null)
  const ts = event?.ts || payload?.timestamp || null
  const source = event?.source || event?.actor || null
  const evidence_id = event?.evidence_id || payload?.evidence_id || null
  const type = String(event?.type || '').toUpperCase()

  if (nodeId) {
    let status = 'running'
    let warning_key = null
    let recommendation_key = null

    if (type === 'RUN_ABORTED') {
      status = 'failed'
    } else if (type === 'COMMAND_DONE' && payload?.success === false) {
      status = 'failed'
      warning_key = 'workbench.alert.qcRiskFlagged'
    } else if (nodeId === SCHEDULER_NODE_IDS.MEASUREMENT && ['EIS_ACQUIRED', 'RAW_SAVED'].includes(type)) {
      status = 'success'
    } else if (nodeId === SCHEDULER_NODE_IDS.QC_RB && ['QC_GRADED', 'QC_GRADE'].includes(type)) {
      const qcDecision = evaluateQcRecommendation(snapshot?.qc_state || {})
      status = qcDecision.status
      warning_key = qcDecision.warning_key
      recommendation_key = qcDecision.recommendation_key
    } else if (nodeId === SCHEDULER_NODE_IDS.TRANSITION && ['PHASE_SCORE_UPDATED', 'PHASE_SCORE'].includes(type)) {
      const score = asNumber(payload?.phase_jump_score ?? payload?.score, null)
      const threshold = asNumber(payload?.threshold, asNumber(snapshot?.phase_state?.threshold, 0.2))
      if (score !== null && threshold !== null && score > threshold) {
        status = 'running'
        warning_key = 'workbench.alert.transitionModeTriggered'
        recommendation_key = 'workbench.alert.fineScanBacktrackPolicy'
      } else {
        status = 'success'
      }
    } else if (nodeId === SCHEDULER_NODE_IDS.TRANSITION && ['BACKTRACK', 'RE_MEASURE', 'RETEST', 'TRIGGER_FINE_SCAN'].includes(type)) {
      status = 'running'
      warning_key = 'workbench.alert.fineScanBacktrackPolicy'
      recommendation_key = type === 'RE_MEASURE' || type === 'RETEST'
        ? 'workbench.alert.retestScheduled'
        : null
    } else if (nodeId === SCHEDULER_NODE_IDS.ARRHENIUS && ['ARRHENIUS_UPDATED', 'ARRHENIUS_SEGMENT_DONE', 'BREAKPOINT_FOUND'].includes(type)) {
      status = 'success'
    } else if (nodeId === SCHEDULER_NODE_IDS.EVIDENCE) {
      status = 'success'
    } else if (nodeId === SCHEDULER_NODE_IDS.REPORT && ['RUN_COMPLETED', 'REPORT_DONE'].includes(type)) {
      status = 'success'
    }

    if (type === 'RISK_CHECKED') {
      const decision = String(payload?.decision || payload?.result || '').toUpperCase()
      if (decision === 'DENY') {
        status = 'blocked'
        warning_key = 'workbench.alert.riskDenied'
        recommendation_key = 'workbench.alert.blockedAwaitingManualOverride'
      } else if (decision === 'CLAMPED') {
        status = 'blocked'
        warning_key = 'workbench.alert.riskClamped'
      }
    }

    updateNode(next, nodeId, {
      status,
      last_ts: ts,
      last_seq: seq,
      last_event_type: type,
      step_idx,
      responsible_agent: source,
      evidence_id: evidence_id || next.nodes[nodeId]?.evidence_id || null,
      warning_key,
      recommendation_key,
    })

    next.active_node_id = nodeId
    next.last_updated_at = ts || next.last_updated_at
  }

  if (type === 'RUN_ABORTED') {
    if (next.active_node_id && next.nodes[next.active_node_id]) {
      updateNode(next, next.active_node_id, {
        status: 'failed',
        last_event_type: type,
        last_ts: ts,
        last_seq: seq,
      })
    }
  }

  if (type === 'RUN_COMPLETED' || type === 'RUN_FINISHED') {
    updateNode(next, SCHEDULER_NODE_IDS.REPORT, {
      status: 'success',
      last_ts: ts,
      last_seq: seq,
      last_event_type: type,
      responsible_agent: source,
      step_idx,
      evidence_id: evidence_id || next.nodes[SCHEDULER_NODE_IDS.REPORT]?.evidence_id || null,
      warning_key: null,
      recommendation_key: null,
    })
  }

  const riskDecision = String(snapshot?.risk_state?.decision || '').toUpperCase()
  if (riskDecision === 'DENY' || riskDecision === 'CLAMPED') {
    next.warning_key = 'workbench.alert.blockedAwaitingManualOverride'
    next.recommendation_key = 'workbench.alert.manualOverrideHint'
  } else {
    const qcEval = evaluateQcRecommendation(snapshot?.qc_state || {})
    next.warning_key = qcEval.warning_key
    next.recommendation_key = qcEval.recommendation_key
  }

  return next
}

export default reduceSchedulerState

