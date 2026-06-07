import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import AgentStatusRow from './AgentStatusRow'
import NegotiationPanel from './NegotiationPanel'
import EventTimeline from './EventTimeline'
import EvidenceDrawer from './EvidenceDrawer'
import { formatDateTime, formatLocaleNumber } from '../../utils/localeFormat'
import { formatR2OrNA } from '../../features/runEvents/qcDisplay'

function downloadTextFile(filename, content, mime = 'text/plain') {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function buildTraceSummary({ runId, state, selectedEvent, selectedEvidence }) {
  const summary = {
    run_id: runId,
    exported_at: new Date().toISOString(),
    last_seq: state?.last_seq || 0,
    qc: state?.qc_state || null,
    risk: state?.risk_state || null,
    negotiation: {
      planner: state?.negotiation?.planner || null,
      critic: state?.negotiation?.critic || null,
      orchestrator: state?.negotiation?.orchestrator || null,
    },
    selected_event: selectedEvent || null,
    selected_evidence: selectedEvidence || null,
    evidence_index: state?.evidence_index || [],
  }

  const lines = []
  lines.push('# Agent Trace Summary')
  lines.push('')
  lines.push(`- run_id: ${summary.run_id || '--'}`)
  lines.push(`- exported_at: ${summary.exported_at}`)
  lines.push(`- last_seq: ${summary.last_seq}`)
  lines.push('')
  lines.push('## Negotiation')
  lines.push('')
  lines.push(`- planner: ${summary.negotiation.planner?.text || '--'}`)
  lines.push(`- critic: ${summary.negotiation.critic?.text || '--'}`)
  lines.push(`- orchestrator: ${summary.negotiation.orchestrator?.text || '--'}`)
  lines.push('')
  lines.push('## Evidence')
  lines.push('')
  lines.push(`- selected evidence_id: ${summary.selected_evidence?.evidence_id || '--'}`)
  lines.push(`- selected event: ${summary.selected_event?.type || '--'} @ seq ${summary.selected_event?.seq || '--'}`)

  return {
    json: summary,
    markdown: lines.join('\n'),
  }
}

function AgentTeamWorkbench({ runId, state, collapsed = false, onEvidenceLoaded }) {
  const { t } = useTranslation()

  const [selectedEvent, setSelectedEvent] = useState(null)
  const [selectedEvidenceId, setSelectedEvidenceId] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)

  const latestByAgent = useMemo(() => {
    const map = {}
    const rows = state?.events || []
    for (let i = rows.length - 1; i >= 0; i -= 1) {
      const evt = rows[i]
      if (!evt?.source) continue
      if (!map[evt.source]) {
        map[evt.source] = evt
      }
    }
    return map
  }, [state?.events])

  const selectedEvidence = selectedEvidenceId ? state?.evidence_by_id?.[selectedEvidenceId] : null

  const openEvidenceById = (evidenceId) => {
    if (!evidenceId) return
    setSelectedEvidenceId(evidenceId)
    setDrawerOpen(true)
  }

  const openFromEvent = (event) => {
    setSelectedEvent(event)
    if (event?.evidence_id) {
      setSelectedEvidenceId(event.evidence_id)
      setDrawerOpen(true)
    }
  }

  const exportSummary = () => {
    const summary = buildTraceSummary({ runId, state, selectedEvent, selectedEvidence })
    downloadTextFile(`agent_trace_summary_${runId || 'run'}.md`, summary.markdown, 'text/markdown')
    downloadTextFile(`agent_trace_summary_${runId || 'run'}.json`, JSON.stringify(summary.json, null, 2), 'application/json')
  }

  const latestArrheniusUpdate = state?.arrhenius_state?.updated_at || null
  const latestBreakpointCount = Array.isArray(state?.arrhenius_state?.breakpoints) ? state.arrhenius_state.breakpoints.length : 0
  const latestSegmentCount = Array.isArray(state?.arrhenius_state?.segments) ? state.arrhenius_state.segments.length : 0

  if (collapsed) {
    return (
      <div className="card p-3 text-sm text-gray-600">
        {t('workbench.collapsedHint')}
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col gap-3 min-h-0">
      <AgentStatusRow
        statusMap={state?.agent_status || {}}
        latestByAgent={latestByAgent}
        onOpenEvidence={openEvidenceById}
      />

      <NegotiationPanel
        negotiation={state?.negotiation || {}}
        qc={state?.qc_state || {}}
        risk={state?.risk_state || {}}
        onViewEvidence={openEvidenceById}
      />

      <div className="card p-3 text-xs grid grid-cols-2 gap-2">
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">{t('workbench.arrheniusSegments')}</div>
          <div className="font-semibold">{formatLocaleNumber(latestSegmentCount, { maximumFractionDigits: 0 })}</div>
        </div>
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">{t('workbench.breakpointCandidates')}</div>
          <div className="font-semibold">{formatLocaleNumber(latestBreakpointCount, { maximumFractionDigits: 0 })}</div>
        </div>
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">{t('workbench.phaseJumpScore')}</div>
          <div className="font-semibold">{formatLocaleNumber(state?.phase_state?.latest_score, { maximumFractionDigits: 4 })}</div>
        </div>
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">{t('workbench.r2Display')}</div>
          <div className="font-semibold">{formatR2OrNA(state?.qc_state?.r2)}</div>
        </div>
        <div className="col-span-2 border border-gray-200 rounded p-2">
          <div className="text-gray-500">{t('common.updatedAt')}</div>
          <div className="font-semibold">{formatDateTime(latestArrheniusUpdate)}</div>
        </div>
      </div>

      <EventTimeline
        events={state?.events || []}
        activeSeq={state?.last_seq || 0}
        onSelectEvent={openFromEvent}
        onOpenEvidence={openEvidenceById}
      />

      <div className="card p-3 flex items-center justify-between gap-2 text-xs">
        <div>
          <div className="font-semibold">{t('workbench.auditabilityFirst')}</div>
          <div className="text-gray-600">{t('workbench.auditabilityHint')}</div>
        </div>
        <button type="button" className="btn-secondary text-xs" onClick={exportSummary}>
          {t('workbench.exportTraceSummary')}
        </button>
      </div>

      <EvidenceDrawer
        runId={runId}
        open={drawerOpen}
        evidenceId={selectedEvidenceId}
        selectedEvent={selectedEvent}
        evidence={selectedEvidence}
        onClose={() => setDrawerOpen(false)}
        onLoaded={(detail) => {
          onEvidenceLoaded?.(detail)
          if (!detail?.evidence_id) return
          const event = state?.events?.find((evt) => evt?.evidence_id === detail.evidence_id)
          if (event) setSelectedEvent(event)
        }}
      />
    </div>
  )
}

export default AgentTeamWorkbench
