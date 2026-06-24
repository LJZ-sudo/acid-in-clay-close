import React from 'react'
import { useReveal } from '../useReveal.js'
import cap from '../data/capabilityStack.json'

export default function Act2Capability({ active }) {
  const s = useReveal(active, cap.modules.length + 2, 600)
  return (
    <>
      <div className="kicker rv on">通用能力层 · Agent + Skills 工程栈</div>
      <h1 className="title rv on">真正通用的，是底层<span className="accent">工程能力</span></h1>
      <p className="subtitle rv on">
        这些能力在本项目上得到验证，<span className="accent-g">不绑定某种测量</span>，可迁移到任意工业 / 科研场景。
      </p>

      <div className="cap-grid">
        {cap.modules.map((m, i) => (
          <div key={m.key} className={'cap-card rv' + (s >= i + 2 ? ' on' : '')}>
            <div className="cap-head">
              <span className="cap-name">{m.name}</span>
              <span className="cap-en">{m.en}</span>
            </div>
            <div className="cap-impl"><span className="cap-tag">已实现</span>{m.impl}</div>
            <div className="cap-gen"><span className="cap-arrow">可泛化到</span>{m.general}</div>
          </div>
        ))}
      </div>

      <div className={'note rv' + (s >= cap.modules.length + 2 ? ' on' : '')} style={{ marginTop: '1.6vh' }}>
        {cap.footnote}
      </div>
    </>
  )
}
