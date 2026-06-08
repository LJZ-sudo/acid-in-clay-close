import client from './client'

/**
 * Provenance API — read-only tamper-evidence anchors.
 * Returns { git, llm, preregistration }. Pure display; no analysis logic.
 */
export const provenanceApi = {
  get: () => client.get('/provenance'),
}

export default provenanceApi
