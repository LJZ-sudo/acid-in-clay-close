import { useAgentStore } from '../../stores'

const STATUS_COLORS = {
  idle: 'bg-gray-400',
  planning: 'bg-blue-500 animate-pulse',
  running: 'bg-green-500 animate-pulse',
  completed: 'bg-green-500',
  thinking: 'bg-blue-500 animate-pulse',
}

function AgentMicroStatus() {
  const { agentStatus } = useAgentStore()
  const roles = [
    { key: 'plannerAgent', short: 'P', name: 'Planner' },
    { key: 'criticAgent', short: 'C', name: 'Critic' },
    { key: 'mainAgent', short: 'O', name: 'Orchestrator' },
  ]

  return (
    <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 lg:gap-3 text-[11px] sm:text-xs text-gray-500 border-l border-gray-200 pl-2 sm:pl-3 lg:pl-4 min-w-0 max-w-[200px] lg:max-w-[240px] xl:max-w-none">
      {roles.map(({ key, short, name }) => {
        const status = agentStatus?.[key] || 'idle'
        const color = STATUS_COLORS[status] || STATUS_COLORS.idle
        return (
          <span key={key} className="flex items-center gap-0.5 sm:gap-1 shrink-0" title={`${name}: ${status}`}>
            <span className={`w-2 h-2 rounded-full shrink-0 ${color}`} />
            <span className="font-medium text-gray-600 hidden xl:inline">{name}</span>
            <span className="font-semibold text-gray-600 xl:hidden">{short}</span>
          </span>
        )
      })}
    </div>
  )
}

export default AgentMicroStatus
