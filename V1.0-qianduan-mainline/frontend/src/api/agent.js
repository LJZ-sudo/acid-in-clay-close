import client from './client'

/**
 * Agent API — read-only status/config for the main decision agent.
 * `config` carries the live LLM provider/model so the UI never hard-codes it.
 */
export const agentApi = {
  getStatus: () => client.get('/agent/status'),
}

export default agentApi
