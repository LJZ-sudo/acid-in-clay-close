/**
 * EventStreamCompact — last-N raw SSE events, rendered as a tight one-liner each.
 * Replaces the legacy infinite TerminalLog: at most 10 rows visible, scrolling
 * is for the in-page detail not the entire history.
 */
const TYPE_TONE = {
  MEASUREMENT_COMPLETED: 'text-emerald-700',
  ARRHENIUS_UPDATED: 'text-indigo-700',
  PHASE_TRANSITION_DETECTED: 'text-amber-700',
  HARDWARE_CONNECTED: 'text-blue-700',
  HARDWARE_DISCONNECTED: 'text-red-700',
  EXPERIMENT_STARTED: 'text-blue-700',
  EXPERIMENT_STOPPED: 'text-gray-700',
  EXPERIMENT_COMPLETED: 'text-emerald-800 font-semibold',
  STREAM_END: 'text-gray-500',
}

function fmtTs(ts) {
  if (!ts) return ''
  const d = typeof ts === 'number' ? new Date(ts * (ts < 1e12 ? 1000 : 1)) : new Date(ts)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString()
}

function summarizePayload(type, payload) {
  if (!payload || typeof payload !== 'object') return ''
  switch (type) {
    case 'MEASUREMENT_COMPLETED': {
      const tC = payload.temperature_C
      const sigma = payload.conductivity_S_cm
      return `T=${tC != null ? Number(tC).toFixed(1) : '?'}°C  σ=${
        sigma != null ? Number(sigma).toExponential(2) : '?'
      }`
    }
    case 'PHASE_TRANSITION_DETECTED':
      return `T~${payload.temperature_C ?? '?'}°C${
        payload.confidence != null ? ` (conf ${Number(payload.confidence).toFixed(2)})` : ''
      }`
    case 'SET_T':
      return `target=${payload.target ?? payload.temperature_C ?? '?'}`
    case 'WAIT_STABLE':
      return `tol=${payload.tolerance ?? '?'}`
    case 'EXPERIMENT_COMPLETED':
      return `sample=${payload.sample_id ?? '?'}`
    default:
      return ''
  }
}

function EventStreamCompact({ events = [], limit = 10 }) {
  const tail = events.slice(-limit).reverse()
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="text-xs font-semibold text-gray-700 mb-2">Event stream (last {limit})</div>
      {tail.length === 0 ? (
        <div className="text-xs text-gray-400">No events yet — waiting for SSE.</div>
      ) : (
        <ul className="space-y-1 text-[11px] font-mono">
          {tail.map((e, i) => (
            <li key={`${e.ts}-${i}`} className="flex items-baseline gap-2">
              <span className="text-gray-400 w-16 shrink-0">{fmtTs(e.ts)}</span>
              <span className={`w-44 shrink-0 ${TYPE_TONE[e.type] || 'text-gray-700'}`}>{e.type}</span>
              <span className="text-gray-600 truncate">{summarizePayload(e.type, e.payload)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default EventStreamCompact
