import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { useDataStore } from '../../stores'
import { CHART_COLORS } from '../../utils/constants'

/**
 * Arrhenius chart component
 */
function ArrheniusChart({ height = 350, showFitLine = true }) {
  const { arrheniusData, phaseTransitions } = useDataStore()

  const option = useMemo(() => {
    if (!arrheniusData || !arrheniusData.points) {
      return {
        title: {
          text: 'Arrhenius plot',
          subtext: 'No data',
          left: 'center',
          top: 'center',
        },
      }
    }

    const points = arrheniusData.points || []
    const segments = arrheniusData.segment_lines || []
    const ea_values = arrheniusData.ea_values || []

    // Scatter series data
    const scatterData = points.map(p => ({
      value: [p.inv_t, p.ln_sigma],
      temperature: p.temperature,
      sigma: p.sigma,
    }))

    // Fit line series
    const fitLines = []
    if (showFitLine && segments.length > 0) {
      segments.forEach((seg, index) => {
        fitLines.push({
          name: `Segment ${index + 1} (Ea=${ea_values?.[index]?.toFixed(3) || '--'} eV)`,
          type: 'line',
          smooth: false,
          symbol: 'none',
          lineStyle: {
            color: index === 0 ? '#ef4444' : '#3b82f6',
            width: 2,
            type: 'dashed',
          },
          data: seg.map(p => [p.inv_t, p.ln_sigma]),
        })
      })
    }

    // Phase transition markers
    const phaseMarkers = phaseTransitions.map(pt => {
      const point = points.find(p => Math.abs(p.temperature - pt.temperature) < 0.5)
      if (point) {
        return {
          coord: [point.inv_t, point.ln_sigma],
          name: `Phase transition ${pt.temperature}°C`,
        }
      }
      return null
    }).filter(Boolean)

    return {
      title: {
        text: 'Arrhenius plot (ln σ vs 1000/T)',
        left: 'center',
        textStyle: {
          fontSize: 14,
          fontWeight: 500,
        },
      },
      tooltip: {
        trigger: 'item',
        formatter: (params) => {
          if (params.data.temperature !== undefined) {
            return `
              <div class="text-xs">
                <div class="font-medium">${params.data.temperature}°C</div>
                <div>1000/T: ${params.data.value[0].toFixed(4)} K⁻¹</div>
                <div>ln(σ): ${params.data.value[1].toFixed(4)}</div>
                <div>σ: ${params.data.sigma?.toExponential(3)} S/cm</div>
              </div>
            `
          }
          return ''
        },
      },
      legend: {
        data: ['Data points', ...fitLines.map(l => l.name)],
        bottom: 0,
        textStyle: { fontSize: 10 },
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '15%',
        top: '12%',
        containLabel: true,
      },
      xAxis: {
        type: 'value',
        name: '1000/T (K⁻¹)',
        nameLocation: 'center',
        nameGap: 30,
        nameTextStyle: { fontSize: 12 },
        axisLabel: {
          fontSize: 10,
          formatter: (v) => v.toFixed(2),
        },
        splitLine: {
          lineStyle: { type: 'dashed', color: '#e5e7eb' },
        },
      },
      yAxis: {
        type: 'value',
        name: 'ln(σ)',
        nameTextStyle: { fontSize: 12 },
        axisLabel: {
          fontSize: 10,
          formatter: (v) => v.toFixed(1),
        },
        splitLine: {
          lineStyle: { type: 'dashed', color: '#e5e7eb' },
        },
      },
      series: [
        {
          name: 'Data points',
          type: 'scatter',
          symbolSize: 8,
          itemStyle: { color: CHART_COLORS.arrhenius },
          data: scatterData,
          markPoint: phaseMarkers.length > 0 ? {
            symbol: 'pin',
            symbolSize: 35,
            itemStyle: { color: CHART_COLORS.phase },
            data: phaseMarkers,
          } : undefined,
        },
        ...fitLines,
      ],
    }
  }, [arrheniusData, phaseTransitions, showFitLine])

  return (
    <div className="card p-4">
      {/* Activation energy summary */}
      {arrheniusData?.ea_values && arrheniusData.ea_values.length > 0 && (
        <div className="flex items-center space-x-4 mb-3 p-2 bg-gray-50 rounded-lg">
          <span className="text-sm text-gray-600">Activation energy:</span>
          {arrheniusData.ea_values.map((ea, index) => (
            <div key={index} className="flex items-center space-x-1">
              <span 
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: index === 0 ? '#ef4444' : '#3b82f6' }}
              />
              <span className="text-sm font-medium">
                Segment {index + 1}: {ea.toFixed(3)} eV
              </span>
            </div>
          ))}
        </div>
      )}
      
      <ReactECharts 
        option={option} 
        style={{ height }} 
        opts={{ renderer: 'canvas' }}
      />
    </div>
  )
}

export default ArrheniusChart
