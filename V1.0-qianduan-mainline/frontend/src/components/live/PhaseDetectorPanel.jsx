/**
 * PhaseDetectorPanel — surfaces PHASE_TRANSITION_DETECTED events emitted by
 * stage0_measurement/modules/analysis/phase_detect.py during an online run.
 *
 * Each transition is rendered with its temperature and (optional) confidence;
 * the panel also shows the running count so the researcher can decide whether
 * to trigger a fine-scan or stop the run early.
 */
function fmt(v, digits = 2) {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  return Number(v).toFixed(digits)
}

function PhaseDetectorPanel({ transitions = [] }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-semibold text-gray-700">Phase Transitions (online)</div>
        <span className="text-[10px] text-gray-400">{transitions.length} detected</span>
      </div>
      {transitions.length === 0 ? (
        <div className="text-xs text-gray-400">
          Online change-point detector is monitoring σ(T) — no transition reported yet.
        </div>
      ) : (
        <ul className="space-y-1.5 text-xs">
          {transitions.slice(-8).reverse().map((t, i) => (
            <li
              key={`${t.temperature_C ?? t.temperature_K ?? i}-${i}`}
              className="flex items-center justify-between border-b border-gray-100 last:border-b-0 py-1"
            >
              <span className="font-mono text-gray-700">
                T = {fmt(t.temperature_C, 1)} °C
                {t.temperature_K != null && (
                  <span className="text-gray-400 ml-1">({fmt(t.temperature_K, 1)} K)</span>
                )}
              </span>
              <span className="text-gray-500">
                {t.confidence != null && <span className="mr-2">conf {fmt(t.confidence, 2)}</span>}
                {t.method && <span className="text-[10px] text-indigo-600 font-mono">{t.method}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default PhaseDetectorPanel
