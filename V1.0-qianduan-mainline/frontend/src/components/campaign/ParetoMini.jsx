import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'

/**
 * Mini Pareto plot — sigma_RT vs ea_low_temp_eV. Maximise sigma, minimise Ea_low.
 * Pareto-optimal trials are highlighted; the rest fade to gray.
 */
function ParetoMini({ trials = [], paretoIds = [], height = 200 }) {
  const { pareto, others, hasData } = useMemo(() => {
    const paretoSet = new Set(paretoIds)
    const p = []
    const o = []
    for (const t of trials) {
      const sigma = t?.objectives?.conductivity_room_temp_S_cm
      const ea = t?.objectives?.ea_low_temp_eV
      if (!Number.isFinite(Number(sigma)) || !Number.isFinite(Number(ea))) continue
      const point = { value: [Number(sigma), Number(ea)], name: t?.metadata?.sample_id || `trial_${t?.trial_id}` }
      if (paretoSet.has(t?.trial_id)) p.push(point)
      else o.push(point)
    }
    return { pareto: p, others: o, hasData: p.length + o.length > 0 }
  }, [trials, paretoIds])

  const option = useMemo(
    () => ({
      tooltip: {
        trigger: 'item',
        formatter: (p) => `${p.data?.name ?? ''}<br/>σ_RT = ${Number(p.value[0]).toExponential(2)}<br/>Ea_low = ${Number(p.value[1]).toFixed(3)} eV`,
      },
      grid: { left: 40, right: 16, top: 20, bottom: 36, containLabel: true },
      xAxis: { name: 'σ_RT', type: 'log', nameLocation: 'middle', nameGap: 22 },
      yAxis: { name: 'Ea_low (eV)', nameLocation: 'middle', nameGap: 30, type: 'value', inverse: true },
      series: [
        { name: 'others', type: 'scatter', symbolSize: 8, itemStyle: { color: '#cbd5e1' }, data: others },
        {
          name: 'pareto',
          type: 'scatter',
          symbol: 'diamond',
          symbolSize: 12,
          itemStyle: { color: '#3D5AFE' },
          data: pareto,
        },
      ],
    }),
    [pareto, others]
  )

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="text-xs font-semibold text-gray-700 mb-1">Pareto · σ_RT vs Ea_low</div>
      {hasData ? (
        <ReactECharts option={option} style={{ height, width: '100%' }} notMerge lazyUpdate />
      ) : (
        <div className="flex items-center justify-center text-xs text-gray-400" style={{ height }}>
          No σ_RT / Ea_low pairs yet.
        </div>
      )}
    </div>
  )
}

export default ParetoMini
