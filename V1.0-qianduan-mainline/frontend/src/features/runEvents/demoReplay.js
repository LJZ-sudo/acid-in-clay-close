import { normalizeWorkbenchEvent } from './eventModel.js'
import { runEventsReducer } from './reducer.js'

export function parseJsonlEvents(text = '', options = {}) {
  const lines = String(text || '').split(/\r?\n/)
  const fallbackRunId = String(options.fallbackRunId || '')
  const events = []
  const errors = []

  lines.forEach((line, index) => {
    const raw = String(line || '').trim()
    if (!raw) return
    try {
      const parsed = JSON.parse(raw)
      const evt = normalizeWorkbenchEvent(parsed, fallbackRunId)
      if (!evt?.type) {
        errors.push({ line: index + 1, reason: 'missing_type' })
        return
      }
      events.push(evt)
    } catch {
      errors.push({ line: index + 1, reason: 'invalid_json' })
    }
  })

  events.sort((a, b) => {
    const seqA = Number(a?.seq || 0)
    const seqB = Number(b?.seq || 0)
    if (seqA !== seqB) return seqA - seqB
    return String(a?.ts || '').localeCompare(String(b?.ts || ''))
  })

  return {
    events,
    errors,
    runId: events[0]?.run_id || fallbackRunId || '',
  }
}

export function loadJsonlFile(file, options = {}) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const parsed = parseJsonlEvents(reader.result, options)
        resolve(parsed)
      } catch (error) {
        reject(error)
      }
    }
    reader.onerror = () => reject(reader.error || new Error('read_failed'))
    reader.readAsText(file)
  })
}

export function replayStep(state, event, runId = '') {
  return runEventsReducer(state, event, { run_id: runId || state?.run_id || event?.run_id || '' })
}

export default {
  parseJsonlEvents,
  loadJsonlFile,
  replayStep,
}
