import client from './client'

/**
 * Main Agent API — decisions and status
 */
export const mainAgentApi = {
  /**
   * Synchronous decision request
   * @param {Object} params
   * @param {string} params.run_id - Run ID
   * @param {Object} params.state - Current state
   * @param {Object} params.evidence - Evidence data
   * @param {Array} params.history - History
   */
  decide(params) {
    return client.post('/agent/decide', params)
  },

  /**
   * Get Agent status
   */
  getStatus() {
    return client.get('/agent/status')
  },

  /**
   * Heartbeat
   */
  heartbeat() {
    return client.get('/agent/heartbeat')
  },

  /**
   * Update Agent config
   * @param {Object} config - Config payload
   */
  updateConfig(config) {
    return client.post('/agent/config', config)
  },

  /**
   * Start a new run
   * @param {Object} params - Run parameters
   */
  startRun(params = {}) {
    return client.post('/agent/start-run', params)
  },
}

/**
 * Subscribe to main Agent thought-chain stream events
 * @param {string} runId - Run ID
 * @param {Function} onEvent - Event callback
 * @param {Function} onError - Error callback
 * @returns {Function} Unsubscribe function
 */
export function subscribeToMainAgentStream(runId, onEvent, onError) {
  const url = `/api/agent/stream?run_id=${encodeURIComponent(runId)}`
  const source = new EventSource(url)

  source.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onEvent(data)
    } catch (e) {
      console.error('Parse SSE event error:', e)
    }
  }

  source.onerror = (error) => {
    console.error('SSE connection error:', error)
    if (onError) onError(error)
  }

  return () => {
    source.close()
  }
}
