const AXES = [
  {
    id: 1,
    label: 'HW Automation',
    color: 'blue',
    metricKey: 'hwAutomation',
  },
  {
    id: 2,
    label: 'Phase Detection',
    color: 'emerald',
    metricKey: 'phaseDetection',
  },
  {
    id: 3,
    label: 'Agent Optimization',
    color: 'indigo',
    metricKey: 'agentOptimization',
  },
  {
    id: 4,
    label: 'Evidence layer summary',
    color: 'amber',
    metricKey: 'evidenceDiscovery',
  },
  {
    id: 5,
    label: 'Discovery layer summary',
    color: 'purple',
    metricKey: 'materialPrediction',
  },
]

const colorClasses = {
  blue:    { bg: 'bg-blue-50',    border: 'border-blue-200',    text: 'text-blue-700',    badge: 'bg-blue-600' },
  emerald: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', badge: 'bg-emerald-600' },
  indigo:  { bg: 'bg-indigo-50',  border: 'border-indigo-200',  text: 'text-indigo-700',  badge: 'bg-indigo-600' },
  amber:   { bg: 'bg-amber-50',   border: 'border-amber-200',   text: 'text-amber-700',   badge: 'bg-amber-600' },
  purple:  { bg: 'bg-purple-50',  border: 'border-purple-200',  text: 'text-purple-700',  badge: 'bg-purple-600' },
}

function FiveAxisSummary({ metrics = {} }) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Five Innovation Axes</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {AXES.map((axis) => {
          const c = colorClasses[axis.color]
          const m = metrics[axis.metricKey] || {}
          return (
            <div key={axis.id} className={`${c.bg} ${c.border} border rounded-lg p-3`}>
              <div className="flex items-center gap-1.5 mb-2">
                <span className={`${c.badge} text-white text-xs font-bold w-5 h-5 rounded flex items-center justify-center`}>{axis.id}</span>
                <span className={`text-xs font-semibold ${c.text}`}>{axis.label}</span>
              </div>
              <div className="text-lg font-bold text-gray-800">{m.primary ?? '--'}</div>
              <div className="text-xs text-gray-500 mt-1">{m.secondary ?? '--'}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default FiveAxisSummary
