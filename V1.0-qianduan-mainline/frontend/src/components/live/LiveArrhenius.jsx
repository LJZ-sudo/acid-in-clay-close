import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'

/**
 * LiveArrhenius — ln(σ·T) vs 1000/T scatter, accumulating MEASUREMENT_COMPLETED
 * events as they arrive. The most recent point is highlighted.
 */
function LiveArrhenius({ measurements = [], height = 300 }) {
  const data = useMemo(() => {
    const out = []
    for (const m of measurements) {
      const tC = Number(m?.temperature_C)
      const sigma = Number(m?.conductivity_S_cm)
      if (!Number.isFinite(tC) || !Number.isFinite(sigma) || sigma <= 0) continue
      const tK = tC + 273.15
      out.push([1000 / tK, Math.log(sigma * tK), tC, sigma])
    }
    return out
  }, [measurements])

  const option = useMemo(
    () => ({
      tooltip: {
        trigger: 'item',
        formatter: (p) => {
          const [x, y, tC, sigma] = p.value
          return `1000/T = ${x.toFixed(3)}<br/>ln(σT) = ${y.toFixed(3)}<br/>T = ${tC.toFixed(1)} °C<br/>σ = ${Number(sigma).toExponential(2)} S/cm`
        },
      },
      grid: { left: 50, right: 16, top: 16, bottom: 40, containLabel: true },
      xAxis: { name: '1000/T (1/K)', nameLocation: 'middle', nameGap: 24, type: 'value' },
      yAxis: { name: 'ln(σ·T)', nameLocation: 'middle', nameGap: 36, type: 'value' },
      series: [
        {
          type: 'scatter',
          symbolSize: 8,
          data: data.slice(0, -1),
          itemStyle: { color: '#3D5AFE' },
        },
        {
          type: 'effectScatter',
          symbolSize: 14,
          data: data.slice(-1),
          itemStyle: { color: '#dc2626' },
          rippleEffect: { brushType: 'stroke', scale: 2 },
        },
      ],
    }),
    [data]
  )

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center text-xs text-gray-400" style={{ height }}>
        Waiting for first measurement...
      </div>
    )
  }
  return <ReactECharts option={option} style={{ height, width: '100%' }} notMerge lazyUpdate />
}

export default LiveArrhenius
