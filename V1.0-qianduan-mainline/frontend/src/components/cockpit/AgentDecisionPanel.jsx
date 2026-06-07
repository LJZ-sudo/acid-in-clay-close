import { useEffect, useState } from 'react'
import { mainAgentApi } from '../../api/mainAgent'

const emptyBody = 'text-sm text-gray-500 text-center py-4 px-2 leading-relaxed'
const emptySub = 'text-xs text-gray-400 mt-1 block'

function AgentDecisionPanel() {
  const [decisions, setDecisions] = useState([])
  const [loading, setLoading] = useState(false)
  const [statusLoading, setStatusLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const resp = await mainAgentApi.getStatus()
        setDecisions(resp?.data?.latest_decisions || resp?.data?.decisions || [])
      } catch { /* ignore */ }
      finally {
        setStatusLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 3000)
    return () => clearInterval(interval)
  }, [])

  const triggerDecision = async () => {
    setLoading(true)
    try {
      const resp = await mainAgentApi.decide({})
      if (resp?.data) setDecisions(prev => [...prev, resp.data])
    } catch { /* ignore */ }
    setLoading(false)
  }

  const latest = decisions.length > 0 ? decisions[decisions.length - 1] : null

  return (
    <div className="bg-white rounded-xl border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Agent Decision</h3>
        <button onClick={triggerDecision} disabled={loading} className="text-xs px-3 py-1 bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200 disabled:opacity-50">
          {loading ? '...' : 'Trigger'}
        </button>
      </div>

      {statusLoading ? (
        <div className={emptyBody}>
          Loading agent status…
          <span className={emptySub}>Polling GET /api/agent/status</span>
        </div>
      ) : null}

      {!statusLoading && latest ? (
        <div className="space-y-2">
          <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
            <div className="text-xs font-bold text-blue-700 mb-1">PLANNER</div>
            <div className="text-sm font-semibold">{latest.planner?.action || '--'}</div>
            <div className="text-xs text-gray-600 mt-1">{latest.planner?.reason || '--'}</div>
          </div>

          <div className="bg-amber-50 rounded-lg p-3 border border-amber-100">
            <div className="text-xs font-bold text-amber-700 mb-1">CRITIC (AI)</div>
            <div className="text-sm font-semibold">{latest.critic?.approved ? '✅ Approved' : '❌ Rejected'}</div>
            <div className="text-xs text-gray-500 mt-0.5">Not the same as human HITL approval in the header.</div>
            <div className="text-xs text-gray-600 mt-1">{latest.critic?.reason || '--'}</div>
          </div>

          <div className="bg-green-50 rounded-lg p-3 border border-green-100">
            <div className="text-xs font-bold text-green-700 mb-1">ORCHESTRATOR → {latest.action}</div>
            <div className="text-xs text-gray-600">{latest.orchestrator?.reason || latest.reasoning || '--'}</div>
            <div className="text-xs text-gray-400 mt-1">confidence: {latest.confidence ? (latest.confidence * 100).toFixed(0) + '%' : '--'}</div>
          </div>
        </div>
      ) : null}

      {!statusLoading && !latest ? (
        <div className={emptyBody}>
          No agent decisions in the current window.
          <span className={emptySub}>Start a run, connect hardware, or press Trigger to request a decision cycle.</span>
        </div>
      ) : null}

      {decisions.length > 1 && (
        <div className="pt-2 border-t">
          <div className="text-xs text-gray-500 mb-1">Previous ({decisions.length - 1})</div>
          <div className="space-y-1 max-h-32 overflow-auto">
            {decisions.slice(0, -1).reverse().slice(0, 5).map((d, i) => (
              <div key={d.id || i} className="text-xs px-2 py-1 bg-gray-50 rounded flex justify-between">
                <span className="font-mono font-semibold">{d.action}</span>
                <span className="text-gray-400">{d.timestamp?.slice(11, 19) || ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default AgentDecisionPanel
