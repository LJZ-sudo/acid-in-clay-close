import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { useTranslation } from 'react-i18next'
import { useDataStore } from '../../stores'
import { CHART_COLORS } from '../../utils/constants'
import { formatLocaleNumber, formatTemperature } from '../../utils/localeFormat'

function TemperatureChart({ height = 250 }) {
  const { t } = useTranslation()
  const { temperatureHistory, currentTemperature, targetTemperature } = useDataStore()

  const option = useMemo(() => ({
    title: {
      text: t('charts.temperatureTrend'),
      left: 'center',
      textStyle: {
        fontSize: 14,
        fontWeight: 500,
      },
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        const time = new Date(params[0].axisValue)
        const timeText = Number.isNaN(time.getTime()) ? '—' : time.toLocaleTimeString()
        const rows = [`<div class="text-xs"><div class="font-medium">${timeText}</div>`]
        params.forEach((item) => {
          const value = Number(item?.value?.[1])
          const display = Number.isFinite(value)
            ? formatLocaleNumber(value, { maximumFractionDigits: 2 })
            : '—'
          rows.push(
            `<div class="flex items-center mt-1"><span style="background:${item.color}" class="w-2 h-2 rounded-full mr-1"></span>${item.seriesName}: ${display}°C</div>`
          )
        })
        rows.push('</div>')
        return rows.join('')
      },
    },
    legend: {
      data: [t('charts.actualTemperature'), t('charts.targetTemperature')],
      bottom: 0,
      textStyle: { fontSize: 11 },
    },
    grid: {
      left: '3%',
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
      type: 'value',
      name: `${t('charts.temperature')} (°C)`,
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 10 },
      splitLine: {
        lineStyle: { type: 'dashed', color: '#e5e7eb' },
      },
    },
    series: [
      {
        name: t('charts.actualTemperature'),
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { color: CHART_COLORS.temperature, width: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
              { offset: 1, color: 'rgba(59, 130, 246, 0.05)' },
            ],
          },
        },
        data: temperatureHistory.map((point) => [point.timestamp, point.value]),
      },
      {
        name: t('charts.targetTemperature'),
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: '#f59e0b',
          width: 1.5,
          type: 'dashed',
        },
        data: temperatureHistory.map((point) => [point.timestamp, point.target]),
      },
    ],
  }), [t, temperatureHistory])

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-4 text-sm">
          <span className="text-gray-500">{t('dashboard.currentTemperatureLabel')}:</span>
          <span className="font-semibold text-lg text-blue-600">{formatTemperature(currentTemperature)}</span>
          <span className="text-gray-500">{t('dashboard.targetTemperatureLabel')}:</span>
          <span className="font-medium text-amber-600">{formatTemperature(targetTemperature)}</span>
        </div>
      </div>
      {temperatureHistory.length === 0 ? (
        <p className="text-xs text-gray-400 mb-2">
          No trace points yet — connect and run; WebSocket / HTTP will populate this chart.
        </p>
      ) : null}
      <ReactECharts option={option} style={{ height }} opts={{ renderer: 'canvas' }} />
    </div>
  )
}

export default TemperatureChart
