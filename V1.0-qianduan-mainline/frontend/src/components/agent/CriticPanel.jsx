import { useAgentStore } from '../../stores'
import clsx from 'clsx'

/**
 * Critic Agent panel — evaluation results and suggestions
 */
function CriticPanel() {
  const { criticResult, agentStatus } = useAgentStore()
  const isActive = agentStatus.criticAgent === 'active'
  const isCompleted = agentStatus.criticAgent === 'completed'

  const getScoreColor = (score) => {
    if (score >= 0.8) return 'text-success'
    if (score >= 0.6) return 'text-warning'
    return 'text-danger'
  }

  const getScoreLabel = (score) => {
    if (score >= 0.8) return 'Excellent'
    if (score >= 0.6) return 'Good'
    if (score >= 0.4) return 'Fair'
    return 'Needs improvement'
  }

  return (
    <div className="card p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <span className="text-lg">🔍</span>
          <h4 className="font-semibold text-gray-800">Critic review</h4>
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

      {criticResult ? (
        <div className="space-y-4">
          {/* Overall score */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span className="text-sm text-gray-600">Overall score</span>
            <div className="flex items-center space-x-2">
              <span className={clsx('text-2xl font-bold', getScoreColor(criticResult.score))}>
                {(criticResult.score * 100).toFixed(0)}
              </span>
              <span className={clsx('text-xs', getScoreColor(criticResult.score))}>
                {getScoreLabel(criticResult.score)}
              </span>
            </div>
          </div>

          {/* Evaluation dimensions */}
          {criticResult.dimensions && (
            <div className="space-y-2">
              <p className="text-xs text-gray-500 font-medium">Evaluation dimensions</p>
              {Object.entries(criticResult.dimensions).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">{key}</span>
                  <div className="flex items-center space-x-2 w-32">
                    <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div 
                        className={clsx(
                          'h-full rounded-full',
                          value >= 0.8 ? 'bg-success' :
                          value >= 0.6 ? 'bg-warning' : 'bg-danger'
                        )}
                        style={{ width: `${value * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-500 w-8 text-right">
                      {(value * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Suggestions */}
          {criticResult.suggestions && criticResult.suggestions.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-gray-500 font-medium">Suggestions</p>
              <ul className="space-y-1">
                {criticResult.suggestions.map((suggestion, index) => (
                  <li key={index} className="flex items-start space-x-2 text-sm text-gray-700">
                    <span className="text-amber-500 mt-0.5">•</span>
                    <span>{suggestion}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Analysis rationale */}
          {criticResult.analysis && (
            <div className="p-3 bg-blue-50 rounded-lg">
              <p className="text-xs text-blue-600 font-medium mb-1">Analysis rationale</p>
              <p className="text-sm text-blue-800">{criticResult.analysis}</p>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-400">
          <svg className="w-10 h-10 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
          </svg>
          <p className="text-sm">Waiting for critic review...</p>
        </div>
      )}
    </div>
  )
}

export default CriticPanel
