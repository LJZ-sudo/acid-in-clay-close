import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Outlet } from 'react-router-dom'
import { Layout, App as AntdApp } from 'antd'
import Header from './Header'
import Sidebar from './Sidebar'
import { RouteErrorBoundary } from '../common/RouteErrorBoundary'
import { useUIStore, useDataStore, useAgentStore } from '../../stores'
import { wsService } from '../../services/websocket'
import { WS_EVENTS } from '../../utils/constants'
import { controlApi } from '../../api/control'

const { Content } = Layout

/**
 * MainLayout — antd Layout shell.
 *
 * Plan-X (paper/frontend_redesign_v2_zh.md): Stage0 主线 + Stage1 二级。
 * The websocket subscription block is unchanged from v1 — proven to work.
 * react-hot-toast was replaced by antd `App.useApp().message` (now obtained
 * inside views as needed).
 */
function MainLayout() {
  const { t } = useTranslation()
  const { message } = AntdApp.useApp()
  const { setWsConnected, handleStatusUpdate } = useUIStore()
  const {
    setTemperature,
    addTemperaturePoint,
    addConductivityPoint,
    addMeasurement,
    addPhaseTransition,
  } = useDataStore()
  const { handleSSEEvent, setAutoDecision } = useAgentStore()

  useEffect(() => {
    const normalizeTimestamp = (ts) => {
      if (ts == null) return Date.now()
      const n = Number(ts)
      if (!Number.isFinite(n)) return Date.now()
      return n < 1e12 ? n * 1000 : n
    }
    const toNumber = (v) => {
      const n = Number(v)
      return Number.isFinite(n) ? n : null
    }
    const getCurrentTemp = (o = {}) =>
      toNumber(o.current ?? o.temperature ?? o.current_temp ?? o.current_temperature)
    const getTargetTemp = (o = {}) =>
      toNumber(o.target ?? o.target_temp ?? o.target_temperature)

    wsService.connect()
      .then(() => {
        setWsConnected(true)
        wsService.subscribe({
          channels: ['temperature', 'measurement', 'log', 'phase_transition'],
          last_seq: 0,
        })
      })
      .catch((err) => {
        console.error('WebSocket connect failed:', err)
        message.error(t('messages.wsFailed') || 'WebSocket 连接失败')
      })

    const subs = []
    subs.push(wsService.on(WS_EVENTS.CONNECT,    () => setWsConnected(true)))
    subs.push(wsService.on(WS_EVENTS.DISCONNECT, () => setWsConnected(false)))
    subs.push(wsService.on(WS_EVENTS.HEARTBEAT,  () => setWsConnected(true)))
    subs.push(wsService.on(WS_EVENTS.UNSTABLE,   () => setWsConnected(false)))

    subs.push(wsService.on(WS_EVENTS.STATUS_CHANGE, (data) => {
      handleStatusUpdate(data)
      if (data?.autonomous_mode !== undefined) setAutoDecision(Boolean(data.autonomous_mode))
      const cur = getCurrentTemp(data)
      const tgt = getTargetTemp(data)
      if (cur !== null || tgt !== null) {
        setTemperature(cur, tgt)
        if (cur !== null) addTemperaturePoint({ value: cur, target: tgt, timestamp: normalizeTimestamp(data.timestamp) })
      }
    }))

    subs.push(wsService.on(WS_EVENTS.TEMPERATURE_UPDATE, (data) => {
      if (data?.autonomous_mode !== undefined) setAutoDecision(Boolean(data.autonomous_mode))
      const cur = getCurrentTemp(data)
      const tgt = getTargetTemp(data)
      if (cur === null) return
      setTemperature(cur, tgt)
      addTemperaturePoint({ value: cur, target: tgt, timestamp: normalizeTimestamp(data.timestamp) })
    }))

    subs.push(wsService.on(WS_EVENTS.MEASUREMENT_COMPLETE, (data) => {
      const m = data?.measurement || data || {}
      const ts = normalizeTimestamp(data?.timestamp || m.timestamp)
      const temp = toNumber(m.temperature ?? m.temperature_C ?? m.temp_C)
      const cond = toNumber(m.conductivity ?? m.conductivity_S_per_cm ?? m.conductivity_S_cm ?? m.sigma)
      addMeasurement({ ...m, timestamp: ts, temperature: temp, conductivity: cond })
      if (cond !== null) {
        addConductivityPoint({
          value: cond,
          temperature: temp,
          timestamp: ts,
          measurement_id: m.id || m.measurement_id || null,
          step_idx: Number(m.step_idx ?? data?.step_idx ?? 0) || null,
        })
      }
      if (temp !== null) {
        message.info(`测量完成 @ ${temp.toFixed(2)}°C`)
      }
    }))

    subs.push(wsService.on(WS_EVENTS.PHASE_TRANSITION, (data) => {
      const tr = data?.transition || data || {}
      const norm = {
        ...tr,
        temperature: toNumber(tr.temperature ?? tr.temperature_C ?? tr.T_transition),
        conductivity: toNumber(tr.conductivity ?? tr.conductivity_S_per_cm ?? tr.sigma),
        timestamp: normalizeTimestamp(data?.timestamp || tr.timestamp),
      }
      addPhaseTransition(norm)
      if (norm.temperature !== null) {
        message.warning(`检测到相变 @ ${norm.temperature.toFixed(2)}°C`)
      }
    }))

    subs.push(wsService.on(WS_EVENTS.THOUGHT_CHAIN_EVENT, (data) => handleSSEEvent(data)))

    let timer = null
    const pollStatus = async () => {
      try {
        const r = await controlApi.getStatus()
        const s = r?.data || {}
        handleStatusUpdate(s)
        if (s?.autonomous_mode !== undefined) setAutoDecision(Boolean(s.autonomous_mode))
        const cur = getCurrentTemp(s)
        const tgt = getTargetTemp(s)
        if (cur !== null || tgt !== null) {
          setTemperature(cur, tgt)
          if (cur !== null) addTemperaturePoint({ value: cur, target: tgt, timestamp: Date.now() })
        }
      } catch { /* swallow */ }
    }
    pollStatus()
    timer = setInterval(pollStatus, 3000)

    return () => {
      subs.forEach((u) => u && u())
      if (timer) clearInterval(timer)
      wsService.disconnect()
    }
  }, [setWsConnected, handleStatusUpdate, setTemperature, addTemperaturePoint, addConductivityPoint, addMeasurement, addPhaseTransition, handleSSEEvent, setAutoDecision, t, message])

  return (
    <Layout style={{ height: '100vh' }}>
      <Header />
      <Layout>
        <Sidebar />
        <Content style={{ padding: 20, overflow: 'auto', background: '#f0f2f5' }}>
          <RouteErrorBoundary>
            <Outlet />
          </RouteErrorBoundary>
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout
