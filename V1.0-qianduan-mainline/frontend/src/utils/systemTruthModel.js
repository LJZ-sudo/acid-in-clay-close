/**
 * Single source of truth for platform / hardware / session semantics.
 * Rules:
 * - "Real" execution mode only when connected and simulate is explicitly false.
 * - Successful connect never implies the physical instrument is certified—only the current session mode.
 * - Disconnected does not mean "no real hardware"; use session + capability copy separately.
 * - When unsure (API down or no status yet), prefer unverified.
 */

/** @type {boolean} Set when this browser tab has observed a non-simulation control session. */
let sessionEvidenceNonSimInstrument = false

/**
 * Test-only reset (optional); not used in production UI.
 */
export function resetSessionInstrumentEvidenceForTests() {
  sessionEvidenceNonSimInstrument = false
}

/**
 * @typedef {'real'|'simulation'|'unverified'} ExecutionMode
 */

/**
 * @param {object} input
 * @param {boolean} [input.wsConnected]
 * @param {boolean} [input.apiReachable] Last control API poll succeeded
 * @param {object|null|undefined} [input.hwStatus] Payload from GET control status
 * @returns {{
 *   platformReachability: { apiReachable: boolean, wsReachable: boolean },
 *   hardwareCapability: { realHardwareSupported: boolean, simulationAvailable: boolean, capabilityUnverified: boolean },
 *   sessionConnection: { connected: boolean, disconnected: boolean },
 *   executionMode: ExecutionMode,
 * }}
 */
export function deriveSystemTruthModel({
  wsConnected = false,
  apiReachable = false,
  hwStatus = null,
} = {}) {
  if (hwStatus && hwStatus.connected === true && hwStatus.simulate === false) {
    sessionEvidenceNonSimInstrument = true
  }

  const sessionConnected = Boolean(hwStatus?.connected)

  /** @type {ExecutionMode} */
  let executionMode = 'unverified'
  if (sessionConnected) {
    executionMode = hwStatus?.simulate === true ? 'simulation' : 'real'
  } else {
    executionMode = 'unverified'
  }

  const realHardwareSupported = sessionEvidenceNonSimInstrument === true
  const simulationAvailable = Boolean(apiReachable)
  const capabilityUnverified = !apiReachable || hwStatus == null

  return {
    platformReachability: {
      apiReachable: Boolean(apiReachable),
      wsReachable: Boolean(wsConnected),
    },
    hardwareCapability: {
      realHardwareSupported,
      simulationAvailable,
      capabilityUnverified,
    },
    sessionConnection: {
      connected: sessionConnected,
      disconnected: !sessionConnected,
    },
    executionMode,
  }
}

/** Long-form hardware capability (no implication that disconnected means no instrument). */
export function getHardwareCapabilitySentence(truth) {
  const { hardwareCapability, sessionConnection, platformReachability } = truth
  if (!platformReachability.apiReachable) {
    return 'Hardware capability unverified (control API unreachable).'
  }
  if (hardwareCapability.capabilityUnverified) {
    return 'Hardware capability unverified (no status payload yet).'
  }
  if (sessionConnection.connected) {
    return truth.executionMode === 'simulation'
      ? 'Simulation mode active (software stand-in for the instrument path).'
      : 'Real instrument session active (non-simulation control session).'
  }
  if (hardwareCapability.realHardwareSupported) {
    return 'Real instrument path supported — session currently disconnected.'
  }
  return 'Session disconnected — real vs simulated instrument path not yet confirmed this session.'
}

export function getSessionConnectionSentence(truth) {
  if (!truth.platformReachability.apiReachable) {
    return 'Control session unknown (API unreachable).'
  }
  return truth.sessionConnection.connected
    ? 'Control session connected.'
    : 'Control session disconnected.'
}

export function getExecutionModeSentence(truth) {
  switch (truth.executionMode) {
    case 'real':
      return 'Run mode: real instrument (non-simulation).'
    case 'simulation':
      return 'Run mode: simulation.'
    default:
      return 'Run mode: unverified (no active non-sim session to certify the path).'
  }
}

/** Compact labels for header / cockpit badges (English-only). */
export function getTruthCompactLabels(truth) {
  const { platformReachability, hardwareCapability, sessionConnection, executionMode } = truth

  const api = platformReachability.apiReachable ? { abbr: 'API', ok: true } : { abbr: 'API', ok: false }
  const ws = platformReachability.wsReachable ? { abbr: 'WS', ok: true } : { abbr: 'WS', ok: false }

  let hwAbbr = 'HW'
  let hwTitle = 'Hardware capability'
  if (!platformReachability.apiReachable) {
    hwAbbr = 'HW:?'
    hwTitle = 'Hardware capability unverified (API down)'
  } else if (hardwareCapability.capabilityUnverified) {
    hwAbbr = 'HW:?'
    hwTitle = 'Hardware capability unverified'
  } else if (sessionConnection.connected && executionMode === 'simulation') {
    hwAbbr = 'HW:sim'
    hwTitle = 'Simulation mode active'
  } else if (sessionConnection.connected && executionMode === 'real') {
    hwAbbr = 'HW:live'
    hwTitle = 'Real instrument session'
  } else if (hardwareCapability.realHardwareSupported) {
    hwAbbr = 'HW:live·off'
    hwTitle = 'Real instrument path supported; session disconnected'
  } else {
    hwAbbr = 'HW:unk'
    hwTitle = 'Disconnected — instrument path not confirmed this session'
  }

  const sessAbbr = sessionConnection.connected ? 'Sess:on' : 'Sess:off'
  const sessTitle = sessionConnection.connected ? 'Control session connected' : 'Control session disconnected'

  let execAbbr = 'Run:?'
  let execTitle = 'Run mode unverified'
  if (executionMode === 'real') {
    execAbbr = 'Run:live'
    execTitle = 'Run mode: real instrument'
  } else if (executionMode === 'simulation') {
    execAbbr = 'Run:sim'
    execTitle = 'Run mode: simulation'
  }

  return {
    api,
    ws,
    hardware: { abbr: hwAbbr, title: hwTitle },
    session: { abbr: sessAbbr, title: sessTitle },
    execution: { abbr: execAbbr, title: execTitle },
  }
}

/** Badge style for cockpit header (background / text utility classes). */
export function getExecutionModeBadgeTone(truth) {
  if (truth.executionMode === 'real') {
    return { className: 'bg-emerald-500/25 text-emerald-100 border border-emerald-400/40', label: 'Run: live instrument' }
  }
  if (truth.executionMode === 'simulation') {
    return { className: 'bg-amber-500/25 text-amber-100 border border-amber-400/40', label: 'Run: simulation' }
  }
  return { className: 'bg-slate-500/25 text-slate-200 border border-slate-400/30', label: 'Run: unverified' }
}
