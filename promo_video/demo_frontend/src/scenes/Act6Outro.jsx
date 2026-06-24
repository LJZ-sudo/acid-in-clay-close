import React from 'react'
import { useReveal } from '../useReveal.js'
import seed from '../data/seedLibrary.json'
import loop from '../data/aiafLoop.json'

export default function Act6Outro({ active }) {
  const s = useReveal(active, 4, 750)
  const g = loop.generalization
  return (
    <>
      <div className="kicker rv on">从一个发现闭环 → 一个产业基础设施</div>
      <h1 className="title rv on" style={{ fontSize: '2.5cqw', textWrap: 'balance' }}>{g.headline}</h1>

      <div className="tiles rv on" style={{ marginTop: '1.2vh' }}>
        <div className="tile"><div className="v accent">{seed.stats.scenarios}</div><div className="k">场景种子库</div></div>
        <div className="tile"><div className="v accent">{seed.stats.chain_links}</div><div className="k">全产业链路</div></div>
        <div className="tile"><div className="v accent">{seed.stats.agents}</div><div className="k">Agent</div></div>
        <div className="tile"><div className="v accent">{seed.stats.skills}</div><div className="k">Skills</div></div>
        <div className="tile"><div className="v accent">{seed.stats.meu}</div><div className="k">MEU</div></div>
      </div>

      <div className={'levels rv' + (s >= 1 ? ' on' : '')}>
        {g.levels.map((lv, i) => (
          <React.Fragment key={lv.k}>
            <div className="level-step">
              <div className="lv-k">{lv.k}</div>
              <div className="lv-v">{lv.v}</div>
            </div>
            {i < g.levels.length - 1 && <div className="level-arrow">→</div>}
          </React.Fragment>
        ))}
      </div>

      <div className={'rv' + (s >= 2 ? ' on' : '')} style={{ marginTop: '1.6vh' }}>
        <div className="bridge-line">你刚看到的这个质子导体发现项目，<b className="accent-g">只是 FactoryLab 能力库里的一个落点</b> —— 同一套能力，覆盖材料 → 电芯 → PACK → 制造 → 测试 → 回收的完整链路：</div>
        <div className="link-grid">
          {seed.chain_links.map((name, i) => (
            <div key={i} className={'link-chip' + (i === seed.demo_link_index ? ' demo' : '')}>
              {name}{i === seed.demo_link_index && <span className="link-here">本 demo</span>}
            </div>
          ))}
        </div>
      </div>

      <div className={'rv' + (s >= 3 ? ' on' : '')} style={{ marginTop: 'auto', textAlign: 'center' }}>
        <div className="title" style={{ fontSize: '1.95cqw', textWrap: 'balance', margin: 0 }}>
          <span className="accent">FactoryLab</span> —— 让工业知识，真正变成<span className="accent-g">可调用、可验证、可执行</span>的产业能力
        </div>
        <div className="subtitle">AIAF OS · Autonomous Industrial-Agentic Fabrication</div>
      </div>
    </>
  )
}
