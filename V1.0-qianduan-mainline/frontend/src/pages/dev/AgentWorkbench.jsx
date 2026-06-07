import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { mainAgentApi } from '../../api/mainAgent'
import { agentsApi } from '../../api/agents'
import { runsAuditApi } from '../../api/runsAudit'
import { useAgentStore, useUIStore } from '../../stores'
import { useWiredHitlExplicitApproval } from '../../hooks/useWiredHitlExplicitApproval'
import DecisionTimeline from '../../components/agentOs/DecisionTimeline'
import AgentOsTriad from '../../components/agentOs/AgentOsTriad'
import RecentRunsPanel from '../../components/agentOs/RecentRunsPanel'
import AgentOsCapabilities from '../../components/agentOs/AgentOsCapabilities'
import ApprovalQueuePanel from '../../components/agentOs/ApprovalQueuePanel'

function HeroHitlLines({ experimentRunning, autoDecisionEnabled, explicitHumanApproved }) {
  const autonomy = autoDecisionEnabled ? 'Auto (autonomous proposals enabled)' : 'Human required (autonomy off)'
  if (!experimentRunning) {
    return (
      <div className="text-xs text-indigo-100/90 space-y-1 mt-2">
        <p>Experiment loop: <strong>idle</strong> -HITL pill on Header reflects runtime only.</p>
        <p>Autonomy setting: <strong>{autonomy}</strong></p>
        <p>
          Human gate (explicit API field):{' '}
          {explicitHumanApproved === true ? 'approved' : explicitHumanApproved === false ? 'not approved' : 'not exposed -do not confuse AI Critic with human approval.'}
        </p>
      </div>
    )
  }
  return (
    <div className="text-xs text-indigo-100/90 space-y-1 mt-2">
      <p>Experiment loop: <strong>active</strong></p>
      <p>Autonomy: <strong>{autonomy}</strong></p>
      <p>
        Human gate (explicit API field):{' '}
        {explicitHumanApproved === true ? (
          <strong>Human approved (wired)</strong>
        ) : explicitHumanApproved === false ? (
          <strong>Not approved</strong>
        ) : (
          <span>Not exposed by API -showing <strong>Human required</strong> when autonomy is off; AI Critic labels in the timeline are not human sign-off.</span>
        )}
      </p>
    </div>
  )
}

function AgentWorkbench() {
  const { experimentRunning } = useUIStore()
  const { autoDecisionEnabled, runId: storeRunId } = useAgentStore()
  const explicitHumanApproved = useWiredHitlExplicitApproval(12000)

  const [agentsStatus, setAgentsStatus] = useState({ agents: [] })
  const [agentStatus, setAgentStatus] = useState(null)
  const [stats, setStats] = useState(null)
  const [decisions, setDecisions] = useState([])
  const [runs, setRuns] = useState([])
  const [capData, setCapData] = useState(null)
  const [capError, setCapError] = useState(null)
  const [capLoading, setCapLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [ag, multi, st] = await Promise.allSettled([
          mainAgentApi.getStatus(),
          agentsApi.getStatus(),
          agentsApi.getStats(),
        ])
        if (ag.status === 'fulfilled') {
          const data = ag.value?.data
          setAgentStatus(data)
          setDecisions(data?.latest_decisions || data?.decisions || [])
        }
        if (multi.status === 'fulfilled') setAgentsStatus(multi.value?.data || { agents: [] })
        if (st.status === 'fulfilled') setStats(st.value?.data)
      } catch { /* ignore */ }
    }
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    runsAuditApi.listRuns().then((r) => setRuns(r?.data?.runs || [])).catch(() => setRuns([]))
  }, [])

  useEffect(() => {
    let cancelled = false
    setCapLoading(true)
    agentsApi
      .getCapabilities()
      .then((r) => {
        if (!cancelled) {
          setCapData(r?.data || null)
          setCapError(null)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setCapData(null)
          setCapError(e.response?.data?.detail || e.message || 'request failed')
        }
      })
      .finally(() => {
        if (!cancelled) setCapLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const actionDist = stats?.action_distribution || {}
  const activeRunId = agentStatus?.run_id || agentStatus?.current_run_id || storeRunId || null
  const latestDecision = decisions.length ? decisions[decisions.length - 1] : null

  const microById = useMemo(
    () => ({
      planner: agentStatus?.plannerAgent,
      critic: agentStatus?.criticAgent,
      orchestrator: agentStatus?.mainAgent,
    }),
    [agentStatus]
  )

  const triggerDecide = async () => {
    try {
      const resp = await mainAgentApi.decide({})
      setDecisions((prev) => [...prev, resp?.data].filter(Boolean))
    } catch (e) {
      window.alert(`Decision failed: ${e?.message || 'unknown error'}`)
    }
  }

  return (
    <div className="space-y-6">
      {/* A. Hero */}
      <div className="bg-gradient-to-r from-slate-900 to-indigo-900 rounded-xl p-6 text-white">
        <h1 className="text-2xl font-bold tracking-tight">Agent OS</h1>
        <p className="text-sm text-indigo-100/90 mt-1 max-w-3xl leading-relaxed">
          Planner–critic–orchestrator decision system for closed-loop EIS research -status, decisions, runs, and human
          boundaries in one place.
        </p>
        <div className="flex flex-wrap gap-x-6 gap-y-2 mt-4 text-sm">
          <span>
            Current status: <strong className="font-mono">{agentStatus?.status || 'idle'}</strong>
          </span>
          <span>
            Recent decision count: <strong>{stats?.total_decisions ?? decisions.length}</strong>
          </span>
          <span className="flex items-center gap-2 flex-wrap">
            Active run:
            {activeRunId ? (
              <Link
                to={`/runs/${encodeURIComponent(String(activeRunId))}`}
                className="font-mono text-amber-200 hover:text-white underline underline-offset-2"
              >
                {activeRunId}
              </Link>
            ) : (
              <strong className="text-indigo-200">none</strong>
            )}
          </span>
        </div>
        <HeroHitlLines
          experimentRunning={experimentRunning}
          autoDecisionEnabled={autoDecisionEnabled}
          explicitHumanApproved={explicitHumanApproved}
        />
      </div>

      {/* B. Triad */}
      <AgentOsTriad
        agents={agentsStatus.agents || []}
        microById={microById}
        latestDecision={latestDecision}
      />

      {/* C. Main body */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8 space-y-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
              <h2 className="text-sm font-semibold text-gray-900">Decision timeline</h2>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(actionDist).map(([action, count]) => (
                  <span key={action} className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-700 font-mono">
                    {action}: {count}
                  </span>
                ))}
              </div>
            </div>
            <DecisionTimeline decisions={decisions} />
          </div>
        </div>

        <div className="lg:col-span-4 space-y-4">
          <RecentRunsPanel runs={runs} />

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-1">Agent configuration</h3>
            <p className="text-xs text-gray-500 mb-3">From GET /agent/status config (read-only display).</p>
            <dl className="space-y-2 text-xs">
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500">Model</dt>
                <dd className="font-mono text-right">{agentStatus?.config?.model || '-'}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500">Fallback</dt>
                <dd className="font-mono text-right">{agentStatus?.config?.fallback || '-'}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500">Phase threshold</dt>
                <dd className="font-mono text-right">{agentStatus?.config?.phase_threshold ?? '-'}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500">QC retest grades</dt>
                <dd className="font-mono text-right">
                  {(agentStatus?.config?.qc_retest_grades || []).join(', ') || '-'}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500">Max retests</dt>
                <dd className="font-mono text-right">{agentStatus?.config?.max_retest_count ?? '-'}</dd>
              </div>
            </dl>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-1">Manual decision / trigger</h3>
            <p className="text-xs text-gray-500 mb-3">POST /agent/decide -one planner–critic–orchestrator cycle.</p>
            <button
              type="button"
              className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium transition-colors"
              onClick={triggerDecide}
            >
              Trigger agent decision
            </button>
          </div>

          <ApprovalQueuePanel />

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-2">Tool &amp; capability map (light)</h3>
            <p className="text-xs text-gray-500 mb-3">GET /agents/capabilities -no activation graph.</p>
            <AgentOsCapabilities data={capData} error={capError} loading={capLoading} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default AgentWorkbench
