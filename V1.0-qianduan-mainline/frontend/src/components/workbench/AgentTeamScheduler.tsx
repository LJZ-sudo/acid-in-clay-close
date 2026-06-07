import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import AgentStatusRow from './AgentStatusRow'
import EventTimeline from './EventTimeline'
import EvidenceDrawer from './EvidenceDrawer'
import {
  SCHEDULER_NODE_META,
  SCHEDULER_NODE_ORDER,
  initialSchedulerState,
} from '../../features/runEvents/schedulerReducer.js'
import { initialRunEventsState } from '../../features/runEvents/reducer.js'
import { loadJsonlFile, replayStep } from '../../features/runEvents/demoReplay.js'
import { formatDateTime, formatLocaleNumber } from '../../utils/localeFormat'
import { formatR2OrNA } from '../../features/runEvents/qcDisplay'
import './AgentTeamScheduler.css'

const STATUS_CLASS = {
  idle: 'agent-scheduler-status-idle',
  running: 'agent-scheduler-status-running',
  success: 'agent-scheduler-status-success',
  failed: 'agent-scheduler-status-failed',
  blocked: 'agent-scheduler-status-blocked',
}

const AGENT_LABEL_KEY = {
  orchestrator: 'domain.orchestrator',
  planner: 'domain.planner',
  critic: 'domain.critic',
  controller_adapter: 'domain.controllerAdapter',
  analysis_agent: 'domain.analysisAgent',
  acquisition_agent: 'domain.acquisitionAgent',
}

function cloneStateForReplay(runId = '') {
  return {
    ...initialRunEventsState,
    run_id: runId,
    telemetry: { ...initialRunEventsState.telemetry },
    arrhenius_state: { ...initialRunEventsState.arrhenius_state },
    phase_state: { ...initialRunEventsState.phase_state, points: [] },
    qc_state: { ...initialRunEventsState.qc_state },
    risk_state: { ...initialRunEventsState.risk_state },
    negotiation: { ...initialRunEventsState.negotiation },
    agent_status: { ...initialRunEventsState.agent_status },
    measurement_points: [],
    agent_messages: [],
    tool_timeline: [],
    events: [],
    evidence_index: [],
    evidence_by_id: {},
    seen_keys: {},
    scheduler: {
      ...initialSchedulerState,
      nodes: Object.fromEntries(
        Object.entries(initialSchedulerState.nodes || {}).map(([k, v]) => [k, { ...v }])
      ),
    },
  }
}

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
    scheduler: state?.scheduler || null,
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
  lines.push('# AgentTeam Scheduler Trace Summary')
  lines.push('')
  lines.push(`- run_id: ${summary.run_id || '--'}`)
  lines.push(`- exported_at: ${summary.exported_at}`)
  lines.push(`- last_seq: ${summary.last_seq}`)
  lines.push('')
  lines.push('## Negotiation')
  lines.push(`- planner: ${summary.negotiation.planner?.text || '--'}`)
  lines.push(`- critic: ${summary.negotiation.critic?.text || '--'}`)
  lines.push(`- orchestrator: ${summary.negotiation.orchestrator?.text || '--'}`)
  lines.push('')
  lines.push('## Evidence')
  lines.push(`- selected evidence_id: ${summary.selected_evidence?.evidence_id || '--'}`)
  lines.push(`- selected event: ${summary.selected_event?.type || '--'} @ seq ${summary.selected_event?.seq || '--'}`)

  return {
    json: summary,
    markdown: lines.join('\n'),
  }
}

function NegotiationStrip({ negotiation, onOpenEvidence }) {
  const { t } = useTranslation()

  const planner = negotiation?.planner || null
  const critic = negotiation?.critic || null
  const orchestrator = negotiation?.orchestrator || null

  const renderBlock = (titleKey, message, tooltipKey) => (
    <div className="agent-scheduler-negotiation-card">
      <div className="agent-scheduler-negotiation-header">
        <span className="font-semibold text-xs uppercase tracking-wide">{t(titleKey)}</span>
        <span className="agent-scheduler-tip" title={t(tooltipKey)}>?</span>
      </div>
      <div className="text-sm font-medium mt-1 break-words">{message?.type || t('common.none')}</div>
      <div className="text-xs text-gray-600 mt-1 break-words">
        {message?.payload?.reason || message?.payload?.rationale || message?.text || t('common.none')}
      </div>
      <div className="text-[11px] text-gray-500 mt-1 flex items-center gap-2">
        <span>#{message?.seq ?? '—'}</span>
        {message?.evidence_id && (
          <button className="text-blue-600 hover:underline" type="button" onClick={() => onOpenEvidence?.(message.evidence_id)}>
            {message.evidence_id}
          </button>
        )}
      </div>
    </div>
  )

  return (
    <div className="card p-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm">{t('workbench.negotiationStrip')}</h3>
        <div className="text-xs text-gray-500">{t('workbench.plannerCriticOrchestrator')}</div>
      </div>
      <div className="agent-scheduler-negotiation-strip">
        {renderBlock('workbench.plannerProposal', planner, 'workbench.tooltips.phaseJumpPolicy')}
        <div className="agent-scheduler-arrow">→</div>
        {renderBlock('workbench.criticReview', critic, 'workbench.tooltips.retestPolicy')}
        <div className="agent-scheduler-arrow">→</div>
        {renderBlock('workbench.orchestratorDecision', orchestrator, 'workbench.tooltips.actionBinding')}
      </div>
    </div>
  )
}

function PipelineNodeGrid({ scheduler, onNodeClick }) {
  const { t } = useTranslation()

  const nodes = useMemo(() => {
    const nodeMap = scheduler?.nodes || {}
    return SCHEDULER_NODE_ORDER.map((id) => ({
      id,
      ...SCHEDULER_NODE_META[id],
      ...(nodeMap[id] || { status: 'idle' }),
    }))
  }, [scheduler?.nodes])

  return (
    <div className="card p-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm">{t('workbench.pipelineTitle')}</h3>
        <div className="text-xs text-gray-500">{t('workbench.pipelineHint')}</div>
      </div>

      <div className="agent-scheduler-pipeline-grid">
        {nodes.map((node) => {
          const active = node.id === scheduler?.active_node_id
          const statusClass = STATUS_CLASS[node.status] || STATUS_CLASS.idle
          const agentKey = AGENT_LABEL_KEY[node.responsible_agent] || 'common.unknown'

          return (
            <button
              key={node.id}
              type="button"
              className={`agent-scheduler-node ${active ? 'agent-scheduler-node-active' : ''}`}
              onClick={() => onNodeClick?.(node)}
              title={
                node.id === 'transition'
                  ? t('workbench.tooltips.phaseJumpPolicy')
                  : node.id === 'qc_rb'
                    ? t('workbench.tooltips.retestPolicy')
                    : t('workbench.tooltips.auditability')
              }
            >
              <div className="flex items-center justify-between gap-2">
                <div className="font-semibold text-sm text-left">{t(node.titleKey)}</div>
                <span className={`agent-scheduler-status ${statusClass}`}>
                  {t(`workbench.pipelineStatus.${node.status}`, { defaultValue: node.status })}
                </span>
              </div>

              <div className="text-xs text-gray-600 mt-1 text-left">{t(node.opsKey)}</div>

              <div className="text-[11px] text-gray-500 mt-2 text-left">
                <div>{t('workbench.responsibleAgent')}: {t(agentKey)}</div>
                <div>{t('common.step')}: {node.step_idx ?? '—'}</div>
                <div>{t('common.updatedAt')}: {formatDateTime(node.last_ts)}</div>
              </div>

              {(node.warning_key || node.recommendation_key) && (
                <div className="agent-scheduler-warning mt-2 text-left">
                  {node.warning_key ? t(node.warning_key) : null}
                  {node.warning_key && node.recommendation_key ? ' | ' : ''}
                  {node.recommendation_key ? t(node.recommendation_key) : null}
                </div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function AgentTeamScheduler({ runId, state, collapsed = false, onEvidenceLoaded }) {
  const { t } = useTranslation()

  const [selectedEvent, setSelectedEvent] = useState(null)
  const [selectedEvidenceId, setSelectedEvidenceId] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)

  const [demoMode, setDemoMode] = useState(false)
  const [demoFileName, setDemoFileName] = useState('')
  const [demoErrors, setDemoErrors] = useState([])
  const [replayEvents, setReplayEvents] = useState([])
  const [replayCursor, setReplayCursor] = useState(0)
  const [replaySpeed, setReplaySpeed] = useState(1)
  const [replayPlaying, setReplayPlaying] = useState(false)
  const [replayState, setReplayState] = useState(() => cloneStateForReplay(runId || ''))

  const effectiveState = demoMode ? replayState : (state || {})
  const scheduler = effectiveState?.scheduler || initialSchedulerState

  useEffect(() => {
    if (!demoMode) return
    setReplayState(cloneStateForReplay(runId || replayState?.run_id || ''))
    setReplayCursor(0)
    setReplayPlaying(false)
  }, [demoMode, runId])

  const stepReplay = useCallback(() => {
    setReplayCursor((cursor) => {
      const evt = replayEvents[cursor]
      if (!evt) {
        setReplayPlaying(false)
        return cursor
      }

      setReplayState((prev) => replayStep(prev, evt, evt?.run_id || runId || prev?.run_id || ''))
      const nextCursor = cursor + 1
      if (nextCursor >= replayEvents.length) {
        setReplayPlaying(false)
      }
      return nextCursor
    })
  }, [replayEvents, runId])

  useEffect(() => {
    if (!demoMode || !replayPlaying) return undefined
    const delay = Math.max(120, 700 / Math.max(0.5, Number(replaySpeed || 1)))
    const timer = window.setInterval(() => {
      stepReplay()
    }, delay)
    return () => window.clearInterval(timer)
  }, [demoMode, replayPlaying, replaySpeed, stepReplay])

  const latestByAgent = useMemo(() => {
    const map = {}
    const rows = effectiveState?.events || []
    for (let i = rows.length - 1; i >= 0; i -= 1) {
      const evt = rows[i]
      if (!evt?.source) continue
      if (!map[evt.source]) {
        map[evt.source] = evt
      }
    }
    return map
  }, [effectiveState?.events])

  const selectedEvidence = selectedEvidenceId ? effectiveState?.evidence_by_id?.[selectedEvidenceId] : null
  const activeAgentId = scheduler?.active_node_id
    ? scheduler?.nodes?.[scheduler.active_node_id]?.responsible_agent || ''
    : ''


  const openEvidenceById = useCallback((evidenceId) => {
    if (!evidenceId) return
    setSelectedEvidenceId(evidenceId)
    setDrawerOpen(true)
  }, [])

  const openFromEvent = useCallback((event) => {
    setSelectedEvent(event)
    if (event?.evidence_id) {
      setSelectedEvidenceId(event.evidence_id)
      setDrawerOpen(true)
    }
  }, [])

  const handleNodeClick = useCallback((node) => {
    if (!node) return
    if (node.evidence_id) {
      openEvidenceById(node.evidence_id)
      return
    }

    const events = effectiveState?.events || []
    const found = [...events].reverse().find((evt) => {
      if (!evt) return false
      const sameStep = node.step_idx !== null && node.step_idx !== undefined && Number(evt.step_idx) === Number(node.step_idx)
      return sameStep || String(evt.type || '').toUpperCase() === String(node.last_event_type || '').toUpperCase()
    })

    if (found) {
      openFromEvent(found)
      setDrawerOpen(true)
    }
  }, [effectiveState?.events, openEvidenceById, openFromEvent])

  const handleDemoFile = async (event) => {
    const file = event?.target?.files?.[0]
    if (!file) return

    try {
      const parsed = await loadJsonlFile(file, { fallbackRunId: runId || '' })
      const normalizedRunId = parsed.runId || runId || ''
      setDemoFileName(file.name)
      setDemoErrors(parsed.errors || [])
      setReplayEvents(parsed.events || [])
      setReplayCursor(0)
      setReplayPlaying(false)
      setReplayState(cloneStateForReplay(normalizedRunId))
    } catch {
      setDemoFileName(file.name)
      setDemoErrors([{ line: 0, reason: 'invalid_jsonl_file' }])
      setReplayEvents([])
      setReplayCursor(0)
      setReplayPlaying(false)
      setReplayState(cloneStateForReplay(runId || ''))
    }
  }

  const exportSummary = () => {
    const summary = buildTraceSummary({
      runId: effectiveState?.run_id || runId,
      state: effectiveState,
      selectedEvent,
      selectedEvidence,
    })
    downloadTextFile(`agent_trace_summary_${effectiveState?.run_id || runId || 'run'}.md`, summary.markdown, 'text/markdown')
    downloadTextFile(`agent_trace_summary_${effectiveState?.run_id || runId || 'run'}.json`, JSON.stringify(summary.json, null, 2), 'application/json')
  }

  if (collapsed) {
    return (
      <div className="card p-3 text-sm text-gray-600">
        {t('workbench.collapsedHint')}
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col gap-3 min-h-0">
      <div className="card p-3">
        <div className="text-sm font-semibold">{t('workbench.claimTitle')}</div>
        <div className="text-xs text-gray-600 mt-1">{t('workbench.claimText')}</div>
      </div>

      <div className="card p-3 flex flex-col gap-2 text-xs">
        <div className="flex items-center justify-between gap-3">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={demoMode} onChange={(e) => setDemoMode(e.target.checked)} />
            <span className="font-semibold">{t('workbench.demoMode')}</span>
          </label>

          {demoMode && (
            <div className="flex items-center gap-2">
              <button type="button" className="btn-outline text-xs" onClick={() => setReplayPlaying((v) => !v)} disabled={!replayEvents.length}>
                {replayPlaying ? t('workbench.demoPause') : t('workbench.demoPlay')}
              </button>
              <button type="button" className="btn-outline text-xs" onClick={stepReplay} disabled={!replayEvents.length || replayCursor >= replayEvents.length}>
                {t('workbench.demoStep')}
              </button>
            </div>
          )}
        </div>

        {demoMode && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <input type="file" accept=".jsonl,.txt" onChange={handleDemoFile} className="text-xs" />
              <label className="flex items-center gap-1">
                <span>{t('workbench.demoSpeed')}</span>
                <select value={replaySpeed} onChange={(e) => setReplaySpeed(Number(e.target.value))} className="input py-1 px-2 h-8 text-xs w-20">
                  <option value={0.5}>0.5x</option>
                  <option value={1}>1x</option>
                  <option value={2}>2x</option>
                  <option value={5}>5x</option>
                </select>
              </label>
            </div>
            <div className="text-gray-600">
              {t('workbench.demoFile')}: <span className="font-mono">{demoFileName || '—'}</span>
              {' | '}
              {t('workbench.demoProgress', { current: replayCursor, total: replayEvents.length })}
            </div>
            {demoErrors.length > 0 && (
              <div className="text-amber-700">
                {t('workbench.demoErrors', { count: demoErrors.length })}
              </div>
            )}
          </>
        )}
      </div>

      <AgentStatusRow
        statusMap={effectiveState?.agent_status || {}}
        latestByAgent={latestByAgent}
        activeAgentId={activeAgentId}
        onOpenEvidence={openEvidenceById}
      />

      <NegotiationStrip
        negotiation={effectiveState?.negotiation || {}}
        onOpenEvidence={openEvidenceById}
      />

      <PipelineNodeGrid scheduler={scheduler} onNodeClick={handleNodeClick} />

      {(scheduler?.warning_key || scheduler?.recommendation_key) && (
        <div className="card p-3 text-xs border border-amber-200 bg-amber-50 text-amber-800">
          {scheduler?.warning_key ? t(scheduler.warning_key) : null}
          {scheduler?.warning_key && scheduler?.recommendation_key ? ' | ' : ''}
          {scheduler?.recommendation_key ? t(scheduler.recommendation_key) : null}
        </div>
      )}

      <div className="card p-3 text-xs grid grid-cols-2 gap-2">
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">{t('workbench.arrheniusSegments')}</div>
          <div className="font-semibold">{formatLocaleNumber(effectiveState?.arrhenius_state?.segments?.length || 0, { maximumFractionDigits: 0 })}</div>
        </div>
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">{t('workbench.breakpointCandidates')}</div>
          <div className="font-semibold">{formatLocaleNumber(effectiveState?.arrhenius_state?.breakpoints?.length || 0, { maximumFractionDigits: 0 })}</div>
        </div>
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">{t('workbench.phaseJumpScore')}</div>
          <div className="font-semibold">{formatLocaleNumber(effectiveState?.phase_state?.latest_score, { maximumFractionDigits: 4 })}</div>
        </div>
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">{t('workbench.r2Display')}</div>
          <div className="font-semibold">{formatR2OrNA(effectiveState?.qc_state?.r2)}</div>
        </div>
      </div>

      <EventTimeline
        events={effectiveState?.events || []}
        activeSeq={effectiveState?.last_seq || 0}
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
        runId={effectiveState?.run_id || runId}
        open={drawerOpen}
        evidenceId={selectedEvidenceId}
        selectedEvent={selectedEvent}
        evidence={selectedEvidence}
        onClose={() => setDrawerOpen(false)}
        onLoaded={(detail) => {
          onEvidenceLoaded?.(detail)
          if (!detail?.evidence_id) return
          const event = effectiveState?.events?.find((evt) => evt?.evidence_id === detail.evidence_id)
          if (event) setSelectedEvent(event)
        }}
      />
    </div>
  )
}

export default AgentTeamScheduler
