import { useEffect, useState } from 'react'

// Staged reveal: when `active` becomes true, advances `step` 0..steps every `interval` ms.
// Resets to 0 when inactive so re-entering the scene replays the animation.
export function useReveal(active, steps, interval = 900) {
  const [step, setStep] = useState(0)
  useEffect(() => {
    if (!active) { setStep(0); return }
    setStep(1)
    let i = 1
    const id = setInterval(() => {
      i += 1
      setStep(i)
      if (i >= steps) clearInterval(id)
    }, interval)
    return () => clearInterval(id)
  }, [active, steps, interval])
  return step
}
