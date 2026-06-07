import { useEffect, useState } from 'react'
import { mainAgentApi } from '../api/mainAgent'
import { controlApi } from '../api/control'
import { getExplicitHumanApprovedFromWiredSources } from '../utils/hitlLabels'

/**
 * Polls only already-existing REST endpoints (no new APIs).
 * Returns tri-state for explicit human-gate approval from backend payloads.
 */
export function useWiredHitlExplicitApproval(pollMs = 12000) {
  const [explicitHumanApproved, setExplicitHumanApproved] = useState(null)

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const [a, c] = await Promise.allSettled([
          mainAgentApi.getStatus(),
          controlApi.getStatus(),
        ])
        const agentData = a.status === 'fulfilled' ? a.value?.data : null
        const controlData = c.status === 'fulfilled' ? c.value?.data : null
        const v = getExplicitHumanApprovedFromWiredSources(agentData, controlData)
        if (!cancelled) setExplicitHumanApproved(v)
      } catch {
        if (!cancelled) setExplicitHumanApproved(null)
      }
    }
    tick()
    const id = setInterval(tick, pollMs)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [pollMs])

  return explicitHumanApproved
}
