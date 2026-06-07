import { useState } from 'react'
import { Link } from 'react-router-dom'
import { dataApi } from '../../api/data'

/**
 * Lazy fan-out: only scans when user clicks. No fabricated queue.
 */
function ApprovalQueuePanel() {
  const [items, setItems] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const scan = async () => {
    setLoading(true)
    setError(null)
    setItems(null)
    try {
      const exResp = await dataApi.getExperiments()
      const experiments = exResp?.data?.experiments || []
      const found = []

      const subset = experiments.slice(0, 8)
      await Promise.all(
        subset.map(async (exp) => {
          const sampleId = exp.sample_id || exp.id || exp
          if (!sampleId) return
          try {
            const saved = await dataApi.getSavedNextPlan(sampleId)
            if (saved?.data?.ok && saved.data.next_plan) {
              found.push({
                sampleId: String(sampleId),
                plan: saved.data.next_plan,
                source: 'saved_next_plan',
              })
            }
          } catch {
            /* skip sample */
          }
        })
      )

      setItems(found)
    } catch (e) {
      setError(e.response?.data?.message || e.message || 'Scan failed.')
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-900 mb-1">Approval queue</h3>
      <p className="text-xs text-gray-500 mb-3">
        Human HITL for next-experiment plans is separate from AI Critic acceptance. Items appear only when saved next-plan
        data exists for a sample.
      </p>
      <p className="text-xs mb-3">
        <Link to="/validation" className="font-medium text-indigo-600 hover:text-indigo-800 hover:underline">
          Open Validation Loop
        </Link>
      </p>
      <button
        type="button"
        onClick={scan}
        disabled={loading}
        className="w-full px-3 py-2 text-xs font-medium bg-gray-900 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50"
      >
        {loading ? 'Scanning…' : 'Refresh queue (samples × saved next-plan)'}
      </button>

      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}

      {items && items.length === 0 && !error && (
        <p className="text-xs text-gray-600 mt-3 border border-dashed rounded-lg p-3 bg-gray-50">
          No approval items available from current data sources.
        </p>
      )}

      {items && items.length > 0 && (
        <ul className="mt-3 space-y-2 max-h-48 overflow-y-auto text-xs">
          {items.map((row) => (
            <li key={row.sampleId} className="border rounded-lg p-2 bg-amber-50/40 border-amber-100">
              <div className="font-mono font-semibold text-gray-900">{row.sampleId}</div>
              <div className="text-gray-600 mt-1">
                {row.plan?.recommendation_type || 'plan'} — {row.plan?.rationale?.slice?.(0, 120) || '—'}
              </div>
            </li>
          ))}
        </ul>
      )}

      {items === null && !loading && !error && (
        <p className="text-[11px] text-gray-400 mt-2">Queue not loaded yet. Use the button to avoid automatic fan-out.</p>
      )}
    </div>
  )
}

export default ApprovalQueuePanel
