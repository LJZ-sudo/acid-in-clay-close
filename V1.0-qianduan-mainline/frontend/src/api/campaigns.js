import client from './client'

/**
 * Thin wrapper around backend_api/routers/campaigns.py.
 * Each method maps 1:1 to a route — keep it that way; the dashboard's value
 * comes from faithfully exposing the on-disk Stage1 evidence.
 */
export const campaignsApi = {
  list: () => client.get('/campaigns'),
  getMeta: (slug) => client.get(`/campaigns/${encodeURIComponent(slug)}`),
  getTrials: (slug) => client.get(`/campaigns/${encodeURIComponent(slug)}/trials`),
  getNextRecipe: (slug) => client.get(`/campaigns/${encodeURIComponent(slug)}/next-recipe`),
  getHealth: (slug) => client.get(`/campaigns/${encodeURIComponent(slug)}/health`),
  /** Stage1 BO readiness: 返回去重配方数 vs 冷启动阈值，告诉 UI 当前能否走 GP+EI */
  getStage1Readiness: (slug, params = {}) =>
    client.get(`/campaigns/${encodeURIComponent(slug)}/stage1-readiness`, { params }),
  /** Termination v3 评估：A/B/C/D 四象限触发情况，前端"闭环终止条件"面板用 */
  getTermination: (slug) =>
    client.get(`/campaigns/${encodeURIComponent(slug)}/termination`),
}

export default campaignsApi
