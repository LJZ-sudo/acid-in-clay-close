import React from 'react'
import { useReveal } from '../useReveal.js'
import ranking from '../data/frozenRanking.json'

const tagClass = { '重点验证 · 低温仍导电': 'tag-pos', '边界验证 · 低温失效': 'tag-bound', '未来工作': 'tag-future' }

export default function Act2Material({ active }) {
  // steps: 1 funnel, 2..6 rows, 7 governance
  const s = useReveal(active, ranking.candidates.length + 2, 600)
  const showGov = s >= ranking.candidates.length + 2

  return (
    <>
      <div className="kicker rv on">数字世界 · 第一个成果：新材料</div>
      <h1 className="title rv on">AI 自主发现的<span className="accent">新材料候选</span></h1>
      <p className="subtitle rv on">过去靠经验反复试错、动辄数月；现在 AI 从海量文献与配方组合中迁移推理，快速锁定最有潜力的新材料。</p>

      <div className={'funnel rv' + (s >= 1 ? ' on' : '')}>
        <div className="funnel-step"><div className="fs-big">海量</div><div className="fs-k">文献 · 配方组合</div></div>
        <div className="funnel-arrow">→</div>
        <div className="funnel-step"><div className="fs-big accent">AI</div><div className="fs-k">迁移推理 + 证据约束</div></div>
        <div className="funnel-arrow">→</div>
        <div className="funnel-step hot"><div className="fs-big accent-g">5</div><div className="fs-k">个高潜力新材料</div></div>
      </div>

      <div style={{ marginTop: '1.2vh' }}>
        {ranking.candidates.map((c, i) => (
          <div key={c.candidate_id} className={'mat-row rv' + (i < 2 ? ' top' : '') + (s >= i + 2 ? ' on' : '')}>
            <div className="mat-rank">{c.rank}</div>
            <div>
              <div className="mat-name">
                {c.name_zh}
                <span className={'mat-tag ' + (tagClass[c.experiment_role] || 'tag-future')}>{c.experiment_role}</span>
              </div>
              <div className="mat-sub">{c.components.join(' · ')} → {c.maps_to}</div>
            </div>
            <div className="mat-score">{c.score.toFixed(4)}</div>
          </div>
        ))}
      </div>

      <div className={'gov-strip rv' + (showGov ? ' on' : '')}>
        <div className="gov-chip"><span className="gi">🔗</span>证据可追溯</div>
        <div className="gov-chip"><span className="gi">↻</span>结果可复现</div>
        <div className="gov-chip"><span className="gi">✓</span>全程可审计</div>
        <div className="gov-note">从文献到候选，全链路留痕、可复算 —— 玻璃箱，而非黑箱。</div>
      </div>
    </>
  )
}
