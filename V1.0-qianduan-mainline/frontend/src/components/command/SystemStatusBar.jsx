function SystemStatusBar({
  pipelineStatus = {},
  experimentCount = 0,
  agentStats = {},
  pipelineSource = 'unavailable',
}) {
  const stages = [
    { key: 'stage0', label: 'S0' },
    { key: 'stage1', label: 'S1' },
    { key: 'stage2', label: 'S2' },
    { key: 'stage3', label: 'S3' },
  ]

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">System Status</h2>
      <div className="flex flex-wrap items-center gap-6 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-gray-500">Pipeline:</span>
          {pipelineSource === 'unavailable' && (
            <span
              className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-0.5"
              title="No stage entries from GET /api/pipeline/status (empty in-memory state)"
            >
              Stage status unavailable
            </span>
          )}
          {pipelineSource === 'api' && (
            <span className="text-xs text-gray-500" title="Values from pipeline API">
              From pipeline API
            </span>
          )}
          {stages.map((s) => {
            const status = pipelineStatus[s.key] || 'idle'
            const color = status === 'unavailable'
              ? 'bg-gray-200 ring-1 ring-dashed ring-gray-400'
              : status === 'completed' ? 'bg-green-500' :
                status === 'running' ? 'bg-blue-500 animate-pulse' :
                  status === 'error' || status === 'failed' || status === 'timeout' ? 'bg-red-500' :
                    'bg-gray-300'
            return (
              <span key={s.key} className="flex items-center gap-1" title={`${s.label}: ${status}`}>
                <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${color}`} />
                <span className="text-xs font-mono">{s.label}</span>
              </span>
            )
          })}
        </div>
        <div className="h-4 w-px bg-gray-300" />
        <div>
          <span className="text-gray-500">Samples:</span>
          <span className="font-mono ml-1 font-semibold">{experimentCount}</span>
        </div>
        <div className="h-4 w-px bg-gray-300" />
        <div>
          <span className="text-gray-500">Agent:</span>
          <span className="ml-1">{agentStats.healthy ? '✓ Healthy' : '— Idle'}</span>
          {agentStats.totalDecisions > 0 && (
            <span className="text-gray-400 ml-2">{agentStats.totalDecisions} decisions</span>
          )}
        </div>
        <div className="h-4 w-px bg-gray-300" />
        <div>
          <span className="text-gray-500">Run:</span>
          <span className="ml-1">{agentStats.activeRun || 'none active'}</span>
        </div>
      </div>
    </div>
  )
}

export default SystemStatusBar
