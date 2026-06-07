import { useAgentStore } from '../../stores'
import { HITL_LABELS } from '../../utils/hitlLabels'

const STATUS_COLORS = {
  idle: 'bg-gray-200 text-gray-600',
  planning: 'bg-blue-100 text-blue-700',
  running: 'bg-green-100 text-green-700',
  completed: 'bg-green-100 text-green-700',
  thinking: 'bg-blue-100 text-blue-700',
}

function AgentTriadStatus({ explicitHumanApproved = null } = {}) {
  const { agentStatus } = useAgentStore()

  const roles = [
    { key: 'plannerAgent', label: 'Planner', description: 'Plans next measurement action' },
    { key: 'criticAgent', label: 'Critic', description: 'Reviews and validates decisions' },
    { key: 'mainAgent', label: 'Orchestrator', description: 'Executes final decision' },
  ]

  return (
    <div className="bg-white rounded-xl border p-4">
      <h3 className="font-semibold mb-3 text-sm">Agent Triad</h3>
      <div className="space-y-2">
        {roles.map(({ key, label, description }) => {
          const status = agentStatus?.[key] || 'idle'
          const colorClass = STATUS_COLORS[status] || STATUS_COLORS.idle
          return (
            <div key={key} className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium">{label}</div>
                <div className="text-xs text-gray-400">{description}</div>
              </div>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
                {status}
              </span>
            </div>
          )
        })}
      </div>
      {explicitHumanApproved === true && (
        <p className="mt-3 text-xs font-semibold text-emerald-800 bg-emerald-50 border border-emerald-100 rounded-lg px-2 py-1.5">
          {HITL_LABELS.humanApproved} <span className="font-normal text-emerald-700">(from API)</span>
        </p>
      )}
    </div>
  )
}

export default AgentTriadStatus
