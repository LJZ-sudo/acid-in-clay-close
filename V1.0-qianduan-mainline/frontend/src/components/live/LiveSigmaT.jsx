import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'

/**
 * LiveSigmaT — temperature trace + measured sigma overlay.
 * Used in the cockpit because Nyquist data is not always streamed in
 * MEASUREMENT_COMPLETED payloads, while T and sigma always are.
 */
function LiveSigmaT({ measurements = [], lastSetT = null, height = 300 }) {
  const series = useMemo(() => {
    const t = []
    const sigma = []
    measurements.forEach((m, idx) => {
      const tC = Number(m?.temperature_C)
      const s = Number(m?.conductivity_S_cm)
      if (Number.isFinite(tC)) t.push([idx, tC])
      if (Number.isFinite(s) && s > 0) sigma.push([idx, s])
    })
    return { t, sigma }
  }, [measurements])

  const option = useMemo(
    () => ({
      tooltip: { trigger: 'axis' },
      legend: { data: ['T (°C)', 'σ (S/cm)'], top: 0, textStyle: { fontSize: 11 } },
      grid: { left: 50, right: 60, top: 30, bottom: 40, containLabel: true },
      xAxis: { name: 'step', nameLocation: 'middle', nameGap: 22, type: 'value', minInterval: 1 },
      yAxis: [
        { name: 'T (°C)', nameLocation: 'middle', nameGap: 36, type: 'value', position: 'left' },
        { name: 'σ (S/cm)', nameLocation: 'middle', nameGap: 50, type: 'log', position: 'right' },
      ],
      series: [
        {
          name: 'T (°C)',
          type: 'line',
          smooth: true,
          symbol: 'none',
          itemStyle: { color: '#3D5AFE' },
          data: series.t,
          yAxisIndex: 0,
          markLine:
            lastSetT && Number.isFinite(Number(lastSetT.target))
              ? {
                  symbol: 'none',
                  lineStyle: { color: '#3D5AFE', type: 'dashed', opacity: 0.5 },
                  data: [{ yAxis: Number(lastSetT.target), name: 'target' }],
                }
              : undefined,
        },
        {
          name: 'σ (S/cm)',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 4,
          itemStyle: { color: '#dc2626' },
          data: series.sigma,
          yAxisIndex: 1,
        },
      ],
    }),
    [series, lastSetT]
  )

  if (series.t.length === 0 && series.sigma.length === 0) {
    return (
      <div className="flex items-center justify-center text-xs text-gray-400" style={{ height }}>
        Waiting for first measurement...
      </div>
    )
  }
  return <ReactECharts option={option} style={{ height, width: '100%' }} notMerge lazyUpdate />
}

export default LiveSigmaT
