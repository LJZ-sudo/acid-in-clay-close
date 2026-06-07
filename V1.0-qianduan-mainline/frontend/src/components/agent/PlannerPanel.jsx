import { useAgentStore } from '../../stores'
import clsx from 'clsx'

/**
 * Planner Agent panel — next plan and recommended action
 */
function PlannerPanel() {
  const { plannerResult, agentStatus } = useAgentStore()
  const isActive = agentStatus.plannerAgent === 'active'
  const isCompleted = agentStatus.plannerAgent === 'completed'

  const actionTypeConfig = {
    continue: { label: 'Continue', color: 'bg-green-100 text-green-700' },
    densify: { label: 'Densify', color: 'bg-blue-100 text-blue-700' },
    backtrack: { label: 'Backtrack', color: 'bg-amber-100 text-amber-700' },
    remeasure: { label: 'Retest', color: 'bg-purple-100 text-purple-700' },
    stop: { label: 'Stop', color: 'bg-red-100 text-red-700' },
  }

  return (
    <div className="card p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <span className="text-lg">📊</span>
          <h4 className="font-semibold text-gray-800">Planner proposal</h4>
          {isActive && (
            <span className="w-2 h-2 bg-primary-500 rounded-full animate-pulse" />
          )}
        </div>
        {isCompleted && (
          <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
            Done
          </span>
        )}
      </div>

      {plannerResult ? (
        <div className="space-y-4">
          {/* Recommended action */}
          <div className="p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600">Recommended action</span>
              {plannerResult.action && (
                <span className={clsx(
                  'text-xs px-2 py-0.5 rounded-full font-medium',
                  actionTypeConfig[plannerResult.action]?.color || 'bg-gray-100 text-gray-700'
                )}>
                  {actionTypeConfig[plannerResult.action]?.label || plannerResult.action}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-800 font-medium">
              {plannerResult.description || 'Continue current measurement'}
            </p>
          </div>

          {/* Confidence */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Confidence</span>
            <div className="flex items-center space-x-2 w-40">
              <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                <div 
                  className={clsx(
                    'h-full rounded-full transition-all',
                    plannerResult.confidence >= 0.8 ? 'bg-success' :
                    plannerResult.confidence >= 0.6 ? 'bg-primary-500' : 'bg-warning'
                  )}
                  style={{ width: `${(plannerResult.confidence || 0) * 100}%` }}
                />
              </div>
              <span className="text-sm font-medium text-gray-700 w-12 text-right">
                {((plannerResult.confidence || 0) * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Next step parameters */}
          {plannerResult.nextParams && (
            <div className="space-y-2">
              <p className="text-xs text-gray-500 font-medium">Next step parameters</p>
              <div className="grid grid-cols-2 gap-2 text-sm">
                {plannerResult.nextParams.temperature !== undefined && (
                  <div className="p-2 bg-blue-50 rounded">
                    <span className="text-xs text-blue-600">Target temperature</span>
                    <p className="font-medium text-blue-800">
                      {plannerResult.nextParams.temperature}°C
                    </p>
                  </div>
                )}
                {plannerResult.nextParams.step !== undefined && (
                  <div className="p-2 bg-green-50 rounded">
                    <span className="text-xs text-green-600">Step size</span>
                    <p className="font-medium text-green-800">
                      {plannerResult.nextParams.step}°C
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Trigger conditions */}
          {plannerResult.triggers && plannerResult.triggers.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-gray-500 font-medium">Trigger conditions</p>
              <div className="flex flex-wrap gap-2">
                {plannerResult.triggers.map((trigger, index) => (
                  <span 
                    key={index}
                    className="text-xs px-2 py-1 bg-amber-50 text-amber-700 rounded-full"
                  >
                    {trigger}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Decision rationale */}
          {plannerResult.reasoning && (
            <div className="p-3 bg-indigo-50 rounded-lg">
              <p className="text-xs text-indigo-600 font-medium mb-1">Decision rationale</p>
              <p className="text-sm text-indigo-800">{plannerResult.reasoning}</p>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-400">
          <svg className="w-10 h-10 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-sm">Waiting for planner proposal...</p>
        </div>
      )}
    </div>
  )
}

export default PlannerPanel
