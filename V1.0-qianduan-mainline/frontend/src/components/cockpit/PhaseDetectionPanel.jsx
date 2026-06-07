import { useEffect, useMemo, useState } from 'react'
import { dataApi } from '../../api/data'
import { useDataStore } from '../../stores'
import ReactECharts from 'echarts-for-react'

const emptyBody = 'text-sm text-gray-500 text-center py-6 px-2 leading-relaxed'
const emptySub = 'text-xs text-gray-400 mt-1 block'

/** ln(σT) vs 1000/T from live SocketIO measurement stream (no mid-run segmentation). */
function arrheniusScatterFromMeasurements(measurements) {
  return (measurements || [])
    .filter((m) => {
      const T_C = m.T_C ?? m.temperature_C ?? m.temperature
      const sigma = m.sigma_S_cm ?? m.conductivity_S_cm ?? m.conductivity
      return T_C != null && sigma != null && sigma > 0
    })
    .map((m) => {
      const T_C = m.T_C ?? m.temperature_C ?? m.temperature
      const sigma = m.sigma_S_cm ?? m.conductivity_S_cm ?? m.conductivity
      const T_K = T_C + 273.15
      return [1000 / T_K, Math.log(sigma * T_K)]
    })
}

function PhaseDetectionPanel() {
  const [phases, setPhases] = useState([])
  const [phaseLoad, setPhaseLoad] = useState('loading')
  const measurements = useDataStore((s) => s.measurements)
  const arrheniusData = useMemo(
    () => arrheniusScatterFromMeasurements(measurements),
    [measurements],
  )

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const r = await dataApi.getPhaseTransitions()
        if (!alive) return
        setPhases(r?.data?.phase_transitions || r?.data?.transitions || [])
        setPhaseLoad('ok')
      } catch {
        if (alive) setPhaseLoad('unavailable')
      }
    }
    load()
    const interval = setInterval(load, 5000)
    return () => {
      alive = false
      clearInterval(interval)
    }
  }, [])

  const arrheniusOption = {
    animation: false,
    grid: { left: 55, right: 15, top: 15, bottom: 35 },
    xAxis: { type: 'value', name: '1000/T (1/K)', nameTextStyle: { fontSize: 10 } },
    yAxis: { type: 'value', name: 'ln(σT)', nameTextStyle: { fontSize: 10 } },
    series: [{
      type: 'scatter',
      symbolSize: 6,
      itemStyle: { color: '#0284c7' },
      data: arrheniusData,
    }],
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border p-4">
        <h3 className="font-semibold mb-2">Arrhenius (current run, scatter only)</h3>
        {arrheniusData.length > 0 ? (
          <ReactECharts option={arrheniusOption} style={{ height: 220 }} />
        ) : (
          <div className={emptyBody}>
            No σ(T) points in the live stream yet.
            <span className={emptySub}>Segmented fits appear after Stage0 on the Analysis page (saved sample).</span>
          </div>
        )}
      </div>
      <div className="bg-white rounded-xl border p-4">
        <h3 className="font-semibold mb-2">Phase Transitions</h3>
        {phaseLoad === 'loading' ? (
          <div className={emptyBody}>Loading phase list…</div>
        ) : phaseLoad === 'unavailable' ? (
          <div className={emptyBody}>
            Phase transition list unavailable
            <span className={emptySub}>Check data API reachability.</span>
          </div>
        ) : phases.length > 0 ? (
          <div className="space-y-1">
            {phases.map((p, i) => (
              <div key={i} className="text-xs px-2 py-1.5 bg-red-50 rounded-lg border border-red-100 flex justify-between">
                <span className="font-semibold text-red-700">Phase transition at {p.temperature_C?.toFixed(1) || '--'}°C</span>
                <span className="text-gray-400">{p.temperature_K?.toFixed(1) || '--'} K</span>
              </div>
            ))}
          </div>
        ) : (
          <div className={emptyBody}>
            No phase transitions detected yet.
            <span className={emptySub}>The detector runs on incoming measurement stream; none recorded in this session.</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default PhaseDetectionPanel
