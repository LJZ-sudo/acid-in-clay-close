import client from './client'

/**
 * Control API — device connection and experiment control
 */
export const controlApi = {
  /**
   * Connect device
   * @param {Object} params - Connection parameters
   * @param {string} params.port - Serial port
   * @param {number} params.T_start - Start temperature
   * @param {number} params.T_end - End temperature
   * @param {number} params.coarse_step - Coarse scan step
   * @param {number} params.fine_step - Fine scan step
   * @param {boolean} params.simulate - Simulation mode
   */
  connect(params) {
    return client.post('/control/connect', params)
  },

  /**
   * Disconnect device
   */
  disconnect() {
    return client.post('/control/disconnect')
  },

  /**
   * Get system status
   */
  getStatus() {
    return client.get('/control/status')
  },

  /**
   * Start experiment
   * @param {Object} params - Start parameters
   */
  start(params = {}) {
    return client.post('/control/start', params)
  },

  /**
   * Manually run Stage0 (+ optional Stage1) after a run, e.g. cold start then BO.
   */
  postprocess(params = {}) {
    return client.post('/control/postprocess', params)
  },

  /**
   * Pause experiment
   */
  pause() {
    return client.post('/control/pause')
  },

  /**
   * Resume experiment
   */
  resume() {
    return client.post('/control/resume')
  },

  /**
   * Stop experiment
   */
  stop() {
    return client.post('/control/stop')
  },

  /**
   * Get current temperature
   */
  getTemperature() {
    return client.get('/control/temperature')
  },

  /**
   * Set target temperature
   * @param {number} temperature - Target temperature
   */
  setTemperature(temperature) {
    return client.post('/control/temperature', { temperature })
  },

  /**
   * Run one EIS measurement at current stable temperature
   * @param {Object} params - Optional run context
   */
  measureNow(params = {}) {
    return client.post('/control/measure', params)
  },

  /**
   * Apply measurement policy (fine scan / rollback / measure now)
   * @param {Object} params - Policy payload
   */
  applyMeasurementPolicy(params = {}) {
    return client.post('/control/measurement-policy', params)
  },

  /**
   * Enable autonomous decision mode
   */
  startAutonomous(params = {}) {
    return client.post('/control/autonomous/start', params)
  },

  /**
   * Disable autonomous decision mode
   */
  stopAutonomous() {
    return client.post('/control/autonomous/stop')
  },

  /**
   * Get autonomous decision status
   */
  getAutonomousStatus() {
    return client.get('/control/autonomous/status')
  },
}
