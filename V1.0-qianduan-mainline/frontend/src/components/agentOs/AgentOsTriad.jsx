const ROLE_DESC = {
  Planner: 'Proposes measurement actions from phase context and policy.',
  Critic: 'Reviews QC and retest logic (AI reviewer — separate from human HITL).',
  Orchestrator: 'Arbitrates and applies the final closed-loop policy.',
}

function snippetFromLastAction(lastAction) {
  if (!lastAction) return null
  if (typeof lastAction === 'string') return lastAction.slice(0, 160)
  const r = lastAction.reason || lastAction.message || lastAction.summary
  if (typeof r === 'string') return r.slice(0, 160)
  try {
    return JSON.stringify(lastAction).slice(0, 160)
  } catch {
    return '—'
  }
}

/**
 * Three triad cards: status, role, latest snippet, optional confidence / time from last decision row.
 */
function AgentOsTriad({ agents = [], microById = {}, latestDecision = null }) {
  const ts = latestDecision?.timestamp?.slice(0, 19) || null

  const rows = (agents.length ? agents : [
    { id: 'planner', name: 'Planner', role: ROLE_DESC.Planner, status: 'idle' },
    { id: 'critic', name: 'Critic', role: ROLE_DESC.Critic, status: 'idle' },
    { id: 'orchestrator', name: 'Orchestrator', role: ROLE_DESC.Orchestrator, status: 'idle' },
  ]).map((a) => {
    const name = a.name || a.id
    const micro =
      microById[a.id] ||
      microById[String(name || '').toLowerCase()] ||
      null
    const roleKey = name === 'Planner' || a.id === 'planner' ? 'Planner' : name === 'Critic' || a.id === 'critic' ? 'Critic' : name === 'Orchestrator' || a.id === 'orchestrator' ? 'Orchestrator' : null
    let conf = null
    if (roleKey === 'Planner') conf = latestDecision?.planner?.confidence ?? null
    else if (roleKey === 'Critic') conf = latestDecision?.critic?.confidence ?? null
    else if (roleKey === 'Orchestrator') conf = latestDecision?.orchestrator?.confidence ?? latestDecision?.confidence ?? null
    return {
      ...a,
      micro,
      conf,
      displayRole: a.role || (roleKey ? ROLE_DESC[roleKey] : null) || 'Agent role',
    }
  })

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {rows.map((agent) => {
        const micro = agent.micro
        const active =
          agent.status === 'active' || micro === 'running' || micro === 'thinking' || micro === 'completed'
        return (
          <div
            key={agent.id || agent.name}
            className={`rounded-xl border-2 p-4 ${active ? 'border-indigo-400 bg-indigo-50/60 shadow-sm' : 'border-gray-200 bg-white'}`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-bold text-gray-900">{agent.name}</span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  active ? 'bg-indigo-100 text-indigo-800' : 'bg-gray-100 text-gray-600'
                }`}
              >
                {micro || agent.status || 'idle'}
              </span>
            </div>
            <p className="text-xs text-gray-600 leading-snug">{agent.displayRole}</p>
            {snippetFromLastAction(agent.last_action) && (
              <div className="mt-3 text-xs bg-white rounded-lg border border-gray-100 p-2 font-mono text-gray-700 line-clamp-4">
                {snippetFromLastAction(agent.last_action)}
              </div>
            )}
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-gray-500">
              {agent.conf != null && <span>confidence: {(agent.conf * 100).toFixed(0)}%</span>}
              {ts && <span className="font-mono">last: {ts}</span>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default AgentOsTriad
