import React from 'react'
import { useReveal } from '../useReveal.js'

function DigitalIcon() {
  return (
    <svg className="worldicon" viewBox="0 0 120 120" fill="none">
      <rect x="34" y="34" width="52" height="52" rx="10" stroke="var(--cyan)" strokeWidth="3" />
      <circle cx="60" cy="60" r="6" fill="var(--cyan)" />
      <circle cx="46" cy="48" r="3.5" fill="var(--cyan)" opacity="0.9" />
      <circle cx="74" cy="48" r="3.5" fill="var(--cyan)" opacity="0.9" />
      <circle cx="46" cy="72" r="3.5" fill="var(--cyan)" opacity="0.9" />
      <circle cx="74" cy="72" r="3.5" fill="var(--cyan)" opacity="0.9" />
      <path d="M46 48L60 60M74 48L60 60M46 72L60 60M74 72L60 60" stroke="var(--cyan)" strokeWidth="2" opacity="0.7" />
      {[[60, 22], [60, 98], [22, 60], [98, 60]].map(([x, y], i) => (
        <line key={i} x1={x} y1={y} x2={x < 60 ? 34 : x > 60 ? 86 : 60} y2={y < 60 ? 34 : y > 60 ? 86 : 60} stroke="var(--cyan)" strokeWidth="3" />
      ))}
      {[22, 98].map((p) => (<React.Fragment key={p}>
        <circle cx={p} cy="60" r="3" fill="var(--cyan)" /><circle cx="60" cy={p} r="3" fill="var(--cyan)" />
      </React.Fragment>))}
    </svg>
  )
}

function PhysicalIcon() {
  return (
    <svg className="worldicon" viewBox="0 0 120 120" fill="none">
      <path d="M52 28h16v22l18 34a6 6 0 0 1-5 9H39a6 6 0 0 1-5-9l18-34V28z" stroke="var(--green)" strokeWidth="3" strokeLinejoin="round" />
      <path d="M44 70h32l9 14a6 6 0 0 1-5 9H40a6 6 0 0 1-5-9l9-14z" fill="var(--green)" opacity="0.22" />
      <line x1="48" y1="28" x2="72" y2="28" stroke="var(--green)" strokeWidth="3" strokeLinecap="round" />
      <circle cx="55" cy="82" r="3" fill="var(--green)" />
      <circle cx="66" cy="76" r="2.4" fill="var(--green)" />
      <circle cx="62" cy="86" r="2" fill="var(--green)" />
    </svg>
  )
}

export default function Act0Hook({ active }) {
  const s = useReveal(active, 4, 800)
  return (
    <>
      <div className="kicker rv on">FactoryLab · AIAF OS</div>
      <h1 className="title rv on" style={{ fontSize: '3.4vw', maxWidth: '74%' }}>
        让 AI 在<span className="accent">数字世界</span>里想清楚，<br />
        再到<span className="accent-g">物理世界</span>里把材料做出来、测出来
      </h1>
      <div className="hero-split" style={{ marginTop: '2.4vh' }}>
        <div className={'world rv' + (s >= 1 ? ' on' : '')}>
          <DigitalIcon />
          <div className="wlabel">数字世界</div>
          <div className="mat-sub">智能体推理 · 知识检索 · 自主优化</div>
        </div>
        <div className="bridge">
          <div className={'pulse rv' + (s >= 2 ? ' on' : '')}>⇌</div>
        </div>
        <div className={'world rv' + (s >= 1 ? ' on' : '')}>
          <PhysicalIcon />
          <div className="wlabel">物理世界</div>
          <div className="mat-sub">真实合成 · 宽温测量 · 硬件闭环</div>
        </div>
      </div>
      <div className={'note rv' + (s >= 3 ? ' on' : '')} style={{ marginTop: '2.6vh' }}>
        大多数 AI 停在屏幕里——它能想，却很难真正动手。FactoryLab 把这两个世界连了起来。
      </div>
    </>
  )
}
