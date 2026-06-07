import { useEffect, useMemo, useState } from 'react'
import { controlApi } from '../api/control'
import { useUIStore } from '../stores'
import { deriveSystemTruthModel } from '../utils/systemTruthModel'

/**
 * Polls control status and combines with WebSocket reachability for {@link deriveSystemTruthModel}.
 */
export function useSystemTruth(pollMs = 4000) {
  const wsConnected = useUIStore((s) => s.wsConnected)
  const [apiReachable, setApiReachable] = useState(true)
  const [hwStatus, setHwStatus] = useState(null)

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const r = await controlApi.getStatus()
        if (cancelled) return
        setHwStatus(r?.data ?? null)
        setApiReachable(true)
      } catch {
        if (cancelled) return
        setApiReachable(false)
        setHwStatus(null)
      }
    }
    tick()
    const id = setInterval(tick, pollMs)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [pollMs])

  return useMemo(
    () => deriveSystemTruthModel({ wsConnected, apiReachable, hwStatus }),
    [wsConnected, apiReachable, hwStatus]
  )
}
