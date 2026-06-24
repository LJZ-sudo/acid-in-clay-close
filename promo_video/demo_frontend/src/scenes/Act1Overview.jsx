import React from 'react'
import { useReveal } from '../useReveal.js'
import loop from '../data/aiafLoop.json'

export default function Act1Overview({ active }) {
  const s = useReveal(active, loop.loop.length + 1, 700)
  return (
    <>
      <div className="kicker rv on">FactoryLab AIAF OS · 工业发现闭环</div>
      <h1 className="title rv on">观测 → 理解 → 仿真授权 → 执行 → 反馈学习</h1>
      <p className="subtitle rv on">每个环节，都由专门的 <span className="accent">Agent</span>、标准化的 <span className="accent">Skill</span> 和真实的 <span className="accent">MEU</span> 执行单元完成。</p>

      <div className="loop-row">
        {loop.loop.map((node, i) => (
          <React.Fragment key={node.key}>
            <div className={'loop-card rv' + (s >= i + 1 ? ' on' : '')}>
              <div className="fa">{node.fa}</div>
              <div className="proj">{node.proj}</div>
              <div className="map">
                Agent：<span>{node.agent}</span><br />
                Skill：<span>{node.skill}</span><br />
                MEU：<span>{node.meu}</span>
              </div>
            </div>
            {i < loop.loop.length - 1 && <div className="arrowflow">→</div>}
          </React.Fragment>
        ))}
      </div>

      <div className={'note rv' + (s >= loop.loop.length + 1 ? ' on' : '')} style={{ marginTop: '2.2vh' }}>
        别人停在示意图——我们把整条闭环真正接到了真实的硬件、真实的智能体和真实的材料上。
      </div>
    </>
  )
}
