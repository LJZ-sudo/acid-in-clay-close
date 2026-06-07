function stageBorderClass(status) {
  if (status === 'unavailable') return 'border-dashed border-gray-300 border-2 bg-gray-50/80'
  if (!status || status === 'idle') return 'border-gray-200'
  if (status === 'completed') return 'border-green-400'
  if (status === 'running') return 'border-blue-500 ring-2 ring-blue-200'
  if (status === 'failed' || status === 'error' || status === 'timeout') return 'border-red-400'
  return 'border-gray-300'
}

function DualLoopStatic({ innerLoopStats = {}, outerLoopStats = {}, stageStatus = {}, measurementPathHint = '' }) {
  const s0 = stageBorderClass(stageStatus.stage0)
  const s1 = stageBorderClass(stageStatus.stage1)
  const s2 = stageBorderClass(stageStatus.stage2)
  const s3 = stageBorderClass(stageStatus.stage3)

  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Dual Closed-Loop Architecture</h2>
      {measurementPathHint ? (
        <p className="text-xs text-gray-600 bg-gray-50 border border-gray-100 rounded-lg px-3 py-2 mb-3 leading-relaxed">
          {measurementPathHint}
        </p>
      ) : null}
      <div className="grid grid-cols-2 gap-4">
        {/* Inner Loop */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-blue-600 font-semibold text-sm">Inner Loop (Stage 0 ↔ 1)</span>
            <span className="text-xs text-blue-400">Single-sample optimization</span>
          </div>
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className={`bg-white border-2 rounded-lg px-4 py-2 text-center ${s0}`}>
              <div className="text-xs text-gray-500">Stage 0</div>
              <div className="text-sm font-semibold text-blue-700">Measurement</div>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-xs text-blue-500">Agent decides</span>
              <div className="flex items-center gap-0.5 text-blue-400">
                <span>◄</span>
                <span className="w-8 h-0.5 bg-blue-300 inline-block" />
                <span>►</span>
              </div>
            </div>
            <div className={`bg-white border-2 rounded-lg px-4 py-2 text-center ${s1}`}>
              <div className="text-xs text-gray-500">Stage 1</div>
              <div className="text-sm font-semibold text-blue-700">Optimization</div>
            </div>
          </div>
          <div className="flex gap-4 text-sm">
            <div className="bg-white rounded px-3 py-1.5 border border-blue-100">
              <span className="text-gray-500">Measurements:</span>
              <span className="font-mono ml-1 font-semibold">{innerLoopStats.measurements ?? 0}</span>
            </div>
            <div className="bg-white rounded px-3 py-1.5 border border-blue-100">
              <span className="text-gray-500">Phase transitions:</span>
              <span className="font-mono ml-1 font-semibold">{innerLoopStats.phaseTransitions ?? 0}</span>
            </div>
          </div>
        </div>

        {/* Outer Loop */}
        <div className="bg-purple-50 border border-purple-200 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-purple-600 font-semibold text-sm">Outer Loop (Stage 2 → 3)</span>
            <span className="text-xs text-purple-400">Family-level discovery</span>
          </div>
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className={`bg-white border-2 rounded-lg px-4 py-2 text-center ${s2}`}>
              <div className="text-xs text-gray-500">Stage 2</div>
              <div className="text-sm font-semibold text-purple-700">Statistics</div>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-xs text-purple-500">Evidence</span>
              <div className="flex items-center gap-0.5 text-purple-400">
                <span className="w-8 h-0.5 bg-purple-300 inline-block" />
                <span>►</span>
              </div>
            </div>
            <div className={`bg-white border-2 rounded-lg px-4 py-2 text-center ${s3}`}>
              <div className="text-xs text-gray-500">Stage 3</div>
              <div className="text-sm font-semibold text-purple-700">Mechanism</div>
            </div>
          </div>
          <div className="flex gap-4 text-sm">
            <div className="bg-white rounded px-3 py-1.5 border border-purple-100">
              <span className="text-gray-500">Samples:</span>
              <span className="font-mono ml-1 font-semibold">{outerLoopStats.samples ?? 0}</span>
            </div>
            <div className="bg-white rounded px-3 py-1.5 border border-purple-100">
              <span className="text-gray-500">Reports:</span>
              <span className="font-mono ml-1 font-semibold">{outerLoopStats.reports ?? 0}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DualLoopStatic
