import client from './client'

export const samplesApi = {
  list: (params = {}) => client.get('/samples', { params }),
  /** 将 CHI 短名解析为 Stage0 canonical sample_id（可选，用于调试） */
  resolve: (sampleId) => client.get(`/samples/resolve/${encodeURIComponent(sampleId)}`),
  get: (sampleId) => client.get(`/samples/${encodeURIComponent(sampleId)}`),
  getBundle: (sampleId) => client.get(`/samples/${encodeURIComponent(sampleId)}/bundle`),
  getClosureReport: (sampleId) => client.get(`/samples/${encodeURIComponent(sampleId)}/closure-report`),
  /** 已落盘样品的原始 EIS 频谱（每个温度一条 Nyquist）。t_c 可选：只取最接近该温度的一条。 */
  getEisSpectra: (sampleId, t_c) =>
    client.get(`/samples/${encodeURIComponent(sampleId)}/eis-spectra`, { params: t_c != null ? { t_c } : {} }),
  generateClosureReport: (sampleId, payload = {}) =>
    client.post(`/samples/${encodeURIComponent(sampleId)}/closure-report`, payload),
}

export default samplesApi
