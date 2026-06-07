import client from './client'
import { API_BASE_URL } from '../utils/constants'

const enc = (v) => encodeURIComponent(String(v || '').trim())

const buildDownloadUrl = (path) => `${API_BASE_URL}${path}`

export const runsAuditApi = {
  listRuns() {
    return client.get('/runs')
  },

  createRun(payload = {}) {
    return client.post('/runs', payload)
  },

  getRun(runId) {
    return client.get(`/runs/${enc(runId)}`)
  },

  getManifest(runId) {
    return client.get(`/runs/${enc(runId)}/manifest`)
  },

  getEvents(runId) {
    return client.get(`/runs/${enc(runId)}/events`)
  },

  getEventsStreamUrl(runId, params = {}) {
    const q = new URLSearchParams()
    if (params.from_step !== undefined) q.set('from_step', String(params.from_step))
    if (params.replay_speed !== undefined) q.set('replay_speed', String(params.replay_speed))
    const suffix = q.toString() ? `?${q.toString()}` : ''
    return buildDownloadUrl(`/runs/${enc(runId)}/events/stream${suffix}`)
  },

  downloadEventsUrl(runId) {
    return buildDownloadUrl(`/runs/${enc(runId)}/events?download=1`)
  },

  downloadManifestUrl(runId) {
    return buildDownloadUrl(`/runs/${enc(runId)}/manifest?download=1`)
  },

  listEvidence(runId) {
    return client.get(`/runs/${enc(runId)}/evidence`)
  },

  getEvidence(evidenceId) {
    return client.get(`/evidence/${enc(evidenceId)}`)
  },

  downloadEvidenceUrl(evidenceId) {
    return buildDownloadUrl(`/evidence/${enc(evidenceId)}?download=1`)
  },

  replayRun(runId, payload = {}) {
    return client.post(`/runs/${enc(runId)}/replay`, payload)
  },

  getBaselineEquivalence(runId, format = 'json') {
    return client.get(`/runs/${enc(runId)}/baseline-equivalence`, {
      params: { format },
      responseType: format === 'csv' ? 'text' : 'json',
    })
  },

  downloadBaselineEquivalenceUrl(runId) {
    return buildDownloadUrl(`/runs/${enc(runId)}/baseline-equivalence?format=csv`)
  },

  thresholdSweep(payload = {}) {
    return client.post('/jobs/threshold_sweep', payload)
  },

  ablation(payload = {}) {
    return client.post('/jobs/ablation', payload)
  },

  reportScores(payload = {}) {
    return client.post('/jobs/report_scores', payload)
  },

  downloadReportUrl(filePath) {
    const q = new URLSearchParams({ file: String(filePath || '') })
    return buildDownloadUrl(`/reports/download?${q.toString()}`)
  },
}

export default runsAuditApi
