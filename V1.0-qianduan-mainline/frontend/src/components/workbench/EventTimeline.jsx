import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDateTime } from '../../utils/localeFormat'

const ROW_HEIGHT = 66
const VIEWPORT_HEIGHT = 320

const KIND_COLOR = {
  run_state: 'border-gray-200 bg-gray-50',
  agent_message: 'border-indigo-200 bg-indigo-50',
  tool_started: 'border-blue-200 bg-blue-50',
  tool_finished: 'border-emerald-200 bg-emerald-50',
  qc_result: 'border-amber-200 bg-amber-50',
  phase_jump: 'border-red-200 bg-red-50',
  safety: 'border-rose-200 bg-rose-50',
  evidence_generated: 'border-cyan-200 bg-cyan-50',
  other: 'border-gray-200 bg-white',
}

function EventTimeline({ events = [], activeSeq = 0, onSelectEvent, onOpenEvidence }) {
  const { t } = useTranslation()
  const [scrollTop, setScrollTop] = useState(0)

  const sorted = useMemo(() => {
    const rows = [...events]
    rows.sort((a, b) => Number(b.seq || 0) - Number(a.seq || 0))
    return rows
  }, [events])

  const totalHeight = sorted.length * ROW_HEIGHT
  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - 6)
  const endIndex = Math.min(sorted.length, Math.ceil((scrollTop + VIEWPORT_HEIGHT) / ROW_HEIGHT) + 6)
  const visible = sorted.slice(startIndex, endIndex)

  return (
    <div className="card p-3 min-h-0 flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm">{t('workbench.eventTimeline')}</h3>
        <span className="text-xs text-gray-500">{sorted.length}</span>
      </div>

      <div
        className="overflow-auto border border-gray-200 rounded"
        style={{ height: VIEWPORT_HEIGHT }}
        onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
      >
        <div style={{ height: totalHeight, position: 'relative' }}>
          {visible.map((event, idx) => {
            const index = startIndex + idx
            const top = index * ROW_HEIGHT
            const active = Number(event.seq || 0) === Number(activeSeq || 0)

            return (
              <button
                key={`${event.seq}-${event.type}-${index}`}
                type="button"
                onClick={() => onSelectEvent?.(event)}
                className={`absolute left-0 right-0 text-left border rounded mx-2 p-2 transition ${KIND_COLOR[event.kind] || KIND_COLOR.other} ${active ? 'ring-2 ring-blue-400' : 'hover:ring-1 hover:ring-gray-300'}`}
                style={{ top, height: ROW_HEIGHT - 6 }}
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold">#{event.seq || '—'} {event.type}</span>
                  <span className="text-gray-500">{event.source}</span>
                </div>
                <div className="text-[11px] text-gray-600 truncate">
                  {event.payload?.reason || event.payload?.message || event.payload?.summary || '—'}
                </div>
                <div className="flex items-center justify-between text-[11px] text-gray-500 mt-1">
                  <span>{formatDateTime(event.ts)}</span>
                  <span>
                    {t('common.step')}: {event.step_idx ?? '—'}
                    {event.evidence_id ? (
                      <span
                        role="button"
                        tabIndex={0}
                        className="ml-2 text-blue-600 hover:underline"
                        onClick={(e) => {
                          e.stopPropagation()
                          onOpenEvidence?.(event.evidence_id)
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            e.stopPropagation()
                            onOpenEvidence?.(event.evidence_id)
                          }
                        }}
                      >
                        {t('workbench.viewEvidence')}
                      </span>
                    ) : null}
                  </span>
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default EventTimeline
