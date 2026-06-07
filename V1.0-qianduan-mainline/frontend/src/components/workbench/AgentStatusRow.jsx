import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

const STATUS_CLASS = {
  idle: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700',
  waiting: 'bg-slate-100 text-slate-700',
  blocked: 'bg-red-100 text-red-700',
  thinking: 'bg-indigo-100 text-indigo-700',
  acting: 'bg-emerald-100 text-emerald-700',
  observing: 'bg-amber-100 text-amber-700',
}

const CARD_CLASS = {
  idle: 'border-gray-200 bg-white',
  running: 'border-blue-300 bg-blue-50/40 ring-1 ring-blue-200',
  waiting: 'border-slate-300 bg-slate-50/40 ring-1 ring-slate-200',
  blocked: 'border-red-300 bg-red-50/40 ring-1 ring-red-200',
  thinking: 'border-indigo-300 bg-indigo-50/40 ring-1 ring-indigo-200',
  acting: 'border-emerald-300 bg-emerald-50/40 ring-1 ring-emerald-200',
  observing: 'border-amber-300 bg-amber-50/40 ring-1 ring-amber-200',
}

const HOT_STATUS = new Set(['running', 'thinking', 'acting', 'blocked'])

const AGENT_DEFINITIONS = [
  { id: 'orchestrator', labelKey: 'domain.orchestrator', taglineKey: 'workbench.agentTaglines.orchestrator' },
  { id: 'planner', labelKey: 'domain.planner', taglineKey: 'workbench.agentTaglines.planner' },
  { id: 'critic', labelKey: 'domain.critic', taglineKey: 'workbench.agentTaglines.critic' },
  { id: 'controller_adapter', labelKey: 'domain.controllerAdapter', taglineKey: 'workbench.agentTaglines.controllerAdapter' },
  { id: 'analysis_agent', labelKey: 'domain.analysisAgent', taglineKey: 'workbench.agentTaglines.analysisAgent' },
  { id: 'acquisition_agent', labelKey: 'domain.acquisitionAgent', taglineKey: 'workbench.agentTaglines.acquisitionAgent' },
]

function AgentStatusRow({ statusMap = {}, latestByAgent = {}, activeAgentId = '', onOpenEvidence }) {
  const { t } = useTranslation()

  const cards = useMemo(
    () => AGENT_DEFINITIONS.map((agent) => {
      const status = String(statusMap?.[agent.id] || 'idle').toLowerCase()
      const latest = latestByAgent?.[agent.id] || null
      const active = agent.id === activeAgentId || HOT_STATUS.has(status)
      return {
        ...agent,
        status,
        latest,
        active,
      }
    }),
    [activeAgentId, latestByAgent, statusMap]
  )

  return (
    <div className="card p-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm">{t('workbench.agentTeam')}</h3>
        <span className="text-xs text-gray-500">{t('workbench.realtime')}</span>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
        {cards.map((card) => (
          <div
            key={card.id}
            className={`border rounded-lg p-2 transition ${CARD_CLASS[card.status] || CARD_CLASS.idle} ${card.active ? 'shadow-sm' : ''}`}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="text-sm font-semibold truncate flex items-center gap-1.5">
                  {card.active ? <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" /> : null}
                  {t(card.labelKey)}
                </div>
                <div className="text-xs text-gray-600 truncate">{t(card.taglineKey)}</div>
              </div>
              <span className={`text-[11px] px-2 py-0.5 rounded ${STATUS_CLASS[card.status] || STATUS_CLASS.idle}`}>
                {t(`workbench.agentStatus.${card.status}`, { defaultValue: card.status })}
              </span>
            </div>

            <div className="mt-2 text-xs text-gray-700">
              <div>
                <span className="font-semibold">{t('workbench.lastAction')}:</span>{' '}
                {card.latest?.type || t('common.none')}
              </div>
              <div className="text-gray-500">
                {t('common.step')}: {card.latest?.step_idx ?? '—'}
                {' | '}
                {card.latest?.payload?.reason || card.latest?.payload?.message || t('common.none')}
              </div>
              <div className="mt-1">
                <span className="font-semibold">{t('workbench.evidenceLink')}:</span>{' '}
                {card.latest?.evidence_id ? (
                  <button
                    type="button"
                    className="text-blue-600 hover:underline"
                    onClick={() => onOpenEvidence?.(card.latest.evidence_id)}
                  >
                    {card.latest.evidence_id}
                  </button>
                ) : (
                  <span className="text-gray-400">{t('workbench.notLinked')}</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default AgentStatusRow
