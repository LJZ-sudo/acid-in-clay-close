import { useUIStore, useAgentStore } from '../../stores'
import { getHitlRuntimePill } from '../../utils/hitlLabels'

/** @param {{ explicitHumanApproved?: true|false|null }} props — supplied by LiveExperiment (single poll) or null if unknown */
function HITLBoundaryBadge({ explicitHumanApproved = null } = {}) {
  const { experimentRunning } = useUIStore()
  const { autoDecisionEnabled } = useAgentStore()

  const mode = getHitlRuntimePill(experimentRunning, autoDecisionEnabled, explicitHumanApproved)

  return (
    <div className="bg-white rounded-xl border p-4 flex items-center justify-between">
      <span className="text-sm font-medium text-gray-600">HITL Boundary</span>
      <span className={`px-3 py-1 rounded-full text-xs font-bold ${mode.color}`}>
        {mode.label}
      </span>
    </div>
  )
}

export default HITLBoundaryBadge
