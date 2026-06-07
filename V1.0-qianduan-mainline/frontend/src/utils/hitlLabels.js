/**
 * Single source of truth for HITL / autonomy display labels (Phase 1A / 1B-a).
 * Keep badge copy identical across Header, Runtime Cockpit, and HITLBoundaryBadge.
 */

// TODO(Phase 1B+ / backend contract): When GET /api/agent/status or GET /api/control/status
// adds an explicit human-gate field, add its key to WIRED_HUMAN_APPROVAL_KEYS below.
// Do NOT map `latest_decisions[].critic.approved` here — that is the AI critic, not a human reviewer.

const WIRED_HUMAN_APPROVAL_KEYS = [
  'human_approved',
  'humanApproved',
  'reviewer_approved',
  'reviewerApproved',
  'hitl_human_approved',
  'hitlHumanApproved',
]

/**
 * Inspect only root-level fields on payloads already returned by wired endpoints.
 * @param {Record<string, unknown>|null|undefined} agentStatusData — from GET /api/agent/status
 * @param {Record<string, unknown>|null|undefined} controlStatusData — from GET /api/control/status
 * @returns {true|false|null} true/false only when an explicit boolean field exists; otherwise null (do not infer)
 */
export function getExplicitHumanApprovedFromWiredSources(agentStatusData, controlStatusData) {
  const sources = [agentStatusData, controlStatusData].filter((x) => x && typeof x === 'object')
  for (const obj of sources) {
    for (const k of WIRED_HUMAN_APPROVAL_KEYS) {
      if (Object.prototype.hasOwnProperty.call(obj, k) && typeof obj[k] === 'boolean') {
        return obj[k]
      }
    }
  }
  return null
}

export const HITL_LABELS = {
  offline: 'Offline',
  auto: '🤖 Auto',
  humanRequired: '👤 Human Required',
  humanApproved: '✅ Human Approved',
}

/**
 * @param {boolean} experimentRunning
 * @param {boolean} autoDecisionEnabled
 * @param {true|false|null} [explicitHumanApproved] from getExplicitHumanApprovedFromWiredSources; null = field absent
 * @returns {{ label: string, color: string }}
 */
export function getHitlRuntimePill(experimentRunning, autoDecisionEnabled, explicitHumanApproved = null) {
  if (!experimentRunning) {
    return { label: HITL_LABELS.offline, color: 'bg-gray-100 text-gray-600' }
  }
  if (autoDecisionEnabled) {
    return { label: HITL_LABELS.auto, color: 'bg-green-100 text-green-800' }
  }
  if (explicitHumanApproved === true) {
    return { label: HITL_LABELS.humanApproved, color: 'bg-emerald-100 text-emerald-800' }
  }
  return { label: HITL_LABELS.humanRequired, color: 'bg-amber-100 text-amber-800' }
}
