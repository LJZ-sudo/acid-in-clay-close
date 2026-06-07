const ACTION_COLORS = {
  CONTINUE_MEASUREMENT: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-200' },
  TRIGGER_FINE_SCAN: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-200' },
  BACKTRACK: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-200' },
  RE_MEASURE: { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-200' },
}

/**
 * Decision history list (reused from former AgentWorkbench; Critic labeled as AI-only).
 */
function DecisionTimeline({ decisions = [] }) {
  if (!decisions.length) {
    return <div className="text-sm text-gray-500 p-4 border border-dashed rounded-lg">No decisions recorded yet.</div>
  }

  return (
    <div className="space-y-3 max-h-[560px] overflow-auto pr-1">
      {decisions.slice().reverse().map((d, i) => {
        const colors = ACTION_COLORS[d.action] || { bg: 'bg-gray-100', text: 'text-gray-700', border: 'border-gray-200' }
        return (
          <div key={d.id || i} className={`${colors.bg} ${colors.border} border rounded-xl p-4`}>
            <div className="flex items-center justify-between mb-2">
              <span className={`font-bold text-sm ${colors.text}`}>{d.action}</span>
              <span className="text-xs text-gray-400 font-mono">{d.timestamp?.slice(0, 19) || '—'}</span>
            </div>

            {d.planner && (
              <div className="mb-2 pl-3 border-l-2 border-blue-300">
                <div className="text-xs font-semibold text-blue-800">Planner</div>
                <div className="text-xs text-gray-600">{d.planner.reason || '—'}</div>
                <div className="text-xs text-gray-500">
                  confidence: {d.planner.confidence != null ? `${(d.planner.confidence * 100).toFixed(0)}%` : '—'}
                </div>
              </div>
            )}

            {d.critic && (
              <div className="mb-2 pl-3 border-l-2 border-amber-300">
                <div className="text-xs font-semibold text-amber-800">AI Critic (not human approval)</div>
                <div className="text-xs text-gray-600">
                  {d.critic.approved ? 'Accepted proposal' : 'Rejected proposal'} — {d.critic.reason || '—'}
                </div>
                <div className="text-xs text-gray-500">QC: {d.critic.qc_grade || '—'}</div>
              </div>
            )}

            {d.orchestrator && (
              <div className="pl-3 border-l-2 border-green-300">
                <div className="text-xs font-semibold text-green-800">Orchestrator</div>
                <div className="text-xs text-gray-600">{d.orchestrator.reason || '—'}</div>
                <div className="text-xs text-gray-500">
                  source: {d.orchestrator.source_agent || '—'} | confidence:{' '}
                  {d.confidence != null ? `${(d.confidence * 100).toFixed(0)}%` : '—'}
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default DecisionTimeline
