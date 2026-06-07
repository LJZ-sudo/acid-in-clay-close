import { useAgentStore } from '../../stores'
import clsx from 'clsx'

/**
 * Tool definitions — backend tool modules
 */
const TOOLS = [
  {
    id: 'eis_measurement',
    name: 'EIS Measurement',
    icon: '📊',
    description: 'Electrochemical impedance spectroscopy measurement',
    color: 'blue',
  },
  {
    id: 'eis_analysis',
    name: 'EIS Analysis',
    icon: '🔬',
    description: 'Impedance data analysis and fitting',
    color: 'indigo',
  },
  {
    id: 'temperature_control',
    name: 'Temperature Control',
    icon: '🌡️',
    description: 'Heating and cooling control',
    color: 'red',
  },
  {
    id: 'cooling_control',
    name: 'Cooldown Control',
    icon: '❄️',
    description: 'Cooling and temperature callback',
    color: 'cyan',
  },
  {
    id: 'arrhenius_analysis',
    name: 'Arrhenius Analysis',
    icon: '📈',
    description: 'Activation energy calculation and fitting',
    color: 'purple',
  },
  {
    id: 'phase_detection',
    name: 'Phase Detection',
    icon: '🔄',
    description: 'Automatic phase transition point detection',
    color: 'amber',
  },
  {
    id: 'report_generation',
    name: 'Report Generation',
    icon: '📝',
    description: 'Automatic experiment report generation',
    color: 'green',
  },
  {
    id: 'data_storage',
    name: 'Data Storage',
    icon: '💾',
    description: 'Experiment data persistence',
    color: 'gray',
  },
]

/**
 * Color tokens for tool cards
 */
const colorClasses = {
  blue: {
    active: 'bg-blue-500 border-blue-600 text-white shadow-blue-300',
    idle: 'bg-blue-50 border-blue-200 text-blue-700',
    pulse: 'bg-blue-400',
  },
  indigo: {
    active: 'bg-indigo-500 border-indigo-600 text-white shadow-indigo-300',
    idle: 'bg-indigo-50 border-indigo-200 text-indigo-700',
    pulse: 'bg-indigo-400',
  },
  red: {
    active: 'bg-red-500 border-red-600 text-white shadow-red-300',
    idle: 'bg-red-50 border-red-200 text-red-700',
    pulse: 'bg-red-400',
  },
  cyan: {
    active: 'bg-cyan-500 border-cyan-600 text-white shadow-cyan-300',
    idle: 'bg-cyan-50 border-cyan-200 text-cyan-700',
    pulse: 'bg-cyan-400',
  },
  purple: {
    active: 'bg-purple-500 border-purple-600 text-white shadow-purple-300',
    idle: 'bg-purple-50 border-purple-200 text-purple-700',
    pulse: 'bg-purple-400',
  },
  amber: {
    active: 'bg-amber-500 border-amber-600 text-white shadow-amber-300',
    idle: 'bg-amber-50 border-amber-200 text-amber-700',
    pulse: 'bg-amber-400',
  },
  green: {
    active: 'bg-green-500 border-green-600 text-white shadow-green-300',
    idle: 'bg-green-50 border-green-200 text-green-700',
    pulse: 'bg-green-400',
  },
  gray: {
    active: 'bg-gray-500 border-gray-600 text-white shadow-gray-300',
    idle: 'bg-gray-50 border-gray-200 text-gray-700',
    pulse: 'bg-gray-400',
  },
}

/**
 * Single tool card
 */
function ToolCard({ tool, isActive, callCount }) {
  const colors = colorClasses[tool.color] || colorClasses.gray
  
  return (
    <div
      className={clsx(
        'relative p-3 rounded-lg border-2 transition-all duration-300 cursor-default',
        isActive 
          ? `${colors.active} shadow-lg scale-105` 
          : colors.idle
      )}
    >
      {/* Pulse when active */}
      {isActive && (
        <span className="absolute -top-1 -right-1 flex h-3 w-3">
          <span className={clsx(
            'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
            colors.pulse
          )} />
          <span className={clsx(
            'relative inline-flex rounded-full h-3 w-3',
            colors.pulse
          )} />
        </span>
      )}
      
      {/* Call count badge */}
      {callCount > 0 && (
        <span className={clsx(
          'absolute -top-2 -left-2 px-1.5 py-0.5 text-xs font-bold rounded-full',
          isActive ? 'bg-white text-gray-800' : 'bg-gray-800 text-white'
        )}>
          {callCount}
        </span>
      )}
      
      {/* Icon and label */}
      <div className="flex items-center space-x-2">
        <span className="text-xl">{tool.icon}</span>
        <div className="flex-1 min-w-0">
          <p className={clsx(
            'font-medium text-sm truncate',
            isActive ? 'text-white' : ''
          )}>
            {tool.name}
          </p>
          <p className={clsx(
            'text-xs truncate',
            isActive ? 'text-white/80' : 'text-gray-500'
          )}>
            {tool.description}
          </p>
        </div>
      </div>
    </div>
  )
}

/**
 * Tool scheduling panel — Agent tools and active state
 */
function ToolsPanel() {
  const { activeTools, toolCallCounts, isThinking } = useAgentStore()
  
  const activeCount = activeTools?.length || 0
  const totalCalls = Object.values(toolCallCounts || {}).reduce((a, b) => a + b, 0)
  
  return (
    <div className="card h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <svg className="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
          <h3 className="font-semibold text-gray-800">Tool Scheduling</h3>
          {isThinking && (
            <span className="flex items-center text-xs text-primary-600">
              <span className="w-1.5 h-1.5 bg-primary-500 rounded-full mr-1 animate-pulse" />
              Active
            </span>
          )}
        </div>
        
        {/* Summary */}
        <div className="flex items-center space-x-3 text-xs text-gray-500">
          {activeCount > 0 && (
            <span className="px-2 py-0.5 bg-primary-100 text-primary-700 rounded-full">
              {activeCount} Active
            </span>
          )}
          {totalCalls > 0 && (
            <span>{totalCalls} calls</span>
          )}
        </div>
      </div>
      
      {/* Tool grid */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="grid grid-cols-2 gap-3">
          {TOOLS.map((tool) => (
            <ToolCard
              key={tool.id}
              tool={tool}
              isActive={activeTools?.includes(tool.id)}
              callCount={toolCallCounts?.[tool.id] || 0}
            />
          ))}
        </div>
        
        {/* Footnote */}
        <div className="mt-4 p-3 bg-gray-50 rounded-lg">
          <p className="text-xs text-gray-500 text-center">
            <span className="inline-flex items-center">
              <span className="w-2 h-2 bg-primary-500 rounded-full mr-1 animate-pulse" />
              Highlighted modules are being dynamically scheduled by the Agent
            </span>
          </p>
          <p className="text-xs text-gray-400 text-center mt-1">
            Not prescripted; driven by MainAgent real-time decisions
          </p>
        </div>
      </div>
    </div>
  )
}

export default ToolsPanel
