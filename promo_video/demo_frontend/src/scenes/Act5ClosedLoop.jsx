import React from 'react'
import { useReveal } from '../useReveal.js'
import Chart from '../components/Chart.jsx'
import cl from '../data/closedLoop.json'

function searchOption() {
  return {
    backgroundColor: 'transparent',
    grid: { left: 52, right: 24, top: 24, bottom: 40 },
    tooltip: {
      trigger: 'item',
      formatter: (p) => `第 ${p.dataIndex + 1} 轮<br/>酸量 R=${p.value[0]} · 中和度 N=${p.value[1]}`,
    },
    xAxis: {
      type: 'value', name: '酸量 R', min: 0, max: 0.8,
      nameTextStyle: { color: '#93a7c9' }, axisLabel: { color: '#93a7c9' },
      axisLine: { lineStyle: { color: '#33456a' } },
      splitLine: { lineStyle: { color: 'rgba(120,160,220,0.08)' } },
    },
    yAxis: {
      type: 'value', name: '中和度 N', min: 0.4, max: 1.2,
      nameTextStyle: { color: '#93a7c9' }, axisLabel: { color: '#93a7c9' },
      axisLine: { lineStyle: { color: '#33456a' } },
      splitLine: { lineStyle: { color: 'rgba(120,160,220,0.08)' } },
    },
    series: [{
      type: 'line', data: cl.rounds.map((r) => [r.R, r.N]),
      lineStyle: { width: 2, color: '#22d3ee', type: 'dashed' },
      symbol: 'circle', symbolSize: 20, itemStyle: { color: '#34d399' },
      label: { show: true, formatter: (p) => p.dataIndex + 1, color: '#04070e', fontSize: 11, fontWeight: 800 },
    }],
  }
}

export default function Act5ClosedLoop({ active }) {
  const s = useReveal(active, 4, 800)
  return (
    <>
      <div className="kicker rv on">数字 ⇌ 物理 · 真实闭环执行</div>
      <h1 className="title rv on">数字 ⇌ 物理 · <span className="accent">真实闭环执行</span><span className="accent-g">（全程可审计）</span></h1>
      <p className="subtitle rv on">AI 提出配方 → 自动合成 → 物理测量 → 数据回流 → AI 再优化 …</p>

      <div className={'tiles rv' + (s >= 1 ? ' on' : '')}>
        <div className="tile"><div className="v accent">{cl.n_rounds}</div><div className="k">数字⇌物理 闭环迭代</div></div>
        <div className="tile"><div className="v accent-g">自动</div><div className="k">合成 → 测量 → 数据回流</div></div>
        <div className="tile"><div className="v accent">{cl.n_gates}</div><div className="k">安全门禁（先仿真后执行）</div></div>
        <div className="tile"><div className="v accent-g">✓</div><div className="k">全程审计留痕</div></div>
      </div>

      <div className="two-col" style={{ marginTop: '1.4vh' }}>
        <div className={'panel chart-box rv' + (s >= 2 ? ' on' : '')}>
          <div className="mat-sub" style={{ marginBottom: '0.6vh' }}>AI 在配方空间中自主探索，逐轮逼近更优配方</div>
          <div style={{ height: 'calc(100% - 2.4vh)' }}><Chart option={searchOption()} /></div>
        </div>
        <div className={'panel rv' + (s >= 3 ? ' on' : '')}>
          <div className="mat-sub" style={{ marginBottom: '0.8vh' }}>执行治理硬门禁（先仿真 → 授权 → 执行 → 审计）</div>
          <div className="chiprow" style={{ marginTop: 0 }}>
            {cl.gates.map((g, i) => <div key={i} className="chip hot">{g}</div>)}
          </div>
          <div className="note honest" style={{ marginTop: '1.8vh' }}>
            {cl.positive_note}
          </div>
        </div>
      </div>

      <div className={'note rv' + (s >= 4 ? ' on' : '')}>
        人机协同：{cl.human_intervention}。闭环一旦跑通，AI 便能持续自我迭代、让性能稳步逼近最优 —— 同一套能力还可复制到更多产线与材料体系，越跑越准。
      </div>
    </>
  )
}
