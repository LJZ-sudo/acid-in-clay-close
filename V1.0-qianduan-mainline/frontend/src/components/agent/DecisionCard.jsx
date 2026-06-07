import clsx from 'clsx'
import { formatTimestamp } from '../../utils/formatters'

const typeConfig = {
  plan: {
    icon: '📋',
    color: 'border-blue-500 bg-blue-50',
    label: 'Plan',
  },
  trigger: {
    icon: '⚡',
    color: 'border-amber-500 bg-amber-50',
    label: 'Trigger',
  },
  action: {
    icon: '🎯',
    color: 'border-green-500 bg-green-50',
    label: 'Execute',
  },
  agent_call: {
    icon: '🤖',
    color: 'border-purple-500 bg-purple-50',
    label: 'Agent call',
  },
  tool_call: {
    icon: '🔧',
    color: 'border-cyan-500 bg-cyan-50',
    label: 'Tool call',
  },
  critic: {
    icon: '🔍',
    color: 'border-orange-500 bg-orange-50',
    label: 'Critic review',
  },
  planner: {
    icon: '📊',
    color: 'border-indigo-500 bg-indigo-50',
    label: 'Planner proposal',
  },
  error: {
    icon: '❌',
    color: 'border-red-500 bg-red-50',
    label: 'Error',
  },
  complete: {
    icon: '✅',
    color: 'border-green-500 bg-green-50',
    label: 'Done',
  },
}

/**
 * Decision card — displays a single thought step
 */
function DecisionCard({ thought, isLatest = false }) {
  const config = typeConfig[thought.type] || typeConfig.plan
  
  return (
    <div
      className={clsx(
        'border-l-4 rounded-r-lg p-4 transition-all',
        config.color,
        isLatest && 'ring-2 ring-primary-300'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <span className="text-lg">{config.icon}</span>
          <span className="font-medium text-gray-800">{config.label}</span>
          {thought.agent && (
            <span className="text-xs px-2 py-0.5 bg-gray-200 rounded-full text-gray-600">
              {thought.agent}
            </span>
          )}
        </div>
        <span className="text-xs text-gray-500">
          {formatTimestamp(thought.timestamp, 'HH:mm:ss')}
        </span>
      </div>
      
      {/* Body */}
      <div className="text-sm text-gray-700 whitespace-pre-wrap">
        {thought.content}
      </div>
      
      {/* Extra payload */}
      {thought.data && (
        <div className="mt-2 p-2 bg-white/50 rounded text-xs font-mono text-gray-600 overflow-x-auto">
          {typeof thought.data === 'object' 
            ? JSON.stringify(thought.data, null, 2)
            : thought.data}
        </div>
      )}
      
      {/* Score (if present) */}
      {thought.score !== undefined && (
        <div className="mt-2 flex items-center space-x-2">
          <span className="text-xs text-gray-500">Score:</span>
          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className={clsx(
                'h-full rounded-full transition-all',
                thought.score >= 0.8 ? 'bg-success' :
                thought.score >= 0.6 ? 'bg-warning' : 'bg-danger'
              )}
              style={{ width: `${thought.score * 100}%` }}
            />
          </div>
          <span className="text-xs font-medium">
            {(thought.score * 100).toFixed(0)}%
          </span>
        </div>
      )}
    </div>
  )
}

export default DecisionCard
