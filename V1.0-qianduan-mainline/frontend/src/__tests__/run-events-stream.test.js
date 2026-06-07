import test from 'node:test'
import assert from 'node:assert/strict'
import { createRunEventStream } from '../services/runEventsStream.js'

test('run event stream defaults to SSE endpoint', () => {
  const originalEventSource = globalThis.EventSource
  const originalWebSocket = globalThis.WebSocket
  const urls = []

  globalThis.EventSource = class FakeEventSource {
    constructor(url) {
      this.url = url
      urls.push(url)
    }
    close() {
      this.closed = true
    }
  }
  delete globalThis.WebSocket

  const stream = createRunEventStream({
    runId: 'RUN 1',
    onEvent() {},
  })

  assert.equal(urls.length, 1)
  assert.equal(urls[0], '/api/runs/RUN%201/events/stream?since=0&last_seq=0')
  assert.equal(urls[0].includes('/ws/runs/'), false)

  stream.stop()
  globalThis.EventSource = originalEventSource
  globalThis.WebSocket = originalWebSocket
})

test('run event stream websocket opt-in uses backend router path', () => {
  const originalWindow = globalThis.window
  const originalWebSocket = globalThis.WebSocket
  const originalEventSource = globalThis.EventSource
  const urls = []

  globalThis.window = { location: { protocol: 'http:', host: 'localhost:5173' } }
  globalThis.WebSocket = class FakeWebSocket {
    constructor(url) {
      this.url = url
      urls.push(url)
    }
    close() {
      this.closed = true
    }
  }
  globalThis.EventSource = undefined

  const stream = createRunEventStream({
    runId: 'RUN-2',
    preferWebSocket: true,
    onEvent() {},
  })

  assert.equal(urls.length, 1)
  assert.equal(urls[0], 'ws://localhost:5173/api/runs/ws/RUN-2?since=0')

  stream.stop()
  globalThis.window = originalWindow
  globalThis.WebSocket = originalWebSocket
  globalThis.EventSource = originalEventSource
})

test('run event stream falls back to REST polling with cursor params', async () => {
  const originalEventSource = globalThis.EventSource
  const originalWebSocket = globalThis.WebSocket
  const requests = []
  const events = []

  globalThis.EventSource = undefined
  delete globalThis.WebSocket

  const stream = createRunEventStream({
    runId: 'RUN-3',
    since: 5,
    pollIntervalMs: 10000,
    clientOverride: {
      async get(path, options) {
        requests.push({ path, options })
        return { data: { events: [{ run_id: 'RUN-3', seq: 6, type: 'QC_GRADED' }] } }
      },
    },
    onEvent(evt) {
      events.push(evt)
    },
  })

  await new Promise((resolve) => setTimeout(resolve, 0))

  assert.equal(requests[0].path, '/runs/RUN-3/events')
  assert.equal(requests[0].options.params.since, 5)
  assert.equal(requests[0].options.params.last_seq, 5)
  assert.equal(events.length, 1)
  assert.equal(stream.getLastSeq(), 6)

  stream.stop()
  globalThis.EventSource = originalEventSource
  globalThis.WebSocket = originalWebSocket
})
