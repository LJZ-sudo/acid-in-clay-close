import { Link } from 'react-router-dom'

/**
 * Recent runs with primary navigation to read-only Run Replay skeleton.
 * Does not reuse old expandable RunsList — expansion duplicated Run Replay concerns; links are the product contract.
 */
function RecentRunsPanel({ runs = [] }) {
  const slice = runs.slice(0, 10)

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-900 mb-1">Recent runs</h3>
      <p className="text-xs text-gray-500 mb-3">Open the read-only replay page for any run (no player controls).</p>
      <ul className="space-y-2 max-h-80 overflow-y-auto">
        {slice.length === 0 && (
          <li className="text-xs text-gray-500 py-2">No runs returned from GET /runs.</li>
        )}
        {slice.map((run) => {
          const id = run.run_id
          return (
            <li key={id}>
              <Link
                to={`/runs/${encodeURIComponent(String(id))}`}
                className="block rounded-lg border border-gray-100 bg-gray-50 hover:bg-indigo-50 hover:border-indigo-200 px-3 py-2 transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-gray-900 truncate" title={id}>{id}</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0 ${
                      run.status === 'completed'
                        ? 'bg-green-100 text-green-800'
                        : run.status === 'running'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    {run.status || 'unknown'}
                  </span>
                </div>
                <div className="text-[11px] text-gray-500 mt-1 font-mono">
                  {run.created_at ? run.created_at.slice(0, 19) : '—'} · mode: {run.mode || run.profile || '—'}
                </div>
              </Link>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default RecentRunsPanel
