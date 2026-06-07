import client from './client'

/**
 * Data API — measurements and analysis results
 */
export const dataApi = {
  /**
   * Get measurement history
   * @param {Object} params
   * @param {number} params.limit - Max rows
   * @param {number} params.offset - Offset
   */
  getMeasurements(params = {}) {
    return client.get('/data/measurements', { params })
  },

  /**
   * Get current EIS data
   */
  getCurrentEIS() {
    return client.get('/data/current_eis')
  },

  /**
   * Get EIS data for a measurement index
   * @param {number} index - Measurement index
   */
  getEISByIndex(index) {
    return client.get(`/data/measurements/${index}/eis`)
  },

  /**
   * Get phase transition data
   */
  getPhaseTransitions() {
    return client.get('/data/phase_transitions')
  },

  /**
   * Get Arrhenius analysis results
   */
  getArrhenius() {
    return client.get('/data/arrhenius')
  },

  /**
   * Get realtime Arrhenius data
   */
  getArrheniusRealtime() {
    return client.get('/data/arrhenius/realtime')
  },

  /**
   * Get experiment report
   * @param {string} expId - Experiment ID (optional)
   * @param {string} language - Locale (zh-CN / en-US)
   */
  getReport(expId = null, language = 'zh-CN') {
    const url = expId ? `/data/report/${expId}` : '/data/report'
    return client.get(url, { params: { language } })
  },

  /**
   * Get experiment list
   */
  getExperiments() {
    return client.get('/data/experiments')
  },

  /**
   * Get experiment history
   */
  getHistory() {
    return client.get('/data/history')
  },

  /**
   * Get experiment detail
   * @param {string} expId - Experiment ID
   */
  getExperiment(expId) {
    return client.get(`/data/experiment/${expId}`)
  },

  /**
   * Get next experiment plan and approval status
   * @param {string|null} expId - Experiment ID; omit to use current
   */
  getNextPlan(expId = null) {
    const url = expId ? `/data/next-plan/${expId}` : '/data/next-plan'
    return client.get(url)
  },

  /**
   * Submit human decision for next experiment plan
   * @param {Object} payload - {decision, notes, selected_window_index, selected_action_indices, execution_preference}
   * @param {string|null} expId - Experiment ID; omit to apply to current
   */
  decideNextPlan(payload = {}, expId = null) {
    const url = expId ? `/data/next-plan/${expId}/decision` : '/data/next-plan/decision'
    return client.post(url, payload)
  },

  /**
   * Apply approved next-plan suggestion for current experiment
   * @param {string|null} expId - Experiment ID; only current/latest/now may execute
   */
  applyApprovedNextPlan(expId = null) {
    const url = expId ? `/data/next-plan/${expId}/apply` : '/data/next-plan/apply'
    return client.post(url)
  },

  /**
   * Get saved next experiment plan for a sample
   * @param {string} sampleId
   */
  getSavedNextPlan(sampleId) {
    return client.get(`/data/next-plan/saved/${sampleId}`)
  },

  /**
   * Archive current experiment
   */
  archiveExperiment() {
    return client.post('/data/archive')
  },
}
