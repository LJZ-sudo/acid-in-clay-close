import test from 'node:test'
import assert from 'node:assert/strict'
import { parseJsonlEvents, replayStep } from '../features/runEvents/demoReplay.js'
import { initialRunEventsState } from '../features/runEvents/reducer.js'

test('parseJsonlEvents parses valid lines and skips invalid lines', () => {
  const text = [
    JSON.stringify({ run_id: 'RUN-X', seq: 1, type: 'RUN_CREATED', payload: {} }),
    'not-json',
    JSON.stringify({ run_id: 'RUN-X', seq: 2, type: 'PHASE_SCORE_UPDATED', payload: { phase_jump_score: 0.3, threshold: 0.2 } }),
  ].join('\n')

  const parsed = parseJsonlEvents(text)
  assert.equal(parsed.events.length, 2)
  assert.equal(parsed.errors.length, 1)
  assert.equal(parsed.runId, 'RUN-X')
})

test('replayStep derives state from events', () => {
  const init = {
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
  }

  const state = replayStep(init, {
    run_id: 'RUN-X',
    seq: 3,
    type: 'SET_T',
    payload: { step_idx: 3, target_temperature_C: 25 },
    source: 'controller_adapter',
  }, 'RUN-X')

  assert.equal(state.run_id, 'RUN-X')
  assert.equal(state.scheduler.active_node_id, 'measurement')
  assert.equal(state.scheduler.nodes.measurement.status, 'running')
})
