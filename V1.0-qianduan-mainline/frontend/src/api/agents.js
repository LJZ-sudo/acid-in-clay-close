import client from './client'

/**
 * Multi-Agent API — agent status and evaluation
 */
export const agentsApi = {
  /**
   * Get status for all agents
   */
  getStatus() {
    return client.get('/agents/status')
  },

  /**
   * Get agent capability descriptions
   */
  getCapabilities() {
    return client.get('/agents/capabilities')
  },

  /**
   * Agent system health check
   */
  healthCheck() {
    return client.get('/agents/health')
  },

  /**
   * Get message log
   * @param {Object} params
   * @param {number} params.limit - Max rows
   * @param {string} params.type - Message type
   * @param {string} params.sender - Sender
   * @param {string} params.receiver - Receiver
   */
  getMessages(params = {}) {
    return client.get('/agents/messages', { params })
  },

  /**
   * Invoke CriticAgent evaluation
   * @param {Object} params
   * @param {string} params.type - Evaluation type (measurement/decision/result/improvement)
   * @param {Object} params.data - Payload to evaluate
   */
  evaluate(params) {
    return client.post('/agents/evaluate', params)
  },

  /**
   * Get message bus statistics
   */
  getStats() {
    return client.get('/agents/stats')
  },
}
