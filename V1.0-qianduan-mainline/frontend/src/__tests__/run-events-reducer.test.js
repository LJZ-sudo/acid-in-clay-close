import test from 'node:test'
import assert from 'node:assert/strict'
import { runEventsReducer, initialRunEventsState } from '../features/runEvents/reducer.js'

function reduceAll(events) {
  return events.reduce((state, evt) => runEventsReducer(state, evt, { run_id: 'RUN-1' }), {
    ...initialRunEventsState,
    telemetry: { ...initialRunEventsState.telemetry },
    arrhenius_state: { ...initialRunEventsState.arrhenius_state },
    phase_state: { ...initialRunEventsState.phase_state, points: [] },
    qc_state: { ...initialRunEventsState.qc_state },
    risk_state: { ...initialRunEventsState.risk_state },
    negotiation: { ...initialRunEventsState.negotiation },
    agent_status: { ...initialRunEventsState.agent_status },
    scheduler: {
      ...initialRunEventsState.scheduler,
      nodes: Object.fromEntries(Object.entries(initialRunEventsState.scheduler?.nodes || {}).map(([k, v]) => [k, { ...v }])),
    },
    events: [],
    tool_timeline: [],
    measurement_points: [],
    evidence_index: [],
    evidence_by_id: {},
    seen_keys: {},
    agent_messages: [],
  })
}

test('run event reducer keeps r2 as null and sets QC state', () => {
  const state = reduceAll([
    { run_id: 'RUN-1', seq: 1, type: 'QC_GRADED', payload: { r2: null, qc_grade: 'C', qc_status: 'QC_UNKNOWN' } },
  ])

  assert.equal(state.qc_state.r2, null)
  assert.equal(state.qc_state.qc_grade, 'C')
  assert.equal(state.qc_state.qc_status, 'QC_UNKNOWN')
})

test('run event reducer maps planner/critic/orchestrator negotiation', () => {
  const state = reduceAll([
    { run_id: 'RUN-1', seq: 2, type: 'PLAN_PROPOSED', payload: { reason: 'dense scan near transition' } },
    { run_id: 'RUN-1', seq: 3, type: 'CRITIC_REVIEWED', payload: { comment: 'quality risk' } },
    { run_id: 'RUN-1', seq: 4, type: 'ACTION_EXECUTED', payload: { action: 'RE_MEASURE' } },
  ])

  assert.equal(state.negotiation.planner?.type, 'PLAN_PROPOSED')
  assert.equal(state.negotiation.critic?.type, 'CRITIC_REVIEWED')
  assert.equal(state.negotiation.orchestrator?.type, 'ACTION_EXECUTED')
})

test('run event reducer deduplicates same event key', () => {
  const event = { run_id: 'RUN-1', seq: 5, type: 'PHASE_SCORE_UPDATED', payload: { score: 0.31, threshold: 0.2 } }
  const state = reduceAll([event, event])

  assert.equal(state.events.length, 1)
  assert.equal(state.phase_state.points.length, 1)
})

test('scheduler reducer marks transition and qc risk states', () => {
  const state = reduceAll([
    { run_id: 'RUN-1', seq: 10, type: 'PHASE_SCORE_UPDATED', payload: { phase_jump_score: 0.31, threshold: 0.2 } },
    { run_id: 'RUN-1', seq: 11, type: 'QC_GRADED', payload: { r2: null, qc_grade: 'UNKNOWN', qc_status: 'QC_UNKNOWN', retest_recommended: true } },
  ])

  assert.equal(state.scheduler.active_node_id, 'qc_rb')
  assert.equal(state.scheduler.nodes.transition.status, 'running')
  assert.equal(state.scheduler.nodes.transition.warning_key, 'workbench.alert.transitionModeTriggered')
  assert.equal(state.scheduler.nodes.qc_rb.status, 'blocked')
  assert.equal(state.scheduler.recommendation_key, 'workbench.alert.retestScheduled')
})


test('phase score and command events drive agent highlight statuses', () => {
  const state = reduceAll([
    { run_id: 'RUN-1', seq: 1, actor: 'Planner', event_type: 'PHASE_SCORE', payload: { score: 0.25, threshold: 0.2 } },
    { run_id: 'RUN-1', seq: 2, actor: 'ControllerAdapter', event_type: 'COMMAND_SENT', payload: { command: 'EIS_RUN' } },
  ])

  assert.equal(state.agent_status.planner, 'thinking')
  assert.equal(state.agent_status.controller_adapter, 'acting')
})

test('terminal run event resets all agents to idle', () => {
  const state = reduceAll([
    { run_id: 'RUN-1', seq: 1, type: 'PLAN_PROPOSED', payload: { reason: 'test' } },
    { run_id: 'RUN-1', seq: 2, type: 'RUN_FINISHED', payload: {} },
  ])

  Object.values(state.agent_status).forEach((v) => {
    assert.equal(v, 'idle')
  })
})
