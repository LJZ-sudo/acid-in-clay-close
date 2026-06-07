import { useEffect, useRef, useState } from 'react'

/**
 * useLiveRun — subscribe to a run's SSE event stream and project it into
 * a small reducer state suitable for the LiveRun cockpit.
 *
 * Event payload shape (from backend_api.services.hardware_adapter._emit_event):
 *   { type: "MEASUREMENT_COMPLETED" | "ARRHENIUS_UPDATED" | "PHASE_TRANSITION_DETECTED"
 *          | "EXPERIMENT_COMPLETED" | "SET_T" | "WAIT_STABLE" | "Rb_FIT" | "STREAM_END" | ... ,
 *     payload: {...},
 *     ts: ... ,
 *   }
 */
export default function useLiveRun(runId) {
  const [state, setState] = useState({
    measurements: [],
    transitions: [],
    arrhenius: null,
    lastSetT: null,
    finalSampleId: null,
    streamEnded: false,
    events: [],
    error: null,
    connected: false,
  })
  const sourceRef = useRef(null)

  useEffect(() => {
    if (!runId) return undefined
    const url = `/api/runs/${encodeURIComponent(runId)}/events/stream`
    const es = new EventSource(url)
    sourceRef.current = es

    es.onopen = () => setState((s) => ({ ...s, connected: true, error: null }))
    es.onerror = () => setState((s) => ({ ...s, connected: false, error: 'SSE error' }))
    es.onmessage = (ev) => {
      let data
      try {
        data = JSON.parse(ev.data)
      } catch {
        return
      }
      const type = data?.type
      const payload = data?.payload || {}
      setState((s) => {
        const next = { ...s }
        next.events = [...s.events.slice(-49), { type, payload, ts: data?.ts || Date.now() }]
        switch (type) {
          case 'MEASUREMENT_COMPLETED':
            next.measurements = [...s.measurements, payload].slice(-500)
            break
          case 'ARRHENIUS_UPDATED':
            next.arrhenius = payload
            break
          case 'PHASE_TRANSITION_DETECTED':
            next.transitions = [...s.transitions, payload].slice(-50)
            break
          case 'SET_T':
          case 'WAIT_STABLE':
            next.lastSetT = payload
            break
          case 'EXPERIMENT_COMPLETED':
            next.finalSampleId = payload?.sample_id || null
            break
          case 'STREAM_END':
            next.streamEnded = true
            break
          default:
            break
        }
        return next
      })
    }

    return () => {
      es.close()
      sourceRef.current = null
    }
  }, [runId])

  return state
}
