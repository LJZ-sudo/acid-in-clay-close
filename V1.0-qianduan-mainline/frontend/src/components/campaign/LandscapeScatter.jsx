import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { useNavigate } from 'react-router-dom'

/**
 * BO Landscape — R x N scatter coloured by combined_score, with the LLM/BO
 * recommended point overlaid as a star and Pareto trials as diamonds.
 *
 * The series intentionally uses three layers (history / pareto / recommended)
 * so the legend doubles as a UI filter.
 */
function LandscapeScatter({ trials = [], paretoIds = [], recommended = null, anchorTrialId = null, height = 420, bounds = null }) {
  const navigate = useNavigate()
  const data = useMemo(() => {
    const paretoSet = new Set(paretoIds)
    const history = []
    const pareto = []
    for (const t of trials) {
      const params = t?.parameters || {}
      const obj = t?.objectives || {}
      const r = Number(params.R)
      const n = Number(params.N)
      const score = obj.combined_score
      if (!Number.isFinite(r) || !Number.isFinite(n)) continue
      const point = {
        value: [r, n, score ?? null],
        name: t?.metadata?.sample_id || `trial_${t?.trial_id ?? '?'}`,
        trial_id: t?.trial_id,
        sample_id: t?.metadata?.sample_id || null,
        objectives: obj,
      }
      if (paretoSet.has(t?.trial_id)) {
        pareto.push(point)
      } else {
        history.push(point)
      }
    }
    return { history, pareto }
  }, [trials, paretoIds])

  const recPoint = useMemo(() => {
    const rec = recommended?.recipe?.recommended_parameters
    const opt = recommended?.optimizer_suggestion
    if (!rec || rec.R == null || rec.N == null) return null
    const llmR = Number(rec.R)
    const llmN = Number(rec.N)
    const boR = opt && opt.R != null ? Number(opt.R) : null
    const boN = opt && opt.N != null ? Number(opt.N) : null
    // 当 |ΔR|<0.01 且 |ΔN|<0.01 时认为 LLM 完全采纳 BO，避免两个标记互相遮挡
    const llmEqualsBo =
      boR != null && boN != null && Math.abs(llmR - boR) < 0.01 && Math.abs(llmN - boN) < 0.01
    return {
      llm: { value: [llmR, llmN], name: 'LLM recommendation' },
      bo: boR != null && boN != null ? { value: [boR, boN], name: 'BO raw suggestion' } : null,
      llmEqualsBo,
    }
  }, [recommended])

  const anchorPoint = useMemo(() => {
    if (anchorTrialId == null) return null
    const t = trials.find((x) => String(x?.trial_id) === String(anchorTrialId))
    if (!t) return null
    const r = Number(t?.parameters?.R)
    const n = Number(t?.parameters?.N)
    if (!Number.isFinite(r) || !Number.isFinite(n)) return null
    return { value: [r, n], name: `anchor: trial ${anchorTrialId}` }
  }, [anchorTrialId, trials])

  const allScores = trials
    .map((t) => t?.objectives?.combined_score)
    .filter((s) => Number.isFinite(s))
  const minScore = allScores.length ? Math.min(...allScores) : -4
  const maxScore = allScores.length ? Math.max(...allScores) : -2

  // Axis ranges come from the live campaign bounds prop. Falling back to a
  // small padded box derived from trial data prevents the previously
  // hard-coded S8 (N∈[2,7.2]) range from masking points when the campaign
  // changes (e.g. attapulgite N∈[0.5,1.3] crushed every point against y=2).
  const axisRanges = useMemo(() => {
    const rLow = Number(bounds?.R?.low)
    const rHigh = Number(bounds?.R?.high)
    const nLow = Number(bounds?.N?.low)
    const nHigh = Number(bounds?.N?.high)
    if (Number.isFinite(rLow) && Number.isFinite(rHigh) && Number.isFinite(nLow) && Number.isFinite(nHigh)) {
      const rPad = Math.max(0.02, (rHigh - rLow) * 0.04)
      const nPad = Math.max(0.02, (nHigh - nLow) * 0.04)
      return {
        xMin: Math.max(0, rLow - rPad),
        xMax: rHigh + rPad,
        yMin: Math.max(0, nLow - nPad),
        yMax: nHigh + nPad,
      }
    }
    const rs = []
    const ns = []
    for (const t of trials) {
      const r = Number(t?.parameters?.R)
      const n = Number(t?.parameters?.N)
      if (Number.isFinite(r)) rs.push(r)
      if (Number.isFinite(n)) ns.push(n)
    }
    if (rs.length && ns.length) {
      return {
        xMin: Math.max(0, Math.min(...rs) - 0.05),
        xMax: Math.max(...rs) + 0.05,
        yMin: Math.max(0, Math.min(...ns) - 0.05),
        yMax: Math.max(...ns) + 0.05,
      }
    }
    return { xMin: 0, xMax: 1.05, yMin: 0, yMax: 1.5 }
  }, [bounds, trials])

  const option = useMemo(
    () => ({
      tooltip: {
        trigger: 'item',
        formatter: (p) => {
          const [r, n, s] = p.value
          const lines = [
            `<b>${p.data?.name ?? ''}</b>`,
            `R = ${r != null ? Number(r).toFixed(2) : '-'}`,
            `N = ${n != null ? Number(n).toFixed(2) : '-'}`,
          ]
          if (s != null) lines.push(`combined_score = ${Number(s).toFixed(4)}`)
          const obj = p.data?.objectives
          if (obj?.conductivity_room_temp_S_cm != null) {
            lines.push(`σ_RT = ${Number(obj.conductivity_room_temp_S_cm).toExponential(2)} S/cm`)
          }
          if (obj?.ea_high_temp_eV != null) {
            lines.push(`Ea_high = ${Number(obj.ea_high_temp_eV).toFixed(3)} eV`)
          }
          if (obj?.ea_low_temp_eV != null) {
            lines.push(`Ea_low = ${Number(obj.ea_low_temp_eV).toFixed(3)} eV`)
          }
          if (p.data?.sample_id) {
            lines.push(`<span style="color:#3b82f6;font-size:11px">click → /sample/${p.data.sample_id}</span>`)
          }
          return lines.join('<br/>')
        },
      },
      grid: { left: 50, right: 30, top: 30, bottom: 50, containLabel: true },
      xAxis: {
        name: 'R (mol/mol)', nameLocation: 'middle', nameGap: 28, type: 'value',
        min: axisRanges.xMin, max: axisRanges.xMax,
        axisLabel: { formatter: (v) => Number(v).toFixed(2) },
      },
      yAxis: {
        name: 'N (g/g)', nameLocation: 'middle', nameGap: 36, type: 'value',
        min: axisRanges.yMin, max: axisRanges.yMax,
        axisLabel: { formatter: (v) => Number(v).toFixed(2) },
      },
      visualMap: allScores.length
        ? {
            min: minScore,
            max: maxScore,
            dimension: 2,
            // 只对 history(0) + pareto(1) 着色；BO/LLM/anchor 用各自的固定颜色，
            // 避免 visualMap 覆盖标记色让图例与图面不一致。
            seriesIndex: [0, 1],
            inRange: { color: ['#440154', '#3b528b', '#21918c', '#5ec962', '#fde725'] },
            calculable: true,
            text: ['high\nscore', 'low\nscore'],
            textStyle: { fontSize: 10 },
            right: 0,
            top: 'middle',
            itemWidth: 10,
            itemHeight: 80,
          }
        : undefined,
      legend: {
        top: 0,
        textStyle: { fontSize: 11 },
        // history / pareto 颜色由 visualMap 控制，legend 里只保留形状提示
        formatter: (name) => {
          if (name === 'history') return 'history (color = score)'
          if (name === 'pareto') return 'pareto front'
          return name
        },
      },
      series: [
        {
          name: 'history',
          type: 'scatter',
          symbolSize: 12,
          data: data.history,
          z: 2,
          // legend icon 用中性灰，避免与实际渐变色冲突
          itemStyle: { color: '#9ca3af' },
        },
        {
          name: 'pareto',
          type: 'scatter',
          symbol: 'diamond',
          symbolSize: 16,
          itemStyle: { color: '#9ca3af', borderColor: '#111', borderWidth: 1 },
          data: data.pareto,
          z: 3,
        },
        recPoint?.bo
          ? {
              name: 'BO raw',
              type: 'scatter',
              symbol: 'circle',
              symbolSize: 20,
              itemStyle: { color: 'rgba(220,38,38,0.25)', borderColor: '#dc2626', borderWidth: 2 },
              data: [recPoint.bo],
              z: 4,
            }
          : null,
        recPoint?.llm
          ? {
              name: 'LLM (next)',
              type: 'effectScatter',
              symbol: 'pin',
              symbolSize: 32,
              itemStyle: {
                color: '#3D5AFE',
                borderColor: '#ffffff',
                borderWidth: 2,
                shadowColor: 'rgba(61,90,254,0.6)',
                shadowBlur: 6,
              },
              rippleEffect: { brushType: 'stroke', scale: 2.8 },
              // 当 LLM ≈ BO 时，把 pin 往右上偏移一点点，避免被红圈完全盖住
              label: recPoint.llmEqualsBo
                ? {
                    show: true,
                    formatter: '✓ LLM = BO',
                    position: 'right',
                    offset: [4, -16],
                    color: '#3D5AFE',
                    fontSize: 11,
                    fontWeight: 600,
                  }
                : undefined,
              data: [recPoint.llm],
              z: 6,
            }
          : null,
        anchorPoint
          ? {
              name: 'anchor',
              type: 'scatter',
              symbol: 'rect',
              symbolSize: 14,
              itemStyle: { color: 'transparent', borderColor: '#f59e0b', borderWidth: 2 },
              data: [anchorPoint],
              z: 5,
            }
          : null,
      ].filter(Boolean),
    }),
    [data, recPoint, anchorPoint, minScore, maxScore, allScores.length, axisRanges]
  )

  if (!trials.length && !recPoint) {
    return (
      <div className="flex items-center justify-center text-sm text-gray-400" style={{ height }}>
        No trials yet — run the closed-loop runner to populate the campaign history database.
      </div>
    )
  }

  const onEvents = useMemo(() => ({
    click: (p) => {
      const sid = p?.data?.sample_id
      if (sid) navigate(`/sample/${encodeURIComponent(sid)}`)
    },
  }), [navigate])

  return <ReactECharts option={option} style={{ height, width: '100%' }} notMerge lazyUpdate onEvents={onEvents} />
}

export default LandscapeScatter
