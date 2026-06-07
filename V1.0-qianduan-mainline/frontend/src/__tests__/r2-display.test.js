import test from 'node:test'
import assert from 'node:assert/strict'
import { formatR2OrNA } from '../features/runEvents/qcDisplay.js'

test('formatR2OrNA returns N/A for null/undefined', () => {
  assert.equal(formatR2OrNA(null), 'N/A')
  assert.equal(formatR2OrNA(undefined), 'N/A')
})

test('formatR2OrNA keeps numeric values', () => {
  const formatted = formatR2OrNA(0.95678)
  assert.notEqual(formatted, 'N/A')
  assert.match(formatted, /0\.95|0,95/)
})
