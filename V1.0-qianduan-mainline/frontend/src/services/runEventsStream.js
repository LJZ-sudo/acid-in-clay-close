let clientPromise = null

function getClient() {
  if (!clientPromise) {
    clientPromise = import('../api/client.js').then((module) => module.default)
  }
  return clientPromise
}

function encodeRunId(runId) {
  return encodeURIComponent(String(runId || '').trim())
}

function buildWsUrl(path) {
  if (typeof window === 'undefined') return ''
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path}`
}

export function createRunEventStream({
  runId,
  since = 0,
  onEvent,
  onStatus,
  onError,
  preferWebSocket = false,
  pollIntervalMs = 1500,
  clientOverride = null,
}) {
  const rid = encodeRunId(runId)
  let stopped = false
  let transport = 'idle'
  let ws = null
  let es = null
  let pollTimer = null
  let reconnectTimer = null
  let reconnectAttempts = 0
  let lastSeq = Number(since || 0)
  const seenKeys = new Set()

  const updateStatus = (status, extra = {}) => {
    onStatus?.({ status, transport, lastSeq, ...extra })
  }

  const eventKey = (evt) => {
    const type = String(evt.type || evt.event_type || '').toUpperCase()
    const seq = Number(evt.seq ?? evt.step_idx ?? 0)
    const evidence = String(evt.evidence_id || evt?.payload?.evidence_id || '')
    return `${evt.run_id || runId}:${seq}:${type}:${evidence}`
  }

  const handleIncomingEvent = (evt) => {
    if (!evt || typeof evt !== 'object') return
    const key = eventKey(evt)
    if (seenKeys.has(key)) return

    seenKeys.add(key)
    if (seenKeys.size > 24000) {
      const keep = Array.from(seenKeys).slice(-10000)
      seenKeys.clear()
      keep.forEach((row) => seenKeys.add(row))
    }

    const seq = Number(evt.seq ?? evt.step_idx ?? 0)
    if (Number.isFinite(seq) && seq > lastSeq) {
      lastSeq = seq
    }

    onEvent?.(evt)
  }

  const stopPolling = () => {
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  const stopReconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  const schedulePoll = () => {
    if (stopped) return
    stopPolling()
    pollTimer = setTimeout(pollOnce, pollIntervalMs)
  }

  const pollOnce = async () => {
    if (stopped) return

    transport = 'poll'
    updateStatus('connected')

    try {
      const urls = [
        `/runs/${rid}/events`,
        `/v1/runs/${rid}/events`,
      ]

      let response = null
      let lastError = null
      const client = clientOverride || await getClient()

      for (const path of urls) {
        try {
          response = await client.get(path, {
            params: {
              since: lastSeq,
              last_seq: lastSeq,
              limit: 500,
            },
          })
          break
        } catch (error) {
          lastError = error
          if (Number(error?.response?.status) !== 404) {
            throw error
          }
        }
      }

      if (!response && lastError) {
        throw lastError
      }

      const rows = response?.data?.items || response?.data?.events || []
      if (Array.isArray(rows)) {
        rows.forEach(handleIncomingEvent)
      }

      schedulePoll()
    } catch (error) {
      onError?.(error)
      updateStatus('error', { error })
      schedulePoll()
    }
  }

  const fallbackToPolling = (reason) => {
    if (stopped) return
    if (ws) {
      ws.close()
      ws = null
    }
    if (es) {
      es.close()
      es = null
    }
    transport = 'poll'
    updateStatus('fallback', { reason })
    pollOnce()
  }

  const connectSse = () => {
    if (stopped) return
    if (typeof EventSource === 'undefined') {
      fallbackToPolling('sse_unavailable')
      return
    }

    const params = new URLSearchParams({
      since: String(lastSeq),
      last_seq: String(lastSeq),
    })
    const sseUrl = `/api/runs/${rid}/events/stream?${params.toString()}`
    transport = 'sse'
    updateStatus('connecting')

    es = new EventSource(sseUrl)

    es.onopen = () => {
      reconnectAttempts = 0
      updateStatus('connected')
    }

    es.onmessage = (message) => {
      try {
        const data = JSON.parse(message.data)
        if (data?.type === 'STREAM_END') {
          stopped = true
          stopReconnect()
          stopPolling()
          if (es) {
            es.close()
            es = null
          }
          updateStatus('ended')
          return
        }
        if (Array.isArray(data?.events)) {
          data.events.forEach(handleIncomingEvent)
          return
        }
        handleIncomingEvent(data)
      } catch (error) {
        onError?.(error)
      }
    }

    es.onerror = (error) => {
      onError?.(error)
      fallbackToPolling('sse_error')
    }
  }

  const connectWebSocket = () => {
    if (stopped) return

    const wsUrl = buildWsUrl(`/api/runs/ws/${rid}?since=${encodeURIComponent(String(lastSeq))}`)
    if (!wsUrl || typeof WebSocket === 'undefined') {
      fallbackToPolling('ws_unavailable')
      return
    }

    transport = 'ws'
    updateStatus('connecting')

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      reconnectAttempts = 0
      updateStatus('connected')
    }

    ws.onmessage = (message) => {
      try {
        const data = JSON.parse(message.data)
        if (Array.isArray(data?.events)) {
          data.events.forEach(handleIncomingEvent)
          return
        }
        handleIncomingEvent(data)
      } catch (error) {
        onError?.(error)
      }
    }

    ws.onerror = (error) => {
      onError?.(error)
    }

    ws.onclose = () => {
      if (stopped) return
      reconnectAttempts += 1

      if (reconnectAttempts <= 3) {
        stopReconnect()
        reconnectTimer = setTimeout(connectWebSocket, Math.min(1000 * reconnectAttempts, 3000))
        return
      }

      fallbackToPolling('ws_closed')
    }
  }

  if (preferWebSocket) {
    connectWebSocket()
  } else {
    connectSse()
  }

  return {
    getLastSeq() {
      return lastSeq
    },
    stop() {
      stopped = true
      stopReconnect()
      stopPolling()
      if (ws) {
        ws.close()
        ws = null
      }
      if (es) {
        es.close()
        es = null
      }
      updateStatus('disconnected')
    },
  }
}

export default createRunEventStream
