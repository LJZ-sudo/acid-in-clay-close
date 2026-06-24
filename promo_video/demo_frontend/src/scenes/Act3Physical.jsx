import React from 'react'
import { useReveal } from '../useReveal.js'

// ACT3 hardware scene. Flow:
//   1) narration (voiceover) plays first  →  video shows first frame, paused.
//   2) when narration ends (App sets narrationEnded), the video auto-plays
//      WITH its own sound (background music / lab audio), unmuted.
//   3) the player exposes native controls so the viewer can pause / scrub / fullscreen.
// Drop the recording at: src/assets/hardware_demo.mp4
let videoSrc = null
try {
  videoSrc = new URL('../assets/hardware_demo.mp4', import.meta.url).href
} catch (e) { videoSrc = null }

export default function Act3Physical({ active, playing, narrationEnded, onComplete }) {
  const s = useReveal(active, 2, 400)
  const ref = React.useRef(null)
  const [hasVideo, setHasVideo] = React.useState(true)
  const [started, setStarted] = React.useState(false)
  const [needTap, setNeedTap] = React.useState(false)

  // start the video (with sound) once the narration has finished
  React.useEffect(() => {
    const v = ref.current
    if (!v) return
    if (active && playing && narrationEnded && !started) {
      v.muted = false
      v.volume = 0.25
      v.currentTime = 0
      v.play().then(() => { setStarted(true); setNeedTap(false) })
            .catch(() => { setNeedTap(true) })
    }
  }, [active, playing, narrationEnded, started])

  // pause / resume with the global play state; reset when leaving the scene
  React.useEffect(() => {
    const v = ref.current
    if (!v) return
    if (!active) { v.pause(); setStarted(false); setNeedTap(false); return }
    if (!playing) v.pause()
    else if (started) v.play().catch(() => {})
  }, [active, playing, started])

  const manualStart = () => {
    const v = ref.current
    if (!v) return
    v.muted = false
    v.volume = 0.25
    v.play().then(() => { setStarted(true); setNeedTap(false) }).catch(() => {})
  }

  const waiting = !narrationEnded && !started

  return (
    <>
      <div className="kicker rv on">物理世界 · 硬件闭环执行</div>
      <h1 className="title rv on">真实宽温 <span className="accent-g">EIS 测量</span></h1>
      <p className="subtitle rv on">数字世界选出的候选，进入物理世界：真实电化学工作站，从常温一路降到极低温。</p>

      <div className={'videoframe rv' + (s >= 1 ? ' on' : '')} style={{ marginTop: '1.6vh' }}>
        <div className="live-badge"><span className="dot" />实时测量</div>
        {videoSrc && hasVideo ? (
          <>
            <video ref={ref} src={videoSrc} playsInline controls preload="auto"
                   onError={() => setHasVideo(false)}
                   onEnded={() => { if (onComplete) onComplete() }} />
            {waiting && (
              <div className="video-veil block">
                <div className="vv-mic">🎙</div>
                <div className="vv-text">配音讲解中 · 稍后自动播放硬件实拍（含原声）</div>
              </div>
            )}
            {needTap && (
              <button className="video-tap" onClick={manualStart}>▶ 点击播放硬件实拍（含原声）</button>
            )}
          </>
        ) : (
          <div className="ph">
            <div className="big">⎍ 硬件测试录屏占位</div>
            <div>把硬件录屏放到 <code>src/assets/hardware_demo.mp4</code> 后自动嵌入此处</div>
          </div>
        )}
      </div>
    </>
  )
}
