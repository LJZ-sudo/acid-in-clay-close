import { AGENT_EVENT_TYPES } from '../utils/constants'

/**
 * SSE service — streaming event subscriptions
 */
class SSEService {
  constructor() {
    this.sources = new Map() // All EventSource instances
    this.reconnectTimers = new Map()
  }

  /**
   * Subscribe to main Agent thought-chain stream
   * @param {string} runId - Run ID
   * @param {Object} callbacks - Callback bundle
   * @param {Function} callbacks.onEvent - Event callback
   * @param {Function} callbacks.onError - Error callback
   * @param {Function} callbacks.onOpen - Connection open callback
   * @returns {string} Subscription key
   */
  subscribeMainAgent(runId, callbacks = {}) {
    const key = `main-agent-${runId}`
    const url = `/api/agent/stream?run_id=${encodeURIComponent(runId)}`
    return this._subscribe(key, url, callbacks)
  }

  /**
   * Subscribe to autonomous decision stream
   * @param {string} runId - Run ID
   * @param {Object} callbacks - Callback bundle
   * @returns {string} Subscription key
   */
  subscribeAutonomous(runId, callbacks = {}) {
    const key = `autonomous-${runId}`
    const url = `/api/agent/autonomous/stream?run_id=${encodeURIComponent(runId)}`
    return this._subscribe(key, url, callbacks)
  }

  /**
   * Generic subscribe helper
   * @param {string} key - Subscription key
   * @param {string} url - SSE endpoint
   * @param {Object} callbacks - Callbacks
   * @returns {string} Subscription key
   */
  _subscribe(key, url, callbacks = {}) {
    // Close existing subscription for this key first
    this.unsubscribe(key)

    const source = new EventSource(url)
    this.sources.set(key, source)

    source.onopen = () => {
      console.log(`SSE connected: ${key}`)
      callbacks.onOpen?.()
    }

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        this._handleEvent(data, callbacks)
      } catch (e) {
        console.error('Parse SSE event error:', e, event.data)
      }
    }

    source.onerror = (error) => {
      console.error(`SSE error (${key}):`, error)
      callbacks.onError?.(error)

      // Auto-reconnect
      if (source.readyState === EventSource.CLOSED) {
        this._scheduleReconnect(key, url, callbacks)
      }
    }

    return key
  }

  /**
   * Handle SSE event payload
   * @param {Object} data - Event data
   * @param {Object} callbacks - Callbacks
   */
  _handleEvent(data, callbacks) {
    const { type, ...rest } = data

    // Generic event callback
    callbacks.onEvent?.(data)

    // Type-specific callbacks
    switch (type) {
      case AGENT_EVENT_TYPES.PLAN:
        callbacks.onPlan?.(rest)
        break
      case AGENT_EVENT_TYPES.TRIGGER:
        callbacks.onTrigger?.(rest)
        break
      case AGENT_EVENT_TYPES.ACTION:
        callbacks.onAction?.(rest)
        break
      case AGENT_EVENT_TYPES.AGENT_CALL:
        callbacks.onAgentCall?.(rest)
        break
      case AGENT_EVENT_TYPES.CRITIC:
        callbacks.onCritic?.(rest)
        break
      case AGENT_EVENT_TYPES.PLANNER:
        callbacks.onPlanner?.(rest)
        break
      case AGENT_EVENT_TYPES.ERROR:
        callbacks.onAgentError?.(rest)
        break
      case AGENT_EVENT_TYPES.COMPLETE:
        callbacks.onComplete?.(rest)
        break
    }
  }

  /**
   * Schedule reconnect
   * @param {string} key - Subscription key
   * @param {string} url - SSE endpoint
   * @param {Object} callbacks - Callbacks
   */
  _scheduleReconnect(key, url, callbacks) {
    if (this.reconnectTimers.has(key)) {
      clearTimeout(this.reconnectTimers.get(key))
    }

    const timer = setTimeout(() => {
      console.log(`SSE reconnecting: ${key}`)
      this._subscribe(key, url, callbacks)
    }, 3000)

    this.reconnectTimers.set(key, timer)
  }

  /**
   * Unsubscribe
   * @param {string} key - Subscription key
   */
  unsubscribe(key) {
    const source = this.sources.get(key)
    if (source) {
      source.close()
      this.sources.delete(key)
    }

    const timer = this.reconnectTimers.get(key)
    if (timer) {
      clearTimeout(timer)
      this.reconnectTimers.delete(key)
    }
  }

  /**
   * Close all subscriptions
   */
  closeAll() {
    this.sources.forEach((source, key) => {
      source.close()
    })
    this.sources.clear()

    this.reconnectTimers.forEach((timer) => {
      clearTimeout(timer)
    })
    this.reconnectTimers.clear()
  }

  /**
   * Whether subscription is open
   * @param {string} key - Subscription key
   * @returns {boolean}
   */
  isSubscribed(key) {
    const source = this.sources.get(key)
    return source && source.readyState === EventSource.OPEN
  }
}

export const sseService = new SSEService()
export default sseService
