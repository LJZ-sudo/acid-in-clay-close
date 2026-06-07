/**
 * Lightweight, props-only ticker for recent agent decisions (Command Center).
 * @param {{ decisions?: Array<Record<string, unknown>> }} props
 */
function AgentTicker({ decisions = [] }) {
  const list = Array.isArray(decisions) ? decisions : []

  return (
    <div className="bg-white rounded-xl border p-5">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
        Agent Ticker — Recent Decisions
      </h3>
      {list.length === 0 ? (
        <p className="text-sm text-gray-400">
          No decisions yet. Start an experiment to see the Agent in action.
        </p>
      ) : (
        <div className="overflow-x-auto pb-1">
          <div className="flex gap-2 min-w-min">
            {list.slice(-5).reverse().map((d, i) => (
              <div
                key={d.id || i}
                className="flex-shrink-0 w-64 flex flex-col gap-1 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100"
              >
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-bold truncate ${
                      d.action === 'CONTINUE_MEASUREMENT'
                        ? 'bg-green-100 text-green-700'
                        : d.action === 'TRIGGER_FINE_SCAN'
                          ? 'bg-blue-100 text-blue-700'
                          : d.action === 'BACKTRACK'
                            ? 'bg-amber-100 text-amber-700'
                            : d.action === 'RE_MEASURE'
                              ? 'bg-red-100 text-red-700'
                              : 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {d.action}
                  </span>
                  <span className="text-xs text-gray-400 font-mono">
                    {d.timestamp?.slice(11, 19) || ''}
                  </span>
                </div>
                <span className="text-xs text-gray-500 line-clamp-2">
                  {d.reasoning || d.reason || '--'}
                </span>
                <span className="text-xs text-gray-400">
                  {d.confidence ? `${(d.confidence * 100).toFixed(0)}% conf` : '--'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default AgentTicker
