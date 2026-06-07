import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { useTranslation } from 'react-i18next'
import { useDataStore } from '../../stores'
import { CHART_COLORS } from '../../utils/constants'
import { formatLocaleNumber } from '../../utils/localeFormat'

const asFiniteNumber = (value) => {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

const normalizeTimestamp = (value) => {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  if (Number.isFinite(n)) return n < 1e12 ? n * 1000 : n
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.getTime()
}

function ConductivityChart({ height = 250 }) {
  const { t } = useTranslation()
  const { conductivityHistory, phaseTransitions } = useDataStore()

  const chartModel = useMemo(() => {
    const normalizedSeries = conductivityHistory
      .map((point) => {
        const ts = normalizeTimestamp(point?.timestamp)
        const value = asFiniteNumber(point?.value ?? point?.conductivity ?? point?.sigma)
        const temperature = asFiniteNumber(point?.temperature ?? point?.temperature_C ?? point?.t_actual)
        return ts === null ? null : [ts, value, temperature]
      })
      .filter(Boolean)

    const hasNonPositive = normalizedSeries.some((item) => Number.isFinite(item[1]) && item[1] <= 0)
    const hasPositive = normalizedSeries.some((item) => Number.isFinite(item[1]) && item[1] > 0)
    const useLogAxis = hasPositive && !hasNonPositive

    const chartPoints = normalizedSeries.filter((item) => {
      if (!Number.isFinite(item[1])) return false
      if (useLogAxis) return item[1] > 0
      return true
    })

    const positiveValues = chartPoints
      .map((item) => Number(item?.[1]))
      .filter((value) => Number.isFinite(value) && value > 0)

    const logRange = (() => {
      if (!useLogAxis || positiveValues.length === 0) {
        return { min: undefined, max: undefined }
      }
      const minVal = Math.min(...positiveValues)
      const maxVal = Math.max(...positiveValues)
      const minExp = Math.floor(Math.log10(minVal))
      const maxExp = Math.ceil(Math.log10(maxVal))
      let min = 10 ** minExp
      let max = 10 ** maxExp
      if (min === max) {
        min /= 10
        max *= 10
      }
      return { min, max }
    })()

    const markPoints = phaseTransitions
      .map((point) => {
        const ts = normalizeTimestamp(point?.timestamp)
        const conductivity = asFiniteNumber(point?.conductivity ?? point?.value ?? point?.sigma)
        if (ts === null || !Number.isFinite(conductivity)) return null
        if (useLogAxis && conductivity <= 0) return null

        return {
          coord: [ts, conductivity],
          name: `${t('charts.phaseTransition')} ${formatLocaleNumber(point?.temperature, { maximumFractionDigits: 2 })}°C`,
          symbol: 'pin',
          symbolSize: 30,
          itemStyle: { color: CHART_COLORS.phase },
        }
      })
      .filter(Boolean)

    return {
      renderedCount: chartPoints.length,
      option: {
      title: {
        text: t('charts.conductivityTrend'),
        left: 'center',
        textStyle: {
          fontSize: 14,
          fontWeight: 500,
        },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          if (!Array.isArray(params) || !params.length) return ''
          const value = Number(params[0]?.value?.[1])
          const temp = Number(params[0]?.value?.[2])
          const time = new Date(params[0].axisValue)
          const timeText = Number.isNaN(time.getTime()) ? '—' : time.toLocaleTimeString()

          return [
            '<div class="text-xs">',
            `<div class="font-medium">${timeText}</div>`,
            `<div>${t('charts.conductivity')}: ${Number.isFinite(value) ? value.toExponential(3) : '—'} S/cm</div>`,
            Number.isFinite(temp) ? `<div>${t('charts.temperature')}: ${formatLocaleNumber(temp, { maximumFractionDigits: 2 })}°C</div>` : '',
            '</div>',
          ].join('')
        },
      },
      legend: {
        data: [t('charts.conductivity')],
        bottom: 0,
        textStyle: { fontSize: 11 },
      },
      grid: {
        left: 56,
        right: '4%',
        bottom: '15%',
        top: '15%',
        containLabel: true,
      },
      xAxis: {
        type: 'time',
        axisLabel: {
          formatter: '{HH}:{mm}:{ss}',
          fontSize: 10,
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: useLogAxis ? 'log' : 'value',
        min: useLogAxis ? logRange.min : undefined,
        max: useLogAxis ? logRange.max : undefined,
        name: `${t('charts.conductivity')} (S/cm)`,
        nameTextStyle: { fontSize: 11 },
        axisLabel: {
          fontSize: 10,
          formatter: (value) => {
            const n = Number(value)
            if (!Number.isFinite(n)) return '—'
            return useLogAxis ? n.toExponential(0) : formatLocaleNumber(n, { maximumFractionDigits: 4 })
          },
        },
        splitLine: {
          lineStyle: { type: 'dashed', color: '#e5e7eb' },
        },
      },
      series: [
        {
          name: t('charts.conductivity'),
          type: 'line',
          smooth: true,
          showAllSymbol: true,
          symbol: 'circle',
          symbolSize: 4,
          lineStyle: { color: CHART_COLORS.conductivity, width: 2 },
          itemStyle: { color: CHART_COLORS.conductivity },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
                { offset: 1, color: 'rgba(16, 185, 129, 0.05)' },
              ],
            },
          },
          markPoint: {
            data: markPoints,
          },
          data: chartPoints,
        },
      ],
      },
    }
  }, [conductivityHistory, phaseTransitions, t])

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-4 text-sm">
          <span className="text-gray-500">{t('dashboard.dataPoints')}:</span>
          <span className="font-medium">{formatLocaleNumber(chartModel.renderedCount, { maximumFractionDigits: 0 })}</span>
          {phaseTransitions.length > 0 && (
            <>
              <span className="text-gray-500">{t('dashboard.phaseTransitions')}:</span>
              <span className="font-medium text-amber-600">{formatLocaleNumber(phaseTransitions.length, { maximumFractionDigits: 0 })}</span>
            </>
          )}
        </div>
      </div>
      {conductivityHistory.length === 0 ? (
        <p className="text-xs text-gray-400 mb-2">
          No conductivity series yet — measurements will add points here (same store as Recent Measurements).
        </p>
      ) : null}
      <ReactECharts option={chartModel.option} style={{ height }} opts={{ renderer: 'canvas' }} />
    </div>
  )
}

export default ConductivityChart

