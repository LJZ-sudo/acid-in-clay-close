import React from 'react'
import { useReveal } from '../useReveal.js'
import Chart from '../components/Chart.jsx'
import wt from '../data/wideTemperature.json'
import ea from '../data/eaBenchmark.json'

function sigmaOption() {
  return {
    backgroundColor: 'transparent',
    grid: { left: 56, right: 18, top: 30, bottom: 44 },
    legend: {
      data: wt.samples.map((s) => s.label),
      textStyle: { color: '#93a7c9', fontSize: 11 }, top: 0, type: 'scroll',
    },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'value', name: '温度 (°C)', inverse: true, min: -90, max: 30,
      nameTextStyle: { color: '#93a7c9' },
      axisLabel: { color: '#93a7c9' }, axisLine: { lineStyle: { color: '#33456a' } },
      splitLine: { lineStyle: { color: 'rgba(120,160,220,0.08)' } },
    },
    yAxis: {
      type: 'log', name: 'σ (S/cm)', min: 1e-6, max: 1e-1,
      nameTextStyle: { color: '#93a7c9' },
      axisLabel: { color: '#93a7c9', formatter: (v) => '1e' + Math.round(Math.log10(v)) },
      axisLine: { lineStyle: { color: '#33456a' } },
      splitLine: { lineStyle: { color: 'rgba(120,160,220,0.08)' } },
    },
    series: wt.samples.map((s) => ({
      name: s.label, type: 'line', smooth: true, symbol: 'circle', symbolSize: 7,
      lineStyle: { width: 3, color: s.color }, itemStyle: { color: s.color },
      data: s.curve.map((p) => [p.tempC, p.sigma]),
    })).concat([{
      name: '低温坍塌带', type: 'line', markArea: {
        silent: true, itemStyle: { color: 'rgba(245,158,11,0.08)' },
        data: [[{ xAxis: -45 }, { xAxis: -35 }]],
      }, data: [],
    }]),
  }
}

function eaOption() {
  const colorMap = { ours_lrs: '#34d399', ref: '#22d3ee', mother: '#f59e0b', ours_control: '#5f739a' }
  return {
    backgroundColor: 'transparent',
    grid: { left: 120, right: 36, top: 12, bottom: 28 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'value', name: '导电势垒 (eV) · 越低越好', max: 0.13, nameTextStyle: { color: '#93a7c9' },
      axisLabel: { color: '#93a7c9' }, axisLine: { lineStyle: { color: '#33456a' } },
      splitLine: { lineStyle: { color: 'rgba(120,160,220,0.08)' } },
    },
    yAxis: {
      type: 'category', inverse: true, data: ea.benchmarks.map((b) => b.label),
      axisLabel: { color: '#cfe0ff', fontSize: 11 }, axisLine: { lineStyle: { color: '#33456a' } },
    },
    series: [{
      type: 'bar', barWidth: '55%',
      data: ea.benchmarks.map((b) => ({ value: b.ea_eV, itemStyle: { color: colorMap[b.kind] || '#22d3ee' } })),
      label: { show: true, position: 'right', color: '#e8f0ff', formatter: (p) => p.value.toFixed(3) },
    }],
  }
}

export default function Act4Mechanism({ active }) {
  const s = useReveal(active, 4, 850)
  return (
    <>
      <div className="kicker rv on">物理世界 · 第二个成果：新机理</div>
      <h1 className="title rv on">为什么有的材料，<span className="accent">低温下还能导电？</span></h1>
      <p className="subtitle rv on">AI 从真实测量数据里找到了原因，并把它变成一把能迁移到其它材料的标尺。</p>

      <div className="two-col" style={{ marginTop: '1.4vh' }}>
        <div className={'panel chart-box rv' + (s >= 1 ? ' on' : '')}>
          <div className="mat-sub" style={{ marginBottom: '0.6vh' }}>宽温电导率：莲藕淀粉平滑延伸到极低温，壳聚糖在 -40°C 附近骤降</div>
          <div style={{ height: 'calc(100% - 2.4vh)' }}><Chart option={sigmaOption()} /></div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2vh', minHeight: 0 }}>
          <div className={'panel rv' + (s >= 2 ? ' on' : '')} style={{ flex: 1, minHeight: 0 }}>
            <div className="mat-sub" style={{ marginBottom: '0.6vh' }}>导电势垒越低越好：本研究新材料逼近已报道最优</div>
            <div style={{ height: 'calc(100% - 2.4vh)' }}><Chart option={eaOption()} /></div>
          </div>
          <div className={'tiles rv' + (s >= 3 ? ' on' : '')} style={{ marginTop: 0 }}>
            <div className="tile"><div className="v accent-g">0.037</div><div className="k">导电势垒 eV（逼近已报道最优）</div></div>
            <div className="tile"><div className="v accent">-81°C</div><div className="k">仍保持导电</div></div>
            <div className="tile"><div className="v accent-a">~100×</div><div className="k">拉开与低温坍塌材料的差距</div></div>
          </div>
        </div>
      </div>

      <div className={'note rv' + (s >= 4 ? ' on' : '')}>
        {wt.collapse_note} <b style={{ color: 'var(--green)' }}>说得直白点：让材料在零下 80 度还能稳定导电 —— 这正是极端低温、极端环境场景最稀缺的硬能力。</b>
      </div>
    </>
  )
}
