import { useMemo, useState } from 'react'
import { normalizeRunEventForReplay } from '../../utils/runReplayLoader'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'physical', label: 'Physical' },
  { id: 'agent', label: 'Agent' },
  { id: 'science', label: 'Science' },
]

const CAT_BORDER = {
  physical: 'border-l-4 border-l-emerald-500',
  agent: 'border-l-4 border-l-indigo-500',
  science: 'border-l-4 border-l-violet-500',
}

/**
 * Lightweight, English-only event list for product Run Replay (read-only).
 * Workbench `EventTimeline` was not reused: it depends on i18n keys, virtualized
 * absolute positioning tied to `kind`/`source` shapes, and demo-oriented copy.
 */
function RunEventList({ events = [], selectedSeq, onSelect }) {
  const [filter, setFilter] = useState('all')

  const normalized = useMemo(
    () => (Array.isArray(events) ? events.map((e, i) => normalizeRunEventForReplay(e, i)) : []),
    [events]
  )

  const filtered = useMemo(() => {
    if (filter === 'all') return normalized
    return normalized.filter((e) => e.category === filter)
  }, [normalized, filter])

  return (
    <div className="bg-white rounded-xl border border-gray-200 flex flex-col min-h-0 max-h-[calc(100vh-12rem)]">
      <div className="p-3 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-900">Event timeline</h2>
        <p className="text-xs text-gray-500 mt-0.5">Read-only skeleton — not a replay player.</p>
        <div className="flex flex-wrap gap-1.5 mt-3">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                filter === f.id ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {filtered.length === 0 ? (
          <p className="text-sm text-gray-500 px-2 py-6 text-center">No events match this filter.</p>
        ) : (
          filtered.map((e) => {
            const active = selectedSeq != null && Number(e.seq) === Number(selectedSeq)
            return (
              <button
                key={`${e.seq}-${e.type}-${e.ts}`}
                type="button"
                onClick={() => onSelect?.(e.raw, e.seq)}
                className={`w-full text-left rounded-lg border p-2.5 transition ${CAT_BORDER[e.category] || ''} ${
                  active ? 'ring-2 ring-blue-500 bg-blue-50/50 border-blue-200' : 'border-gray-200 bg-white hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-mono font-semibold text-gray-800">
                    #{e.seq} · {e.type}
                  </span>
                  <span className="text-gray-400 shrink-0 truncate max-w-[40%]" title={e.ts || ''}>
                    {e.ts || '—'}
                  </span>
                </div>
                <p className="text-[11px] text-gray-600 mt-1 line-clamp-2">{e.summary}</p>
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}

export default RunEventList
