import React, { useEffect, useRef } from 'react'
import * as echarts from 'echarts'

export default function Chart({ option, style }) {
  const ref = useRef(null)
  const inst = useRef(null)

  useEffect(() => {
    inst.current = echarts.init(ref.current, null, { renderer: 'canvas' })
    const onResize = () => inst.current && inst.current.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      inst.current && inst.current.dispose()
    }
  }, [])

  useEffect(() => {
    if (inst.current && option) {
      inst.current.setOption(option, true)
      inst.current.resize()
    }
  }, [option])

  return <div ref={ref} style={{ width: '100%', height: '100%', ...style }} />
}
