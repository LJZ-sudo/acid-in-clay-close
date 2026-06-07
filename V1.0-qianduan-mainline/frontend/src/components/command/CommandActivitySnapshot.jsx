import { Link } from 'react-router-dom'

/**
 * Lightweight activity readout for Command Center (no Stage 2/3 file wiring).
 */
function CommandActivitySnapshot({
  pipelineSource = 'unavailable',
  experimentCount = 0,
  phaseTransitionCount = 0,
  agentDecisionCount = 0,
  activeRunId = null,
  experimentRunningHint = false,
  telemetryReachable = true,
  hardwareModeLine = '',
  telemetryLine = '',
}) {
  const pipelineLabel =
    pipelineSource === 'api'
      ? 'Pipeline stages: from API (in-memory snapshot).'
      : 'Pipeline stages: not indexed in API (no stage rows returned).'

  const telemetryDetail =
    telemetryLine
    || (telemetryReachable
      ? 'Telemetry APIs responded in the last poll.'
      : 'Telemetry partially unreachable — counts may be stale or empty.')

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
      <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wider mb-3">
        Activity Snapshot
      </h2>
      {!telemetryReachable && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">
          Live API snapshot partially unavailable — verify backend and refresh.
        </p>
      )}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
        <div className="bg-white rounded-lg border border-slate-100 p-3">
          <div className="text-xs font-semibold text-slate-500 mb-1">Pipeline source</div>
          <p className="text-slate-800 leading-snug">{pipelineLabel}</p>
          <p className="text-xs text-slate-400 mt-1">Not an evidence → mechanism file feed.</p>
        </div>
        <div className="bg-white rounded-lg border border-slate-100 p-3">
          <div className="text-xs font-semibold text-slate-500 mb-1">Telemetry reachability</div>
          <p className="text-slate-800 leading-snug text-xs">{telemetryDetail}</p>
        </div>
        <div className="bg-white rounded-lg border border-slate-100 p-3">
          <div className="text-xs font-semibold text-slate-500 mb-1">Hardware mode (control API)</div>
          <p className="text-slate-800 leading-snug text-xs">
            {hardwareModeLine || 'Unverified — waiting for control status.'}
          </p>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3 text-sm">
        <div className="bg-white rounded-lg border border-slate-100 p-3 md:col-span-2">
          <div className="text-xs font-semibold text-slate-500 mb-1">Data counts (API)</div>
          <ul className="text-slate-700 space-y-0.5 font-mono text-xs">
            <li>Experiments listed: {telemetryReachable ? experimentCount : '—'}</li>
            <li>Phase transitions: {telemetryReachable ? phaseTransitionCount : '—'}</li>
            <li>Agent decisions (recent window): {telemetryReachable ? agentDecisionCount : '—'}</li>
          </ul>
        </div>
        <div className="bg-white rounded-lg border border-slate-100 p-3">
          <div className="text-xs font-semibold text-slate-500 mb-1">Run</div>
          {activeRunId ? (
            <p className="text-slate-800 font-mono text-xs break-all">
              <span className="text-slate-600">Active / last run id: </span>
              <Link
                to={`/runs/${encodeURIComponent(String(activeRunId))}`}
                className="text-blue-700 hover:underline font-mono"
              >
                {activeRunId}
              </Link>
            </p>
          ) : (
            <p className="text-slate-800 font-mono text-xs break-all">
              {experimentRunningHint
                ? 'Experiment running (no run id on agent status).'
                : 'No active run id reported.'}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export default CommandActivitySnapshot
