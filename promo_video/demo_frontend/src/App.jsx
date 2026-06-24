import React, { useEffect, useRef, useState } from 'react'
import Act0Hook from './scenes/Act0Hook.jsx'
import Act1Overview from './scenes/Act1Overview.jsx'
import Act2Capability from './scenes/Act2Capability.jsx'
import Act2Material from './scenes/Act2Material.jsx'
import Act3Physical from './scenes/Act3Physical.jsx'
import Act4Mechanism from './scenes/Act4Mechanism.jsx'
import Act5ClosedLoop from './scenes/Act5ClosedLoop.jsx'
import Act6Outro from './scenes/Act6Outro.jsx'

// Pre-generated narration audio. Two dubs share the same scene-id filenames:
//   assets/audio/<id>.mp3     -> ENGLISH dub   (default, ?lang=en)
//   assets/audio_zh/<id>.mp3  -> CHINESE dub   (?lang=zh)
// Both versions always show the Chinese subtitle (subs.zh).
const AUDIO_EN = import.meta.glob('./assets/audio/*.mp3', { eager: true, query: '?url', import: 'default' })
const AUDIO_ZH = import.meta.glob('./assets/audio_zh/*.mp3', { eager: true, query: '?url', import: 'default' })
const audioUrl = (id, lang) => lang === 'zh'
  ? (AUDIO_ZH[`./assets/audio_zh/${id}.mp3`] || null)
  : (AUDIO_EN[`./assets/audio/${id}.mp3`] || null)

// Scene registry. `dur` (ms) is a safety cap for autoplay; the show advances ~2.5s
// after narration ends. `subs` holds parallel English + Chinese sentences: the
// spoken-language array (en for English dub, zh for Chinese dub) weights the
// subtitle timing, while subs.zh is what's shown on screen. physical = narration
// THEN video.
const SCENES = [
  {
    id: 'hook', Comp: Act0Hook, dur: 25000,
    subs: {
      en: [
        'In industry and research, AI too often stays trapped behind the screen.',
        'It can think, but it struggles to truly act.',
        'FactoryLab was built to connect the reasoning of AI to the physical world.',
        'It reasons out a new material in the digital world — then makes it, and measures it, in the real one.',
      ],
      zh: [
        '在工业与科研中，AI 常常被困在屏幕里。',
        '它能思考，却很难真正动手。',
        'FactoryLab 要把 AI 的推理，连接到物理世界。',
        '它在数字世界里想清楚一种新材料，再到现实里把它做出来、测出来。',
      ],
    },
  },
  {
    id: 'overview', Comp: Act1Overview, dur: 27000,
    subs: {
      en: [
        "This is FactoryLab's A.I.A.F. operating system.",
        'It turns any industrial discovery into a closed loop: observe, understand, simulate and authorize, execute, and learn.',
        'Every stage runs on dedicated agents, standardized skills, and real execution units.',
        'Where others stop at a diagram, we run the entire loop for real.',
      ],
      zh: [
        '这就是 FactoryLab 的 AIAF 操作系统。',
        '它把任何工业发现拆成闭环：观测、理解、仿真授权、执行、反馈学习。',
        '每个环节，都由专门的智能体、标准化能力和真实执行单元完成。',
        '别人止步于示意图，我们把整条闭环真正跑通。',
      ],
    },
  },
  {
    id: 'capability', Comp: Act2Capability, dur: 31500,
    subs: {
      en: [
        'Powering this loop is a complete set of general-purpose engineering capabilities.',
        'They give the AI the right information, keep it executing step by step, and let every skill be reused like a tool.',
        'With self-checking, full traceability, and rollback at any time — not tied to any single industry.',
        'What discovers a material today can move tomorrow into electronics, chemicals, and pharmaceuticals.',
      ],
      zh: [
        '支撑这条闭环的，是一整套通用的工程能力。',
        '它让 AI 拿到对的信息、按流程稳定执行、把每项技能像工具一样复用。',
        '还能自我检查、全程留痕、随时回滚——不绑定任何单一行业。',
        '今天发现一种新材料，明天就能迁移到电子、化工、医药。',
      ],
    },
  },
  {
    id: 'material', Comp: Act2Material, dur: 26000,
    subs: {
      en: [
        'The first result from the digital world: a new material.',
        'Finding one used to mean months of trial and error.',
        'Now agents reason across vast literature and countless formulations, surfacing the most promising candidates.',
        'And every conclusion is traceable, reproducible, and fully auditable.',
      ],
      zh: [
        '数字世界的第一个成果——新材料。',
        '过去找一种新材料，往往要反复试错、耗上几个月。',
        '如今智能体在海量文献与配方组合中推理，筛出最有潜力的候选。',
        '而每一个结论都证据可追溯、结果可复现、全程可审计。',
      ],
    },
  },
  {
    id: 'physical', Comp: Act3Physical, dur: 165000,
    subs: {
      en: [
        'The candidates chosen in the digital world move immediately into the physical one.',
        'A real electrochemical workstation — real wide-temperature impedance measurements, from room temperature to extreme cold.',
        'This is where an idea, for the first time, becomes data you can hold in your hands.',
      ],
      zh: [
        '数字世界选出的候选，立刻进入物理世界。',
        '真实的电化学工作站，真实的宽温阻抗谱测量，从常温一路降到极低温。',
        '这是 AI 的想法，第一次变成手里能测到的数据。',
      ],
    },
  },
  {
    id: 'mechanism', Comp: Act4Mechanism, dur: 31500,
    subs: {
      en: [
        'In the physical world, we uncovered a new mechanism.',
        'In the same system, some materials fail in extreme cold, while others keep conducting smoothly.',
        'AI found the reason, and turned it into a yardstick that transfers to other materials.',
        'Keeping a material conductive at minus eighty degrees is exactly the kind of hard capability that extreme-cold, extreme-environment applications need most.',
      ],
      zh: [
        '在物理世界里，我们还发现了一个新机理。',
        '同样的体系，有的材料一到极端低温就失效，有的却依然顺畅导电。',
        'AI 找到了背后的原因，并把它变成一把能迁移到别的材料的标尺。',
        '让材料在零下八十度还能稳定导电，正是极端低温、极端环境场景最稀缺的硬能力。',
      ],
    },
  },
  {
    id: 'closedloop', Comp: Act5ClosedLoop, dur: 37000,
    subs: {
      en: [
        'Digital and physical now form one closed loop, iterating round after round.',
        'The AI proposes a formulation; it is synthesized and measured automatically; the data flows straight back, and the AI optimizes again.',
        'Every high-risk action is simulated, then authorized, then executed — fully traceable.',
        'Each round makes it smarter — a discovery engine that keeps improving and can be replicated across product lines and materials.',
      ],
      zh: [
        '数字与物理，如今连成了一条闭环，一轮接一轮地迭代。',
        'AI 提出配方，自动合成、自动测量，数据实时回流，AI 随即再优化。',
        '每一步高风险动作，都先仿真、再授权、后执行，全程可追溯。',
        '每迭代一轮，它就更聪明一分——这是一台能不断进化、并可复制到更多产线与材料的发现引擎。',
      ],
    },
  },
  {
    id: 'outro', Comp: Act6Outro, dur: 35000,
    subs: {
      en: [
        "The proton-conductor project you just saw is only one landing point in FactoryLab's library of capabilities.",
        'Behind it lies a single reusable foundation — scaling from a project to an enterprise, a park, and an entire industry.',
        'Across the full chain: materials, cells, packs, manufacturing, testing, and recycling.',
        'FactoryLab — turning industrial knowledge into capability that can be called, verified, and executed.',
      ],
      zh: [
        '你刚刚看到的质子导体项目，只是 FactoryLab 能力库里的一个落点。',
        '它背后是同一套可复用能力——从项目，泛化到企业、园区，乃至整个行业。',
        '覆盖材料、电芯、PACK、制造、测试到回收的完整链路。',
        'FactoryLab，让工业知识变成可调用、可验证、可执行的产业能力。',
      ],
    },
  },
]

function pickVoice(lang) {
  if (!('speechSynthesis' in window)) return null
  const vs = window.speechSynthesis.getVoices() || []
  if (lang === 'zh') {
    return vs.find((v) => /zh[-_]CN/i.test(v.lang)) || vs.find((v) => /^zh/i.test(v.lang)) || null
  }
  return vs.find((v) => /en[-_]US/i.test(v.lang)) || vs.find((v) => /^en/i.test(v.lang)) || null
}

export default function App() {
  const [idx, setIdx] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [muted, setMuted] = useState(false)
  const [lang, setLang] = useState('zh') // default Chinese dub; switch to English via button / 'l' / ?lang=en (both show zh subtitle)
  const [hideUi, setHideUi] = useState(false) // ?hideui=1 hides the control bar for clean screen-recording
  const [narrationEnded, setNarrationEnded] = useState(false)
  const [hasStarted, setHasStarted] = useState(false)
  const [subText, setSubText] = useState('')
  const raf = useRef(0)
  const last = useRef(0)
  const audioRef = useRef(null)
  const playedRef = useRef(-1)

  // reset narration state whenever we move to a new scene OR switch dub language
  // (switching language re-plays the current scene's narration in the new voice)
  useEffect(() => { setNarrationEnded(false); playedRef.current = -1; setSubText('') }, [idx, lang])

  // Chinese subtitle synced to the narration audio. Picks the current chunk by
  // audio progress, weighted by the SPOKEN language's sentence length (en sentences
  // for the English dub, zh sentences for the Chinese dub) so timing stays aligned.
  useEffect(() => {
    const a = audioRef.current
    if (!a) return
    const onTime = () => {
      const sc = SCENES[idx]
      if (!sc.subs || a.paused || a.ended || !a.duration || isNaN(a.duration)) return
      const { zh } = sc.subs
      const spoken = sc.subs[lang] || zh
      const w = spoken.map((s) => s.length)
      const total = w.reduce((x, y) => x + y, 0) || 1
      const frac = Math.min(0.999, a.currentTime / a.duration)
      let acc = 0, picked = zh[zh.length - 1]
      for (let i = 0; i < zh.length; i++) {
        const start = acc / total; acc += (w[i] || 0); const end = acc / total
        if (frac >= start && frac < end) { picked = zh[i]; break }
      }
      setSubText(picked)
    }
    const onEnd = () => setSubText('')
    a.addEventListener('timeupdate', onTime)
    a.addEventListener('ended', onEnd)
    return () => { a.removeEventListener('timeupdate', onTime); a.removeEventListener('ended', onEnd) }
  }, [idx, lang])

  // autoplay timer
  useEffect(() => {
    if (!playing) return
    last.current = performance.now()
    const tick = (now) => {
      const dt = now - last.current
      last.current = now
      setElapsed((e) => {
        const ne = e + dt
        if (ne >= SCENES[idx].dur) {
          if (idx < SCENES.length - 1) { setIdx(idx + 1); return 0 }
          setPlaying(false)
          return SCENES[idx].dur
        }
        return ne
      })
      raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf.current)
  }, [playing, idx])

  // advance shortly after narration ends (keeps inter-scene gap tight ~2.5s).
  // `dur` above is only a safety cap. The hardware scene is excluded: it
  // advances when the video itself ends (see onComplete passed to the scene).
  useEffect(() => {
    if (!playing || !narrationEnded) return
    if (SCENES[idx].id === 'physical') return
    const t = setTimeout(() => {
      if (idx < SCENES.length - 1) { setIdx(idx + 1); setElapsed(0) }
      else setPlaying(false)
    }, 2500)
    return () => clearTimeout(t)
  }, [playing, narrationEnded, idx])

  // audio orchestration: mp3 if present, else browser speech synthesis.
  // narration starts ONCE per scene; pause/resume only pauses/continues it
  // (so it never restarts over the already-playing hardware video).
  useEffect(() => {
    const a = audioRef.current
    const stopSpeech = () => { if ('speechSynthesis' in window) window.speechSynthesis.cancel() }
    if (!playing) { if (a) a.pause(); stopSpeech(); return }
    // muted: skip narration but let any narration-gated content (hardware video) proceed
    if (muted) { if (a) a.pause(); stopSpeech(); setNarrationEnded(true); return }
    const sc = SCENES[idx]
    const url = audioUrl(sc.id, lang)
    // resume: this scene's narration already began -> just continue, don't restart
    if (playedRef.current === idx) {
      if (a && url && !a.ended) a.play().catch(() => {})
      return
    }
    playedRef.current = idx
    const narrationText = sc.subs ? (lang === 'zh' ? sc.subs.zh.join('') : sc.subs.en.join(' ')) : null
    if (a && url) {
      a.muted = false; a.src = url; a.currentTime = 0
      a.play().catch(() => { if (narrationText) speakFallback(narrationText); else setNarrationEnded(true) })
    } else if (narrationText) {
      speakFallback(narrationText)
    } else {
      setNarrationEnded(true)
    }
    function speakFallback(text) {
      if (!('speechSynthesis' in window)) { setNarrationEnded(true); return }
      window.speechSynthesis.cancel()
      const u = new SpeechSynthesisUtterance(text)
      u.lang = lang === 'zh' ? 'zh-CN' : 'en-US'
      const v = pickVoice(lang)
      if (v) u.voice = v
      u.rate = 0.96; u.pitch = 1.0
      u.onend = () => setNarrationEnded(true)
      window.speechSynthesis.speak(u)
    }
    return () => { stopSpeech() }
  }, [idx, playing, muted, lang])

  // ensure voices are loaded for the speech fallback
  useEffect(() => {
    if ('speechSynthesis' in window) window.speechSynthesis.getVoices()
  }, [])

  const go = (i) => { setIdx(Math.max(0, Math.min(SCENES.length - 1, i))); setElapsed(0) }

  // keyboard: space=play/pause, arrows=prev/next, r=restart, m=mute
  useEffect(() => {
    const onKey = (e) => {
      if (e.code === 'Space') { e.preventDefault(); setPlaying((p) => !p) }
      else if (e.code === 'ArrowRight') { go(idx + 1) }
      else if (e.code === 'ArrowLeft') { go(idx - 1) }
      else if (e.key === 'r' || e.key === 'R') { setIdx(0); setElapsed(0); setPlaying(true) }
      else if (e.key === 'm' || e.key === 'M') { setMuted((m) => !m) }
      else if (e.key === 'l' || e.key === 'L') { setLang((g) => (g === 'zh' ? 'en' : 'zh')) }
      else if (e.key === 'h' || e.key === 'H') { setHideUi((v) => !v) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [idx])

  // autoplay via ?autoplay=1 ; jump via ?scene=N (1-based) ; ?mute=1
  useEffect(() => {
    const p = new URLSearchParams(window.location.search)
    const sc = parseInt(p.get('scene'), 10)
    if (!Number.isNaN(sc)) { setIdx(Math.max(0, Math.min(SCENES.length - 1, sc - 1))); setElapsed(0) }
    if (p.get('mute') === '1') setMuted(true)
    const lg = (p.get('lang') || '').toLowerCase()
    if (lg === 'zh' || lg === 'en') setLang(lg)
    if (p.get('hideui') === '1') setHideUi(true)
    if (p.get('autoplay') === '1') { setHasStarted(true); setPlaying(true) }
  }, [])

  const startShow = () => { setIdx(0); setElapsed(0); setHasStarted(true); setPlaying(true) }

  const sceneProgress = Math.min(1, elapsed / SCENES[idx].dur)

  return (
    <div className="stage">
      <div className="canvas">
        <audio ref={audioRef} preload="auto" onEnded={() => setNarrationEnded(true)} />
        <div className="hud"><div className="hud-fill" style={{ width: `${sceneProgress * 100}%` }} /></div>
        <div className="brandtag"><b>FactoryLab</b> · AIAF OS · 数字 ↔ 物理 发现闭环</div>
        <div className="controls" style={hideUi ? { display: 'none' } : undefined}>
          <span>{idx + 1}/{SCENES.length}</span>
          <button onClick={() => go(idx - 1)}>‹ 上一幕</button>
          <button onClick={() => setPlaying((p) => !p)}>{playing ? '暂停' : '播放'}</button>
          <button onClick={() => go(idx + 1)}>下一幕 ›</button>
          <button onClick={() => { setIdx(0); setElapsed(0); setPlaying(true) }}>重播</button>
          <button onClick={() => setMuted((m) => !m)}>{muted ? '🔇 静音' : '🔊 配音'}</button>
          <button onClick={() => setLang((g) => (g === 'zh' ? 'en' : 'zh'))} title="切换配音语言（中文字幕不变）">
            {lang === 'zh' ? '🗣 中文配音' : '🗣 英文配音'}
          </button>
        </div>

        {SCENES.map((s, i) => {
          const Comp = s.Comp
          return (
            <div key={s.id} className={'scene' + (i === idx ? ' active' : '')}>
              {i === idx && <Comp active={i === idx} playing={playing} progress={sceneProgress} narrationEnded={narrationEnded}
                onComplete={() => { if (!playing) return; if (idx < SCENES.length - 1) { setIdx(idx + 1); setElapsed(0) } else setPlaying(false) }} />}
            </div>
          )
        })}

        <div className={'caption subtitle-bar' + (subText ? ' on' : '')}>{subText}</div>

        {!hasStarted && (
          <div className="start-overlay" onClick={startShow}>
            <div className="start-card">
              <div className="start-kicker">FactoryLab · AIAF OS</div>
              <div className="start-title">数字 ↔ 物理 · 科学发现闭环</div>
              <button className="start-btn" onClick={startShow}>▶ 播放全片（含配音）</button>
              <div className="start-hint">
                约 5 分钟 · 建议开启声音 · 当前：{lang === 'zh' ? '中文配音' : '英文配音'} + 中文字幕
                <br />（播放后可用按钮或快捷键 L 切换中/英配音）
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
