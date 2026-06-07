import { useEffect, useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { controlApi } from '../../api/control'
import { dataApi } from '../../api/data'
import { mainAgentApi } from '../../api/mainAgent'
import { agentsApi } from '../../api/agents'
import client from '../../api/client'
import { useUIStore } from '../../stores'
import {
  deriveSystemTruthModel,
  getHardwareCapabilitySentence,
  getSessionConnectionSentence,
  getExecutionModeSentence,
} from '../../utils/systemTruthModel'
import FiveAxisSummary from '../../components/command/FiveAxisSummary'
import DualLoopStatic from '../../components/command/DualLoopStatic'
import SystemStatusBar from '../../components/command/SystemStatusBar'
import AgentTicker from '../../components/command/AgentTicker'
import CommandActivitySnapshot from '../../components/command/CommandActivitySnapshot'

const STAGE_KEYS = ['stage0', 'stage1', 'stage2', 'stage3']

function PipelineOverview() {
  const { experimentRunning, wsConnected } = useUIStore()
  const [hwStatus, setHwStatus] = useState(null)
  const [controlApiReachable, setControlApiReachable] = useState(true)
  const [agentStatus, setAgentStatus] = useState(null)
  const [experiments, setExperiments] = useState([])
  const [pipelineStatus, setPipelineStatus] = useState({})
  const [phaseTransitions, setPhaseTransitions] = useState([])
  const [agentStats, setAgentStats] = useState({})
  const [agentsHealth, setAgentsHealth] = useState(null)
  const [telemetryReachable, setTelemetryReachable] = useState(true)

  useEffect(() => {
    const load = async () => {
      const results = await Promise.allSettled([
        controlApi.getStatus(),
        mainAgentApi.getStatus(),
        dataApi.getExperiments(),
        client.get('/pipeline/status').catch(() => null),
        dataApi.getPhaseTransitions().catch(() => null),
        agentsApi.getStats().catch(() => null),
        agentsApi.healthCheck().catch(() => null),
      ])
      const coreOk =
        results[0].status === 'fulfilled'
        || results[1].status === 'fulfilled'
        || results[2].status === 'fulfilled'
      setTelemetryReachable(coreOk)
      if (results[0].status === 'fulfilled') {
        setHwStatus(results[0].value?.data ?? null)
        setControlApiReachable(true)
      } else {
        setHwStatus(null)
        setControlApiReachable(false)
      }
      if (results[1].status === 'fulfilled') setAgentStatus(results[1].value?.data)
      if (results[2].status === 'fulfilled') setExperiments(results[2].value?.data?.experiments || [])
      if (results[3].status === 'fulfilled' && results[3].value?.data) setPipelineStatus(results[3].value.data)
      if (results[4].status === 'fulfilled' && results[4].value?.data) {
        const pt = results[4].value.data
        setPhaseTransitions(Array.isArray(pt) ? pt : pt?.phase_transitions || pt?.transitions || [])
      }
      if (results[5].status === 'fulfilled' && results[5].value?.data) setAgentStats(results[5].value.data)
      if (results[6].status === 'fulfilled' && results[6].value?.data) setAgentsHealth(results[6].value.data)
    }
    load()
    const interval = setInterval(load, 8000)
    return () => clearInterval(interval)
  }, [])

  const agentDecisions = agentStatus?.latest_decisions || agentStatus?.decisions || []

  const truth = useMemo(
    () => deriveSystemTruthModel({ wsConnected, apiReachable: controlApiReachable, hwStatus }),
    [wsConnected, controlApiReachable, hwStatus]
  )

  const measurementPathHint = [
    getHardwareCapabilitySentence(truth),
    getSessionConnectionSentence(truth),
    getExecutionModeSentence(truth),
  ].join(' ')

  const telemetryDetailLine = telemetryReachable
    ? 'At least one of control, agent, or experiments API responded in the last poll.'
    : 'Control, agent, and experiments bundle did not all respond -counts may be incomplete.'

  const hardwareModeSnapshot = `${getExecutionModeSentence(truth)} ${getHardwareCapabilitySentence(truth)}`

  const fiveAxisMetrics = useMemo(() => ({
    hwAutomation: {
      primary: getExecutionModeSentence(truth),
      secondary: `${hwStatus?.measurement_count || 0} measurements · ${getSessionConnectionSentence(truth)}`,
    },
    phaseDetection: {
      primary: `${phaseTransitions.length || hwStatus?.phase_transitions || 0} transitions`,
      secondary: `${agentDecisions.filter(d => d.action === 'TRIGGER_FINE_SCAN').length} fine-scans`,
    },
    agentOptimization: {
      primary: `${agentStats?.total_decisions || agentDecisions.length} decisions`,
      secondary: agentStats?.by_agent
        ? `P ${agentStats.by_agent.planner || 0} / C ${agentStats.by_agent.critic || 0} / O ${agentStats.by_agent.orchestrator || 0}`
        : 'Planner / Critic / Orch',
    },
    evidenceDiscovery: {
      primary: 'Evidence layer not indexed',
      secondary: 'No Stage 2 output file feed in this UI yet.',
    },
    materialPrediction: {
      primary: 'Discovery layer not indexed',
      secondary: 'No Stage 3 output file feed in this UI yet.',
    },
  }), [hwStatus, agentDecisions, phaseTransitions, agentStats, truth])

  const innerLoopStats = useMemo(() => ({
    measurements: hwStatus?.measurement_count || 0,
    phaseTransitions: phaseTransitions.length || hwStatus?.phase_transitions || 0,
  }), [hwStatus, phaseTransitions])

  const outerLoopStats = useMemo(() => ({
    samples: experiments.length,
    reports: experiments.length,
  }), [experiments])

  const systemAgentStats = useMemo(() => ({
    healthy: agentsHealth?.healthy === true
      || (agentStatus?.status === 'running' || agentStatus?.status === 'idle'),
    totalDecisions: agentStats?.total_decisions ?? agentDecisions.length,
    activeRun: agentStatus?.run_id || null,
  }), [agentStatus, agentDecisions, agentStats, agentsHealth])

  const hasPipelineApiData = useMemo(() => {
    if (!pipelineStatus || typeof pipelineStatus !== 'object') return false
    return STAGE_KEYS.some((k) => {
      const block = pipelineStatus[k]
      const st = block?.status
      return st != null && String(st).length > 0
    })
  }, [pipelineStatus])

  const { pipelineStageStatus, pipelineSource } = useMemo(() => {
    if (!hasPipelineApiData) {
      return {
        pipelineStageStatus: {
          stage0: 'unavailable',
          stage1: 'unavailable',
          stage2: 'unavailable',
          stage3: 'unavailable',
        },
        pipelineSource: 'unavailable',
      }
    }
    return {
      pipelineStageStatus: {
        stage0: pipelineStatus?.stage0?.status || 'idle',
        stage1: pipelineStatus?.stage1?.status || 'idle',
        stage2: pipelineStatus?.stage2?.status || 'idle',
        stage3: pipelineStatus?.stage3?.status || 'idle',
      },
      pipelineSource: 'api',
    }
  }, [hasPipelineApiData, pipelineStatus])

  return (
    <div className="space-y-6">
      {/* Hero Banner */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-700 rounded-xl p-6 text-white">
        <h1 className="text-2xl font-bold tracking-tight">CLOSE -AI-Agent-Driven Closed-Loop EIS Research System</h1>
        <p className="text-slate-300 mt-1">Autonomous dual-loop electrochemical impedance spectroscopy platform with intelligent decision-making</p>
        <div className="mt-4 space-y-2 text-sm text-slate-200">
          <p className="leading-snug">{getHardwareCapabilitySentence(truth)}</p>
          <p className="leading-snug text-slate-300">{getSessionConnectionSentence(truth)} · {getExecutionModeSentence(truth)}</p>
          <div className="flex flex-wrap gap-x-6 gap-y-2 pt-1">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${agentStatus?.status === 'running' ? 'bg-green-400 animate-pulse' : 'bg-gray-500'}`} />
              <span>Agent service: {agentStatus?.status || 'idle'}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-400" />
              <span>LLM: {agentStatus?.config?.model || 'gpt-5.4'} via {agentStatus?.config?.api_provider || 'openrouter'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Five Innovation Axes */}
      <FiveAxisSummary metrics={fiveAxisMetrics} />

      {/* Dual Closed-Loop */}
      <DualLoopStatic
        innerLoopStats={innerLoopStats}
        outerLoopStats={outerLoopStats}
        stageStatus={pipelineStageStatus}
        measurementPathHint={measurementPathHint}
      />

      <CommandActivitySnapshot
        pipelineSource={pipelineSource}
        experimentCount={experiments.length}
        phaseTransitionCount={phaseTransitions.length}
        agentDecisionCount={agentStats?.total_decisions ?? agentDecisions.length}
        activeRunId={agentStatus?.run_id || agentStatus?.current_run_id || null}
        experimentRunningHint={experimentRunning}
        telemetryReachable={telemetryReachable}
        hardwareModeLine={hardwareModeSnapshot}
        telemetryLine={telemetryDetailLine}
      />

      {/* Agent Ticker + Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <AgentTicker decisions={agentDecisions} />
        </div>

        <div className="space-y-3">
          <Link to="/experiment" className="block bg-blue-600 hover:bg-blue-700 text-white rounded-xl p-4 text-center transition-colors">
            <div className="font-semibold">Start Experiment</div>
            <div className="text-blue-200 text-xs mt-1">Stage 0: Live measurement</div>
          </Link>
          <Link to="/agent" className="block bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl p-4 text-center transition-colors">
            <div className="font-semibold">Agent Workbench</div>
            <div className="text-indigo-200 text-xs mt-1">Decision history & audit</div>
          </Link>
          <Link to="/analysis" className="block bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl p-4 text-center transition-colors">
            <div className="font-semibold">Analysis Hub</div>
            <div className="text-emerald-200 text-xs mt-1">Reports & statistics</div>
          </Link>
        </div>
      </div>

      {/* System Status Bar */}
      <SystemStatusBar
        pipelineStatus={pipelineStageStatus}
        pipelineSource={pipelineSource}
        experimentCount={experiments.length}
        agentStats={systemAgentStats}
      />
    </div>
  )
}

export default PipelineOverview
