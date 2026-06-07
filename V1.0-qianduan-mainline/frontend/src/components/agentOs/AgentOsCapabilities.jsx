/**
 * Lightweight capability visibility from GET /agents/capabilities.
 */
function AgentOsCapabilities({ data, error, loading }) {
  if (loading) {
    return <p className="text-xs text-gray-500 py-2">Loading capabilities…</p>
  }
  if (error) {
    return (
      <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
        Capabilities unavailable: {error}
      </p>
    )
  }

  const agents = Array.isArray(data?.agents) ? data.agents : []

  if (!agents.length) {
    return (
      <p className="text-xs text-gray-500">
        No capability definitions returned by the API (empty or unexpected shape).
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {agents.map((a) => (
        <div key={a.id || a.name} className="border border-gray-100 rounded-lg p-3 bg-gray-50/80">
          <div className="text-xs font-semibold text-gray-800">{a.name || a.id}</div>
          <p className="text-[11px] text-gray-600 mt-0.5">{a.role || '—'}</p>
          <div className="flex flex-wrap gap-1 mt-2">
            {(a.capabilities || []).map((c) => (
              <span key={c} className="text-[10px] px-2 py-0.5 rounded-full bg-white border border-gray-200 text-gray-700 font-mono">
                {c}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default AgentOsCapabilities
