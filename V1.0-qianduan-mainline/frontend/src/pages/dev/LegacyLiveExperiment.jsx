import { useEffect, useState } from 'react'
import { dataApi } from '../../api/data'
import { useDataStore, useUIStore, useAgentStore } from '../../stores'
import TemperatureChart from '../../components/charts/TemperatureChart'
import ConductivityChart from '../../components/charts/ConductivityChart'
import PhysicalWorldColumn from '../../components/cockpit/PhysicalWorldColumn'
import AgentBrainColumn from '../../components/cockpit/AgentBrainColumn'
import ScientificRuntimeColumn from '../../components/cockpit/ScientificRuntimeColumn'
import ConnectPanel from '../../components/cockpit/ConnectPanel'
import AgentDecisionPanel from '../../components/cockpit/AgentDecisionPanel'
import PhaseDetectionPanel from '../../components/cockpit/PhaseDetectionPanel'
import TemperatureDisplay from '../../components/cockpit/TemperatureDisplay'
import NyquistPlaceholder from '../../components/cockpit/NyquistPlaceholder'
import AgentTriadStatus from '../../components/cockpit/AgentTriadStatus'
import HITLBoundaryBadge from '../../components/cockpit/HITLBoundaryBadge'
import MeasurementMetrics from '../../components/cockpit/MeasurementMetrics'
import { getHitlRuntimePill } from '../../utils/hitlLabels'
import { getExecutionModeBadgeTone } from '../../utils/systemTruthModel'
import { useWiredHitlExplicitApproval } from '../../hooks/useWiredHitlExplicitApproval'
import { useSystemTruth } from '../../hooks/useSystemTruth'

const emptyHintClass = 'text-sm text-gray-500 text-center py-4 px-2 leading-relaxed'
const emptySubClass = 'text-xs text-gray-400 mt-1 block'

function LiveExperiment() {
  const [measurements, setMeasurements] = useState([])
  const [measurementsLoading, setMeasurementsLoading] = useState(true)
  const { temperatureHistory, conductivityHistory } = useDataStore()
  const { experimentRunning } = useUIStore()
  const { autoDecisionEnabled } = useAgentStore()
  const explicitHumanApproved = useWiredHitlExplicitApproval(12000)
  const storeHasData = temperatureHistory.length > 0 || conductivityHistory.length > 0
  const truth = useSystemTruth(4000)
  const executionBadge = getExecutionModeBadgeTone(truth)

  useEffect(() => {
    const load = async () => {
      setMeasurementsLoading(true)
      try {
        const resp = await dataApi.getMeasurements({ limit: 200 })
        const data = resp?.data?.measurements || resp?.data?.data || []
        setMeasurements(data)

        if (!storeHasData && data.length > 0) {
          const store = useDataStore.getState()
          data.forEach(m => {
            if (m.temperature_C != null) {
              store.addTemperaturePoint({ value: m.temperature_C, target: null, timestamp: m.timestamp || Date.now() })
            }
            if (m.conductivity_S_cm != null) {
              store.addConductivityPoint({
                step_idx: m.step_idx,
                value: m.conductivity_S_cm,
                temperature_C: m.temperature_C,
                timestamp: m.timestamp || Date.now(),
              })
            }
          })
          if (data.length > 0) {
            const last = data[data.length - 1]
            store.setTemperature(last.temperature_C, null)
          }
        }
      } catch { /* ignore */ }
      finally {
        setMeasurementsLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 4000)
    return () => clearInterval(interval)
  }, [storeHasData])

  const latestMeasurement = measurements.length > 0 ? measurements[measurements.length - 1] : null
  const hitlPill = getHitlRuntimePill(experimentRunning, autoDecisionEnabled, explicitHumanApproved)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-900 to-blue-700 rounded-xl p-5 text-white flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Runtime Cockpit -Physical â†?Agent â†?Science</h1>
          <p className="text-blue-200 text-sm mt-1">Automated EIS measurement with Agent-driven adaptive sampling</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold ${executionBadge.className}`}
            title={executionBadge.label}
          >
            {executionBadge.label}
          </span>
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold ${
              !experimentRunning
                ? 'bg-gray-500/20 text-gray-300'
                : autoDecisionEnabled
                  ? 'bg-green-500/20 text-green-200'
                  : 'bg-amber-500/20 text-amber-200'
            }`}
            title={hitlPill.label}
          >
            HITL: {hitlPill.label}
          </span>
        </div>
      </div>

      {/* Three-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Physical World */}
        <PhysicalWorldColumn>
          <ConnectPanel />
          <TemperatureDisplay />
          <TemperatureChart height={180} />
          <NyquistPlaceholder />
        </PhysicalWorldColumn>

        {/* Center: Agent Brain */}
        <AgentBrainColumn>
          <AgentTriadStatus explicitHumanApproved={explicitHumanApproved} />
          <AgentDecisionPanel />
          <HITLBoundaryBadge explicitHumanApproved={explicitHumanApproved} />
        </AgentBrainColumn>

        {/* Right: Scientific Runtime */}
        <ScientificRuntimeColumn>
          <ConductivityChart height={180} />
          <PhaseDetectionPanel />
          <MeasurementMetrics latestMeasurement={latestMeasurement} />
        </ScientificRuntimeColumn>
      </div>

      {/* Bottom: Measurement Table -always show shell + empty row when no data */}
      <div className="bg-white rounded-xl border p-4 w-full">
        <h3 className="font-semibold mb-2">Recent Measurements</h3>
        <div className="overflow-auto max-h-48">
          <table className="w-full text-xs table-fixed">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-2 py-1.5 w-[8%]">#</th>
                <th className="text-left px-2 py-1.5 w-[12%]">T (C)</th>
                <th className="text-left px-2 py-1.5 w-[14%]">Rb (Î©)</th>
                <th className="text-left px-2 py-1.5 w-[18%]">Ïƒ (S/cm)</th>
                <th className="text-left px-2 py-1.5 w-[12%]">RÂ²</th>
                <th className="text-left px-2 py-1.5 w-[10%]">QC</th>
                <th className="text-left px-2 py-1.5 min-w-0 w-[22%]">Method</th>
              </tr>
            </thead>
            <tbody>
              {measurementsLoading && measurements.length === 0 ? (
                <tr className="border-t">
                  <td colSpan={7} className="px-2 py-6 text-center text-gray-500">
                    Loading measurements-                    <span className={emptySubClass}>HTTP poll + WebSocket may both update this list.</span>
                  </td>
                </tr>
              ) : null}
              {!measurementsLoading && measurements.length === 0 ? (
                <tr className="border-t">
                  <td colSpan={7} className="px-2 py-6 text-center text-gray-500">
                    <span className="italic">No measurements yet</span>
                    <span className={emptySubClass}>Connect hardware (or simulation) and start a run to populate rows.</span>
                  </td>
                </tr>
              ) : null}
              {measurements.length > 0
                ? measurements.slice(-15).reverse().map((m, i) => (
                  <tr key={i} className="border-t hover:bg-gray-50">
                    <td className="px-2 py-1 font-mono">{m.step_idx ?? i}</td>
                    <td className="px-2 py-1 font-mono">{m.temperature_C?.toFixed(1)}</td>
                    <td className="px-2 py-1 font-mono">{m.rb_ohm?.toFixed(2) ?? '--'}</td>
                    <td className="px-2 py-1 font-mono">{m.conductivity_S_cm ? m.conductivity_S_cm.toExponential(3) : '--'}</td>
                    <td className="px-2 py-1 font-mono">{m.r2?.toFixed(4) ?? '--'}</td>
                    <td className="px-2 py-1">
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                        m.qc_grade === 'A' ? 'bg-green-100 text-green-700' :
                        m.qc_grade === 'B' ? 'bg-blue-100 text-blue-700' :
                        m.qc_grade === 'C' ? 'bg-amber-100 text-amber-700' :
                        'bg-red-100 text-red-700'
                      }`}>{m.qc_grade || '--'}</span>
                    </td>
                    <td className="px-2 py-1 text-gray-500 min-w-0 align-top">
                      <span className="block truncate font-mono" title={m.fit_method || ''}>
                        {m.fit_method || '--'}
                      </span>
                    </td>
                  </tr>
                ))
                : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default LiveExperiment
