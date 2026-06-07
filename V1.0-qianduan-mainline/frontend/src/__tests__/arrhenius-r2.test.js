import test from 'node:test'
import assert from 'node:assert/strict'
import useArrheniusRunStore from '../stores/arrheniusRunStore.js'

test('QC event keeps r2 as null when backend does not compute it', () => {
  useArrheniusRunStore.getState().reset()
  useArrheniusRunStore.getState().applyEvent({
    run_id: 'RUN-X',
    seq: 1,
    ts: '2026-01-01T00:00:00Z',
    type: 'QC_GRADE',
    payload: { r_squared: null, qc_grade: 'C' },
  })

  const state = useArrheniusRunStore.getState()
  assert.equal(state.qcLatest.r2, null)
  assert.equal(state.qcLatest.qc_grade, 'C')
})

test('QC event stores numeric r2 without fallback coercion', () => {
  useArrheniusRunStore.getState().reset()
  useArrheniusRunStore.getState().applyEvent({
    run_id: 'RUN-X',
    seq: 2,
    ts: '2026-01-01T00:00:01Z',
    type: 'QC_GRADE',
    payload: { r_squared: 0.9567, qc_grade: 'B' },
  })

  const state = useArrheniusRunStore.getState()
  assert.equal(state.qcLatest.r2, 0.9567)
  assert.notEqual(state.qcLatest.r2, 0)
})
