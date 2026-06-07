import client from './client'

/**
 * Autonomous decision API — thinking sessions and automatic decisions
 */
export const autonomousApi = {
  /**
   * Start a thinking session
   * @param {Object} params
   * @param {string} params.run_id - Run ID
   * @param {Object} params.state - Current state
   * @param {Object} params.evidence - Evidence data
   * @param {number} params.timeout_seconds - Timeout (seconds)
   */
  startThinking(params) {
    return client.post('/agent/autonomous/start-thinking', params)
  },

  /**
   * Get session status
   * @param {string} sessionId - Session ID
   */
  getSessionStatus(sessionId) {
    return client.get(`/agent/autonomous/session/${sessionId}/status`)
  },

  /**
   * Get session event list
   * @param {string} sessionId - Session ID
   */
  getSessionEvents(sessionId) {
    return client.get(`/agent/autonomous/session/${sessionId}/events`)
  },

  /**
   * Stop thinking session
   * @param {string} sessionId - Session ID
   */
  stopSession(sessionId) {
    return client.post(`/agent/autonomous/session/${sessionId}/stop`)
  },

  /**
   * Automatic decision (call after measurement completes)
   * @param {Object} params - Decision parameters
   */
  autoDecision(params = {}) {
    return client.post('/agent/autonomous/auto-decision', params)
  },

  /**
   * Start autonomous decision mode (switch backend adapter via control API)
   * @param {Object} params - Parameters
   * @param {string} params.run_id - Run ID
   */
  startAutoDecision(params = {}) {
    return client.post('/control/autonomous/start', params)
  },

  /**
   * Stop autonomous decision mode
   */
  stopAutoDecision() {
    return client.post('/control/autonomous/stop')
  },
}

/**
 * Subscribe to autonomous decision stream events (includes Critic and Planner output)
 * @param {string} runId - Run ID
 * @param {Function} onEvent - Event callback
 * @param {Function} onError - Error callback
 * @returns {Function} Unsubscribe function
 */
export function subscribeToAutonomousStream(runId, onEvent, onError) {
  const url = `/api/agent/autonomous/stream?run_id=${encodeURIComponent(runId)}`
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
    console.error('Autonomous SSE connection error:', error)
    if (onError) onError(error)
  }

  return () => {
    source.close()
  }
}
