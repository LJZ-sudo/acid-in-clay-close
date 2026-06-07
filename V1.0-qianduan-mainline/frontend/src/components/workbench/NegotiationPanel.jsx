import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { formatR2OrNA } from '../../features/runEvents/qcDisplay'

function whyItMatters(t, event) {
  const type = String(event?.type || '').toUpperCase()
  if (!type) return t('workbench.why.default')
  if (type.includes('TRIGGER_FINE_SCAN') || type.includes('DENSIFY')) return t('workbench.why.densify')
  if (type.includes('BACKTRACK')) return t('workbench.why.backtrack')
  if (type.includes('RE_MEASURE') || type.includes('RETEST')) return t('workbench.why.retest')
  if (type.includes('RISK_CHECKED') || type.includes('QC')) return t('workbench.why.qualityGate')
  if (type.includes('ACTION_EXECUTED')) return t('workbench.why.actionBound')
  return t('workbench.why.default')
}

function MessageCard({ title, message, colorClass, onViewEvidence, why, t }) {
  return (
    <div className={`border rounded-lg p-3 ${colorClass}`}>
      <div className="text-xs font-semibold uppercase tracking-wide">{title}</div>
      <div className="mt-2 text-sm break-words">{message?.text || '—'}</div>
      <div className="mt-1 text-xs text-gray-600">
        {message?.payload?.rationale || message?.payload?.reason || message?.payload?.comment || '—'}
      </div>
      <div className="mt-2 text-xs text-indigo-700">
        <span className="font-semibold">{t('workbench.whyItMattersLabel')}:</span> {why}
      </div>
      <div className="mt-2 text-xs text-gray-500 flex items-center gap-2">
        <span>#{message?.seq ?? '—'}</span>
        <span>{message?.ts || '—'}</span>
        {message?.evidence_id && (
          <button
            type="button"
            className="text-blue-600 hover:underline"
            onClick={() => onViewEvidence?.(message.evidence_id)}
          >
            {message.evidence_id}
          </button>
        )}
      </div>
    </div>
  )
}

function NegotiationPanel({ negotiation = {}, qc = {}, risk = {}, onViewEvidence }) {
  const { t } = useTranslation()

  const warning = useMemo(() => {
    const grade = String(qc?.qc_grade || '').toUpperCase()
    const riskDecision = String(risk?.decision || '').toUpperCase()

    if (riskDecision === 'DENY' || riskDecision === 'CLAMPED') {
      return {
        level: 'danger',
        text: t('workbench.riskBlocked'),
      }
    }

    if (['C', 'D', 'UNKNOWN'].includes(grade) || qc?.qc_status === 'QC_FAIL' || qc?.qc_status === 'QC_UNKNOWN') {
      return {
        level: 'warning',
        text: qc?.retest_recommended ? t('workbench.retestScheduled') : t('workbench.lowQualityWarning'),
      }
    }

    return null
  }, [qc, risk, t])

  return (
    <div className="card p-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm">{t('workbench.negotiation')}</h3>
        <div className="text-xs text-gray-500">{t('workbench.plannerCriticOrchestrator')}</div>
      </div>

      <div className="grid grid-cols-1 gap-2">
        <MessageCard
          title={t('workbench.plannerProposal')}
          message={negotiation?.planner}
          onViewEvidence={onViewEvidence}
          colorClass="bg-blue-50 border-blue-200"
          why={whyItMatters(t, negotiation?.planner)}
          t={t}
        />
        <MessageCard
          title={t('workbench.criticReview')}
          message={negotiation?.critic}
          onViewEvidence={onViewEvidence}
          colorClass="bg-amber-50 border-amber-200"
          why={whyItMatters(t, negotiation?.critic)}
          t={t}
        />
        <MessageCard
          title={t('workbench.orchestratorDecision')}
          message={negotiation?.orchestrator}
          onViewEvidence={onViewEvidence}
          colorClass="bg-emerald-50 border-emerald-200"
          why={whyItMatters(t, negotiation?.orchestrator)}
          t={t}
        />
      </div>

      {warning && (
        <div className={`mt-3 rounded border p-2 text-xs ${warning.level === 'danger' ? 'border-red-300 bg-red-50 text-red-700' : 'border-amber-300 bg-amber-50 text-amber-700'}`}>
          {warning.text}
        </div>
      )}

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">{t('qc.grade')}</div>
          <div className="font-semibold">{qc?.qc_grade || 'UNKNOWN'}</div>
        </div>
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">{t('qc.r2')}</div>
          <div className="font-semibold">{formatR2OrNA(qc?.r2)}</div>
        </div>
      </div>
    </div>
  )
}

export default NegotiationPanel
