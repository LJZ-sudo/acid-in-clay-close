import { useMemo } from 'react'
import { Link } from 'react-router-dom'

function fmt(v, digits = 3) {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  return Number(v).toFixed(digits)
}

function fmtSci(v) {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  return Number(v).toExponential(2)
}

/**
 * Top-3 trials by combined_score. Each row links to /samples/:id when a
 * sample_id is recorded in trial.metadata; otherwise it falls back to the
 * generic trial id (no link).
 */
function Top3Table({ trials = [] }) {
  const rows = useMemo(() => {
    return trials
      .filter((t) => Number.isFinite(Number(t?.objectives?.combined_score)))
      .slice()
      .sort((a, b) => Number(b.objectives.combined_score) - Number(a.objectives.combined_score))
      .slice(0, 3)
  }, [trials])

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="text-xs font-semibold text-gray-700 mb-2">Top-3 by combined_score</div>
      {rows.length === 0 ? (
        <div className="text-xs text-gray-400">No scored trials yet.</div>
      ) : (
        <table className="w-full text-xs tabular-nums">
          <thead>
            <tr className="text-gray-500 border-b border-gray-100">
              <th className="text-left font-normal py-1">#</th>
              <th className="text-left font-normal py-1">sample / trial</th>
              <th className="text-right font-normal py-1">R</th>
              <th className="text-right font-normal py-1">N</th>
              <th className="text-right font-normal py-1">σ_RT (S/cm)</th>
              <th className="text-right font-normal py-1">score</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t, i) => {
              const sampleId = t?.metadata?.sample_id
              const ident = sampleId || `trial_${t?.trial_id}`
              const label = sampleId ? (
                <Link to={`/samples/${encodeURIComponent(sampleId)}`} className="text-primary-600 hover:underline">
                  {sampleId}
                </Link>
              ) : (
                <span className="text-gray-700 font-mono">{ident}</span>
              )
              return (
                <tr key={`${t.trial_id}-${i}`} className="border-b border-gray-50">
                  <td className="py-1 text-gray-400">{i + 1}</td>
                  <td className="py-1">{label}</td>
                  <td className="py-1 text-right">{fmt(t.parameters?.R, 3)}</td>
                  <td className="py-1 text-right">{fmt(t.parameters?.N, 3)}</td>
                  <td className="py-1 text-right">{fmtSci(t.objectives?.conductivity_room_temp_S_cm)}</td>
                  <td className="py-1 text-right font-semibold">{fmt(t.objectives?.combined_score, 3)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default Top3Table
