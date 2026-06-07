import { useEffect, useState } from 'react'
import { loadStageOutput } from '../utils/stageOutputLoader'

/**
 * Load one stage output file; isolated state per hook instance.
 * @param {string|null|undefined} filePath
 * @param {{ kindHint?: 'json'|'jsonl'|'markdown'|'text', enabled?: boolean }} [options]
 */
export function useStageOutputLoader(filePath, options = {}) {
  const { kindHint, enabled = true } = options
  const [loading, setLoading] = useState(Boolean(enabled && filePath))
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!enabled || !filePath) {
      setLoading(false)
      setResult(null)
      return undefined
    }

    let cancelled = false
    setLoading(true)
    loadStageOutput(filePath, { kindHint })
      .then((r) => {
        if (!cancelled) setResult(r)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [filePath, kindHint, enabled])

  return { loading, result }
}
