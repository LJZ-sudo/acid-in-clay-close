import clsx from 'clsx'
import { useUIStore } from '../../stores'
import { SYSTEM_STATUS } from '../../utils/constants'
import { useSystemTruth } from '../../hooks/useSystemTruth'
import { getTruthCompactLabels } from '../../utils/systemTruthModel'

/**
 * Header strip: API/WS reachability, hardware capability, session, execution mode, and experiment lifecycle (English-only).
 */
function ConnectionStatus() {
  const truth = useSystemTruth(4000)
  const { systemStatus, experimentRunning } = useUIStore()
  const labels = getTruthCompactLabels(truth)

  const lifecycle = (() => {
    switch (systemStatus) {
      case SYSTEM_STATUS.RUNNING:
        return { dot: 'bg-emerald-500', text: 'Exp: running', title: 'Experiment running' }
      case SYSTEM_STATUS.PAUSED:
        return { dot: 'bg-amber-500', text: 'Exp: paused', title: 'Experiment paused' }
      case SYSTEM_STATUS.CONNECTED:
        return { dot: 'bg-sky-500', text: 'Exp: idle', title: 'Controller connected; experiment idle' }
      case SYSTEM_STATUS.ERROR:
        return { dot: 'bg-red-500', text: 'Exp: error', title: 'System error state' }
      default:
        return { dot: 'bg-gray-400', text: 'Exp: off', title: 'No active experiment lifecycle signal' }
    }
  })()

  const chip = (dotOk, abbr, title) => (
    <span className="inline-flex items-center gap-0.5 shrink-0" title={title}>
      <span className={clsx('w-1.5 h-1.5 rounded-full shrink-0', dotOk ? 'bg-emerald-500' : 'bg-gray-300')} />
      <span className="font-mono text-[10px] sm:text-[11px] text-gray-600">{abbr}</span>
    </span>
  )

  return (
    <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
      <div className="flex items-center gap-1 sm:gap-1.5 border-r border-gray-200 pr-1.5 sm:pr-2 shrink-0">
        {chip(labels.api.ok, labels.api.abbr, labels.api.ok ? 'Control API reachable' : 'Control API unreachable')}
        {chip(labels.ws.ok, labels.ws.abbr, labels.ws.ok ? 'WebSocket reachable' : 'WebSocket unreachable')}
      </div>
      <div className="flex items-center gap-1 sm:gap-1.5 flex-wrap min-w-0">
        <span className="inline-flex items-center gap-0.5 shrink-0" title={labels.hardware.title}>
          <span className="font-mono text-[10px] sm:text-[11px] text-gray-700 font-semibold">{labels.hardware.abbr}</span>
        </span>
        <span className="inline-flex items-center gap-0.5 shrink-0" title={labels.session.title}>
          <span className="font-mono text-[10px] sm:text-[11px] text-gray-600">{labels.session.abbr}</span>
        </span>
        <span className="inline-flex items-center gap-0.5 shrink-0" title={labels.execution.title}>
          <span className="font-mono text-[10px] sm:text-[11px] text-indigo-700">{labels.execution.abbr}</span>
        </span>
      </div>
      <div
        className={clsx(
          'hidden md:inline-flex items-center gap-0.5 shrink-0 rounded-full bg-gray-100 px-1.5 py-0.5',
          experimentRunning && 'ring-1 ring-emerald-200'
        )}
        title={lifecycle.title}
      >
        <span className={clsx('w-1.5 h-1.5 rounded-full shrink-0', lifecycle.dot)} />
        <span className="text-[10px] sm:text-[11px] font-medium text-gray-700 max-w-[4.5rem] lg:max-w-none truncate">
          {lifecycle.text}
        </span>
      </div>
    </div>
  )
}

export default ConnectionStatus
