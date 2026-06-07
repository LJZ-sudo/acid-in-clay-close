import { useEffect, useRef, useState } from 'react'
import { wsService } from '../services/websocket'
import { WS_EVENTS } from '../utils/constants'

/**
 * Normalize backend thought_chain_event payloads (type + sample_id may be top-level or under payload).
 */
export function parseThoughtChainEvent(data) {
  if (!data || typeof data !== 'object') return { type: '', sampleId: null, payload: {} }
  const type = String(data.event_type || data.type || '').toUpperCase()
  const pl = data.payload && typeof data.payload === 'object' ? data.payload : {}
  const sampleId = data.sample_id ?? pl.sample_id ?? null
  return { type, sampleId, payload: pl, raw: data }
}

/** Refresh when the event is global (no sample_id) or matches the focused sample. */
function eventAppliesToSample(evSid, targetSid) {
  if (!targetSid) return false
  if (!evSid) return true
  return evSid === targetSid
}

/**
 * Refetch callbacks when post-processing / closure finishes (WebSocket).
 * - onRefreshSampleList: e.g. reload /samples table & dropdown
 * - onRefreshThisSample: e.g. reload GET /samples/:id when event concerns this sample
 */
export function useThoughtChainRefetch(sampleId, { onRefreshThisSample, onRefreshSampleList } = {}) {
  const sidRef = useRef(sampleId)
  sidRef.current = sampleId

  const sampleCb = useRef(onRefreshThisSample)
  sampleCb.current = onRefreshThisSample
  const listCb = useRef(onRefreshSampleList)
  listCb.current = onRefreshSampleList

  useEffect(() => {
    const handler = (data) => {
      const { type, sampleId: evSid } = parseThoughtChainEvent(data)

      if (listCb.current) {
        if (
          type === 'POST_PROCESSING_COMPLETED'
          || type === 'POST_PROCESSING_FAILED'
          || type === 'CLOSURE_REPORT_COMPLETED'
        ) {
          listCb.current()
        }
      }

      if (sampleCb.current) {
        const target = sidRef.current
        if (!target) return
        if (!eventAppliesToSample(evSid, target)) return
        if (
          type === 'POST_PROCESSING_COMPLETED'
          || type === 'CLOSURE_REPORT_COMPLETED'
          || type === 'CLOSURE_REPORT_FAILED'
        ) {
          sampleCb.current()
        }
      }
    }
    return wsService.on(WS_EVENTS.THOUGHT_CHAIN_EVENT, handler)
  }, [])
}

/**
 * True while post-processing or closure generation is in flight for the given sample_id.
 */
export function useClosureOrPostProcessPending(sampleId) {
  const [pending, setPending] = useState(false)
  const sidRef = useRef(sampleId)
  sidRef.current = sampleId

  useEffect(() => {
    setPending(false)
  }, [sampleId])

  useEffect(() => {
    const handler = (data) => {
      const { type, sampleId: evSid } = parseThoughtChainEvent(data)
      const target = sidRef.current
      if (!target) return

      if (type === 'POST_PROCESSING_STARTED') {
        if (!evSid || evSid === target) setPending(true)
      }
      if (type === 'CLOSURE_REPORT_STARTED') {
        if (evSid && evSid === target) setPending(true)
      }
      if (
        type === 'CLOSURE_REPORT_COMPLETED'
        || type === 'CLOSURE_REPORT_FAILED'
        || type === 'POST_PROCESSING_COMPLETED'
        || type === 'POST_PROCESSING_FAILED'
      ) {
        if (!evSid || evSid === target) setPending(false)
      }
    }
    return wsService.on(WS_EVENTS.THOUGHT_CHAIN_EVENT, handler)
  }, [sampleId])

  return pending
}
