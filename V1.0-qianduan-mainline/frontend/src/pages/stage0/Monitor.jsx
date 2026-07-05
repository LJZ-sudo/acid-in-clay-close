import { useMemo, useState, useEffect, useRef } from 'react'
import {
  Card, Row, Col, Statistic, Tag, Button, Space, App as AntdApp, Empty,
  Tabs, List, Typography, Switch, Progress, Descriptions, Collapse,
} from 'antd'
import {
  PauseCircleOutlined, PlayCircleOutlined, StopOutlined, ThunderboltOutlined,
  RobotOutlined, LineChartOutlined, FileTextOutlined, SafetyCertificateOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { useTranslation } from 'react-i18next'
import { useUIStore, useDataStore, useAgentStore } from '../../stores'
import { controlApi } from '../../api/control'
import AIThinkingPanel from './AIThinkingPanel'
import GovernancePanel from './GovernancePanel'

const { Text } = Typography

/**
 * Monitor — 复刻旧 Vue ThoughtChainConsole 风格的 cockpit。
 *
 * 布局：左主区 3 Tab（实时 / 思考链 / Raw Log）+ 右侧固定状态栏。
 * 实时 Tab：温度曲线 + Arrhenius 实时数据点（点逐步增长，不分段）
 * 思考链 Tab：filter + 仅 LLM 调用 toggle + cards
 * Raw Log Tab：原始事件 JSON 流
 */
const TYPE_COLOR = {
  PLAN: 'blue', TRIGGER: 'cyan', ACTION: 'geekblue', AGENT_CALL: 'purple',
  TOOL_CALL: 'gold', CRITIC: 'orange', PLANNER: 'magenta', ERROR: 'red', COMPLETE: 'green',
  LLM_CALL: 'purple',
  // Agent / phase
  AGENT_DECISION: 'purple', AGENT_CALL_STARTED: 'purple', AGENT_DECISION_FAILED: 'volcano',
  AGENT_FINE_SCAN: 'magenta', AGENT_FINE_BAND_TICK: 'magenta', AGENT_FINE_BAND_EXIT: 'magenta',
  AGENT_ABORT: 'red', AGENT_BACKTRACK: 'orange', AGENT_RE_MEASURE: 'gold',
  PHASE_TRANSITION_DETECTED: 'magenta',
  // Temperature / stability
  SET_T: 'cyan', WAIT_STABLE_ARRIVAL_START: 'cyan', WAIT_STABLE_ARRIVED: 'green',
  WAIT_STABLE_DRIFT: 'orange', WAIT_STABLE_TIMEOUT: 'red', WAIT_STABLE: 'green',
  COOL_TO_START_STARTED: 'cyan', COOL_TO_START_DONE: 'green', COOL_TO_START_FAILED: 'red',
  REHEAT_SETTLE_STARTED: 'orange', REHEAT_SETTLE_DONE: 'green',
  FINALIZE_REHEAT_STARTED: 'orange', FINALIZE_REHEAT_DONE: 'green', FINALIZE_REHEAT_FAILED: 'red',
  // Measurement
  EIS_RUN: 'blue', MEASUREMENT_COMPLETED: 'green', MEASUREMENT_SKIPPED: 'orange',
  Rb_FIT: 'cyan', QC_GRADE: 'cyan', ARRHENIUS_UPDATED: 'geekblue',
  CHI_MEASUREMENT_STARTED: 'blue', CHI_MEASUREMENT_COMPLETED: 'green', CHI_MEASUREMENT_FAILED: 'red',
  // Safety
  SAFETY_RB_FUSE: 'red', SAFETY_CONDUCTIVITY_FUSE: 'red', SAFETY_CONSECUTIVE_FAIL_FUSE: 'red',
  // Post-processing
  POST_PROCESSING_STARTED: 'gold', POST_PROCESSING_COPY_DONE: 'cyan',
  POST_PROCESSING_COMPLETED: 'green', POST_PROCESSING_FAILED: 'red',
  STAGE0_STARTED: 'gold', STAGE0_COMPLETED: 'green', STAGE0_FAILED: 'red',
  STAGE0_GLOBAL_ARRHENIUS_STARTED: 'gold', STAGE0_GLOBAL_ARRHENIUS_COMPLETED: 'green',
  STAGE0_GLOBAL_ARRHENIUS_FAILED: 'red', STAGE0_GLOBAL_ARRHENIUS_SKIPPED: 'default',
  CLOSURE_REPORT_STARTED: 'processing', CLOSURE_REPORT_COMPLETED: 'green',
  CLOSURE_REPORT_FAILED: 'error',
  STAGE1_STARTED: 'geekblue', STAGE1_SKIPPED: 'default', STAGE1_COMPLETED: 'green', STAGE1_FAILED: 'red',
  RUN_MANIFEST_WRITTEN: 'green', RUN_MANIFEST_FAILED: 'red',
  RESUME_LOADED: 'gold', RESUME_SKIPPED: 'default',
}

const DECISION_TYPES = new Set([
  'PLAN', 'PLANNER', 'ACTION', 'AGENT_CALL', 'AGENT_CALL_STARTED',
  'AGENT_DECISION', 'AGENT_FINE_SCAN', 'AGENT_ABORT', 'AGENT_BACKTRACK',
  'AGENT_RE_MEASURE', 'LLM_CALL',
])
const OBSERVATION_TYPES = new Set([
  'CRITIC', 'TOOL_CALL', 'COMPLETE', 'TRIGGER',
  'MEASUREMENT_COMPLETED', 'MEASUREMENT_SKIPPED', 'Rb_FIT', 'QC_GRADE',
  'WAIT_STABLE_ARRIVED', 'WAIT_STABLE', 'WAIT_STABLE_DRIFT', 'WAIT_STABLE_TIMEOUT',
  'ARRHENIUS_UPDATED', 'PHASE_TRANSITION_DETECTED',
])

const AGENT_DECISION_TYPES = new Set([
  'AGENT_DECISION', 'AGENT_CALL_STARTED', 'AGENT_FINE_SCAN', 'AGENT_ABORT',
  'AGENT_BACKTRACK', 'AGENT_RE_MEASURE', 'AGENT_DECISION_FAILED',
])

// 关键字高亮（Raw Log 用）：°C / Rb / R² / 相变 / 熔断
const HIGHLIGHT_RULES = [
  { re: /([-+]?\d+(?:\.\d+)?\s*°?C)/g, color: '#4fc3f7' },
  { re: /(Rb[_\s]*ohm)/gi, color: '#ffd54f' },
  { re: /(conductivity[_\s]*S[_\s]*c?m)/gi, color: '#aed581' },
  { re: /(r[_\s]*squared|R²|R\^2)/gi, color: '#ce93d8' },
  { re: /(PHASE_TRANSITION_DETECTED|AGENT_DECISION|FINE_GRAINED_SCAN|ABORT)/g, color: '#ff8a65' },
  { re: /(CLOSURE_REPORT_|STAGE1_SKIPPED|POST_PROCESSING_)/g, color: '#81c784' },
  { re: /(SAFETY_[A-Z_]+|_FUSE)/g, color: '#ef5350' },
  { re: /(\b相变\b|\b熔断\b)/g, color: '#ff8a65' },
]

function highlightJSON(jsonStr) {
  const parts = [{ text: jsonStr, color: null }]
  for (const rule of HIGHLIGHT_RULES) {
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i]
      if (p.color) continue
      const segs = []
      let last = 0
      let m
      const re = new RegExp(rule.re.source, rule.re.flags)
      while ((m = re.exec(p.text)) !== null) {
        if (m.index > last) segs.push({ text: p.text.slice(last, m.index), color: null })
        segs.push({ text: m[0], color: rule.color })
        last = m.index + m[0].length
      }
      if (segs.length > 0) {
        if (last < p.text.length) segs.push({ text: p.text.slice(last), color: null })
        parts.splice(i, 1, ...segs)
      }
    }
  }
  return parts
}

function Monitor() {
  const { t } = useTranslation('v3')
  const { message } = AntdApp.useApp()
  const isRunning = useUIStore((s) => s.experimentRunning)
  const isPaused = useUIStore((s) => s.experimentPaused)
  const controllerConnected = useUIStore((s) => s.controllerConnected)
  const currentTemp = useDataStore((s) => s.currentTemperature)
  const targetTemp = useDataStore((s) => s.targetTemperature)
  const tempHistory = useDataStore((s) => s.temperatureHistory)
  const condHistory = useDataStore((s) => s.conductivityHistory)
  const phaseTransitions = useDataStore((s) => s.phaseTransitions)
  const measurements = useDataStore((s) => s.measurements)

  const [busy, setBusy] = useState(false)

  const callControl = async (label, fn) => {
    setBusy(true)
    try { await fn(); message.success(`${label} ✓`) }
    catch (err) { message.error(`${label} failed: ${err?.response?.data?.detail || err?.message || 'unknown'}`) }
    finally { setBusy(false) }
  }

  const tempOption = useMemo(() => buildTempChart(tempHistory, phaseTransitions), [tempHistory, phaseTransitions])
  const arrLiveOption = useMemo(() => buildArrLiveChart(measurements), [measurements])

  const statusTag = !controllerConnected
    ? <Tag>{t('app.controllerDisconnected')}</Tag>
    : isRunning
      ? (isPaused ? <Tag color="warning">{t('home.statusPaused')}</Tag> : <Tag color="processing">{t('home.statusRunning')}</Tag>)
      : <Tag color="default">{t('home.statusIdle')}</Tag>

  return (
    <div style={{ maxWidth: 1500, margin: '0 auto' }}>
      <Card
        title={<Space>{t('monitor.title')} {statusTag}</Space>}
        extra={
          <Space>
            <Button icon={isPaused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
              loading={busy} disabled={!controllerConnected || !isRunning}
              onClick={() => callControl(isPaused ? t('monitor.resume') : t('monitor.pause'),
                isPaused ? controlApi.resume : controlApi.pause)}>
              {isPaused ? t('monitor.resume') : t('monitor.pause')}
            </Button>
            <Button icon={<ThunderboltOutlined />} type="primary"
              loading={busy} disabled={!controllerConnected || !isRunning}
              onClick={() => callControl(t('monitor.measureNow'), () => controlApi.measureNow({}))}>
              {t('monitor.measureNow')}
            </Button>
            <Button danger icon={<StopOutlined />}
              loading={busy} disabled={!controllerConnected || !isRunning}
              onClick={() => callControl(t('monitor.stop'), controlApi.stop)}>
              {t('monitor.stop')}
            </Button>
          </Space>
        }
        bordered={false}
        bodyStyle={{ padding: 0 }}
      >
        <Row gutter={0}>
          {/* 左主区：3 Tab */}
          <Col xs={24} lg={17} style={{ borderRight: '1px solid #f0f0f0' }}>
            <Tabs
              defaultActiveKey="rt"
              tabBarStyle={{ paddingLeft: 16, marginBottom: 0 }}
              items={[
                {
                  key: 'rt',
                  label: <Space><LineChartOutlined />{t('monitor.tabRealtime')}</Space>,
                  children: <RealtimeTab tempOption={tempOption} arrOption={arrLiveOption}
                    tempHistory={tempHistory} measurements={measurements} t={t} />,
                },
                {
                  key: 'chain',
                  label: <Space><RobotOutlined />{t('monitor.tabThoughtChain')}</Space>,
                  children: (
                    <div style={{ padding: 12, height: 620 }}>
                      <AIThinkingPanel
                        connectionStatus={controllerConnected ? 'connected' : 'disconnected'}
                      />
                    </div>
                  ),
                },
                {
                  key: 'gov',
                  label: <Space><SafetyCertificateOutlined />治理</Space>,
                  children: <GovernancePanel />,
                },
                {
                  key: 'raw',
                  label: <Space><FileTextOutlined />{t('monitor.tabRawLog')}</Space>,
                  children: <RawLogTab t={t} />,
                },
              ]}
            />
          </Col>

          {/* 右侧固定状态栏 */}
          <Col xs={24} lg={7}>
            <RightStatusPanel
              t={t}
              currentTemp={currentTemp} targetTemp={targetTemp}
              measurements={measurements} phaseTransitions={phaseTransitions}
              statusTag={statusTag}
            />
          </Col>
        </Row>
      </Card>
    </div>
  )
}

// --- 右侧状态栏 ---
function RightStatusPanel({ t, currentTemp, targetTemp, measurements, phaseTransitions, statusTag }) {
  const tempHistory = useDataStore((s) => s.temperatureHistory)
  const exp = useDataStore((s) => s.experimentParams) || {}
  // 进度估算：测量点数 / (温度跨度/平均步长)
  const total = exp.t_start != null && exp.t_end != null && exp.coarse_step
    ? Math.max(1, Math.ceil(Math.abs(exp.t_start - exp.t_end) / Number(exp.coarse_step)))
    : 100
  const done = measurements?.length || 0
  const pct = Math.min(100, Math.round((done / total) * 100))

  // 最近温度方向（简易判断）
  const trend = useMemo(() => {
    const last = (tempHistory || []).slice(-2).map((p) => p.value)
    if (last.length < 2) return ''
    return last[1] > last[0] ? '↗' : last[1] < last[0] ? '↘' : '→'
  }, [tempHistory])

  return (
    <div style={{ padding: '20px 16px' }}>
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>Status</Text>
        <div style={{ marginTop: 4 }}>{statusTag}</div>
      </div>

      <Row gutter={8} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <div style={{ background: 'linear-gradient(135deg,#5b8def,#3a6ed8)', borderRadius: 8, padding: 10, color: '#fff', textAlign: 'center' }}>
            <div style={{ fontSize: 11, opacity: 0.9 }}>{t('home.currentTemp')}</div>
            <div style={{ fontSize: 22, fontWeight: 'bold', marginTop: 4 }}>
              {currentTemp != null ? Number(currentTemp).toFixed(1) : '--'} °C {trend}
            </div>
          </div>
        </Col>
        <Col span={12}>
          <div style={{ background: 'linear-gradient(135deg,#ff7b9d,#e84393)', borderRadius: 8, padding: 10, color: '#fff', textAlign: 'center' }}>
            <div style={{ fontSize: 11, opacity: 0.9 }}>{t('monitor.targetTemp')}</div>
            <div style={{ fontSize: 22, fontWeight: 'bold', marginTop: 4 }}>
              {targetTemp != null ? Number(targetTemp).toFixed(1) : '--'} °C
            </div>
          </div>
        </Col>
      </Row>

      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#666', marginBottom: 4 }}>
          <span>{t('monitor.progress')}</span>
          <span>{done}/{total}</span>
        </div>
        <Progress percent={pct} size="small" status={pct >= 100 ? 'success' : 'active'} />
      </div>

      <Descriptions size="small" column={1} colon labelStyle={{ color: '#666', fontSize: 12 }}
        contentStyle={{ fontSize: 12, fontFamily: 'monospace' }}>
        <Descriptions.Item label={t('monitor.rangeStart')}>{exp.t_start ?? '—'} °C</Descriptions.Item>
        <Descriptions.Item label={t('monitor.rangeEnd')}>{exp.t_end ?? '—'} °C</Descriptions.Item>
        <Descriptions.Item label={t('monitor.coarse')}>{exp.coarse_step ?? '—'} °C</Descriptions.Item>
        <Descriptions.Item label={t('monitor.fine')}>{exp.fine_step ?? '—'} °C</Descriptions.Item>
        <Descriptions.Item label={t('monitor.nPhase')}>
          <Tag color={phaseTransitions?.length ? 'warning' : 'default'} style={{ margin: 0 }}>
            {phaseTransitions?.length || 0}
          </Tag>
        </Descriptions.Item>
      </Descriptions>
    </div>
  )
}

// --- 实时 Tab ---
function RealtimeTab({ tempOption, arrOption, tempHistory, measurements, t }) {
  return (
    <div style={{ padding: 16 }}>
      <Card type="inner" size="small" title={<Space><LineChartOutlined />{t('monitor.tempProfile')}</Space>}
        style={{ marginBottom: 12 }}>
        {tempHistory?.length > 0
          ? <ReactECharts option={tempOption} style={{ height: 240 }} notMerge lazyUpdate />
          : <Empty description={t('monitor.waitingTemp')} style={{ padding: 30 }} />}
      </Card>

      <Card type="inner" size="small" title={<Space><LineChartOutlined />{t('monitor.arrLive')}</Space>}>
        {measurements?.length > 0
          ? <ReactECharts option={arrOption} style={{ height: 240 }} notMerge lazyUpdate />
          : <Empty description={t('monitor.waitingMeasurement')} style={{ padding: 30 }} />}
      </Card>
    </div>
  )
}

// --- 思考链 Tab 已迁移到 ./AIThinkingPanel.jsx（复刻旧 V1.0 Vue 版 AIThinkingPanel.vue） ---
// 保留下面的工具函数（DECISION_TYPES / OBSERVATION_TYPES / highlightJSON）供 Raw Log Tab 使用。
// eslint-disable-next-line no-unused-vars
function _UnusedThoughtChainTab({ t }) {
  const events = useAgentStore((s) => s.thoughtChain) || []
  const isThinking = useAgentStore((s) => s.isThinking)
  const runId = useAgentStore((s) => s.runId)
  const [filter, setFilter] = useState('all')   // all / decision / observation
  const [llmOnly, setLlmOnly] = useState(false)

  const filtered = useMemo(() => {
    return events.filter((ev) => {
      const type = ev.event_type || ev.type || ''
      if (llmOnly && !(type === 'LLM_CALL' || type === 'AGENT_CALL')) return false
      if (filter === 'decision' && !DECISION_TYPES.has(type)) return false
      if (filter === 'observation' && !OBSERVATION_TYPES.has(type)) return false
      if (filter === 'agent' && !AGENT_DECISION_TYPES.has(type)) return false
      return true
    })
  }, [events, filter, llmOnly])

  return (
    <div style={{ padding: 16 }}>
      <Space style={{ marginBottom: 12 }} wrap>
        <Space.Compact>
          {[
            { key: 'all', label: t('monitor.chainFilterAll') },
            { key: 'decision', label: t('monitor.chainFilterDecision') },
            { key: 'observation', label: t('monitor.chainFilterObservation') },
            { key: 'agent', label: 'Agent' },
          ].map((opt) => (
            <Button key={opt.key} size="small"
              type={filter === opt.key ? 'primary' : 'default'}
              onClick={() => setFilter(opt.key)}>
              {opt.label}
            </Button>
          ))}
        </Space.Compact>
        <Space size={4}>
          <span style={{ fontSize: 12, color: '#666' }}>{t('monitor.onlyLlm')}</span>
          <Switch size="small" checked={llmOnly} onChange={setLlmOnly} />
        </Space>
        {isThinking && <Tag color="processing">{t('monitor.thinking')}</Tag>}
        {runId && <Text type="secondary" style={{ fontSize: 12 }}>run: <Text code>{runId.slice(0, 12)}...</Text></Text>}
        <Text type="secondary" style={{ fontSize: 12 }}>{filtered.length} / {events.length}</Text>
      </Space>

      <div style={{ maxHeight: 520, overflowY: 'auto' }}>
        {filtered.length === 0
          ? <Empty description={t('monitor.waitingAgent')} style={{ padding: 60 }} />
          : (
            <div>
              {[...filtered].reverse().map((ev, i) => (
                <ThoughtCard key={`${ev._local_ts || ev.timestamp || i}-${i}`} ev={ev} idx={i} />
              ))}
            </div>
          )}
      </div>
    </div>
  )
}

// eslint-disable-next-line no-unused-vars
function _UnusedThoughtCard({ ev, idx }) {
  const type = ev.event_type || ev.type || 'INFO'
  const ts = ev._local_ts || ev.timestamp || ev.ts
  const tsStr = ts ? new Date(ts).toLocaleTimeString() : ''
  const payload = ev.payload || ev
  const isAgent = AGENT_DECISION_TYPES.has(type)
  const action = payload.action
  const confidence = payload.confidence
  const reasoning = payload.reasoning
  const warnings = payload.warnings || []
  const llmCalled = payload.llm_called

  const summary = ev.message || ev.summary || (
    type === 'AGENT_DECISION' && action
      ? `${action}${payload.next_temp_target_C != null ? `  →  next ${payload.next_temp_target_C.toFixed(1)}°C` : ''}`
      : type === 'MEASUREMENT_COMPLETED'
        ? `T=${payload.temperature_C}°C  Rb=${payload.rb_ohm != null ? payload.rb_ohm.toExponential(2) : '--'}Ω  R²=${payload.r_squared != null ? payload.r_squared.toFixed(3) : '--'}`
        : type === 'WAIT_STABLE'
          ? `${payload.stable ? '已稳定' : '未稳定'}  target=${payload.target_temperature_C}°C  actual=${payload.actual_temperature_C != null ? payload.actual_temperature_C.toFixed(2) : '--'}°C`
          : (typeof payload === 'object' ? JSON.stringify(payload).slice(0, 160) : String(payload))
  )

  return (
    <div style={{
      padding: '10px 12px', background: idx % 2 ? '#fafbfc' : '#fff',
      borderRadius: 4, marginBottom: 4,
      borderLeft: isAgent ? '3px solid #722ed1' : '2px solid #e8e8e8',
    }}>
      <Space size={6} style={{ marginBottom: 6 }} wrap>
        <Tag color={TYPE_COLOR[type] || 'default'} style={{ margin: 0 }}>{type}</Tag>
        {action && <Tag color={action === 'ABORT' ? 'red' : action === 'FINE_GRAINED_SCAN' ? 'magenta' : 'blue'}>{action}</Tag>}
        {confidence != null && <Tag color="cyan">conf={Number(confidence).toFixed(2)}</Tag>}
        {llmCalled === true && <Tag color="purple">LLM</Tag>}
        {llmCalled === false && <Tag color="default">rule</Tag>}
        <Text type="secondary" style={{ fontSize: 11 }}>{tsStr}</Text>
      </Space>
      <div style={{ fontSize: 12, color: '#555', lineHeight: 1.5, paddingLeft: 4 }}>{summary}</div>
      {isAgent && (reasoning || warnings.length > 0 || payload.next_temp_target_C != null) && (
        <Collapse ghost size="small" style={{ marginTop: 4 }}
          items={[{
            key: '1',
            label: <Text type="secondary" style={{ fontSize: 11 }}>展开详情</Text>,
            children: (
              <div style={{ fontSize: 11 }}>
                {reasoning && (
                  <div style={{ marginBottom: 6 }}>
                    <Text strong>Reasoning: </Text>
                    <Text>{reasoning}</Text>
                  </div>
                )}
                {warnings.length > 0 && (
                  <div style={{ marginBottom: 6 }}>
                    <Text strong>Warnings: </Text>
                    {warnings.map((w, k) => <Tag key={k} color="orange">{w}</Tag>)}
                  </div>
                )}
                <Descriptions size="small" column={2} bordered>
                  {payload.next_temp_target_C != null && (
                    <Descriptions.Item label="next T">{payload.next_temp_target_C.toFixed(2)} °C</Descriptions.Item>
                  )}
                  {payload.step_size_K != null && (
                    <Descriptions.Item label="step">{payload.step_size_K} K</Descriptions.Item>
                  )}
                  {payload.data_quality && (
                    <Descriptions.Item label="data_quality">{payload.data_quality}</Descriptions.Item>
                  )}
                  {payload.model && (
                    <Descriptions.Item label="model">{payload.model}</Descriptions.Item>
                  )}
                  {payload.n_points != null && (
                    <Descriptions.Item label="n_points">{payload.n_points}</Descriptions.Item>
                  )}
                  {payload.rule_triggered && (
                    <Descriptions.Item label="rule" span={2}>{payload.rule_triggered}</Descriptions.Item>
                  )}
                </Descriptions>
              </div>
            ),
          }]}
        />
      )}
    </div>
  )
}

// --- Raw Log Tab ---  复刻旧 V1.0 TerminalLog.vue 视觉：
//   time | LEVEL 色块 | agent | 含 °C/Rb/R²/相变/熔断 关键字高亮的中文消息
function RawLogTab({ t }) {
  const events = useAgentStore((s) => s.thoughtChain) || []
  const [autoScroll, setAutoScroll] = useState(true)
  const [showJson, setShowJson] = useState(false)
  const [levelFilter, setLevelFilter] = useState('all')
  const scrollRef = useRef(null)

  const filtered = useMemo(() => {
    if (levelFilter === 'all') return events
    return events.filter((ev) => (ev.level || 'INFO').toUpperCase() === levelFilter)
  }, [events, levelFilter])

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [filtered.length, autoScroll])

  return (
    <div style={{ padding: 12 }}>
      <Space style={{ marginBottom: 8 }} wrap>
        <Space.Compact size="small">
          {['all', 'INFO', 'SUCCESS', 'WARNING', 'ERROR'].map((lvl) => (
            <Button key={lvl} size="small"
              type={levelFilter === lvl ? 'primary' : 'default'}
              onClick={() => setLevelFilter(lvl)}>
              {lvl === 'all' ? '全部' : lvl}
            </Button>
          ))}
        </Space.Compact>
        <Space size={4}>
          <span style={{ fontSize: 12, color: '#666' }}>自动滚动</span>
          <Switch size="small" checked={autoScroll} onChange={setAutoScroll} />
        </Space>
        <Space size={4}>
          <span style={{ fontSize: 12, color: '#666' }}>JSON 视图</span>
          <Switch size="small" checked={showJson} onChange={setShowJson} />
        </Space>
        <Text type="secondary" style={{ fontSize: 12 }}>events: {filtered.length} / {events.length}</Text>
      </Space>
      {events.length === 0
        ? <Empty description={t('monitor.rawEmpty')} style={{ padding: 60 }} />
        : (
          <div ref={scrollRef} style={{
            background: '#1e1e1e', padding: 12, borderRadius: 8,
            maxHeight: 540, overflow: 'auto',
            fontFamily: '"Consolas", "Monaco", "Courier New", monospace',
            fontSize: 12.5, lineHeight: 1.6,
            boxShadow: '0 2px 12px rgba(0,0,0,0.3)',
          }}>
            {filtered.map((ev, i) => (
              <LogLine key={`${ev._local_ts || ev.timestamp || i}-${i}`} ev={ev} showJson={showJson} />
            ))}
          </div>
        )}
    </div>
  )
}

// ---- log highlighting (旧 V1.0 TerminalLog 配色) ----
const LOG_HIGHLIGHT_RULES = [
  { re: /([-+]?\d+(?:\.\d+)?\s*°C)/g, color: '#4ec9b0' },
  { re: /(R²\s*=\s*[-+]?\d+(?:\.\d+)?)/gi, color: '#569cd6' },
  { re: /(Rb\s*=\s*[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s*Ω)/gi, color: '#ce9178' },
  { re: /(σ\s*=\s*[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s*S\/cm)/gi, color: '#aed581' },
  { re: /(QC\s*=\s*[ABCD])/g, color: '#ffd54f' },
  { re: /(step\s*#\s*\d+)/gi, color: '#9ccc65' },
  { re: /(精细扫描|fine\s*scan)/gi, color: '#ffd93d' },
  { re: /(相变|phase\s*transition)/gi, color: '#ff6b6b' },
  { re: /(熔断|FUSE)/gi, color: '#ff6b6b' },
  { re: /(成功|完成|success)/gi, color: '#6bcf7f' },
  { re: /(失败|错误|error)/gi, color: '#ff6b6b' },
  { re: /(警告|warning)/gi, color: '#ffd93d' },
]

function highlightLogMessage(text) {
  if (!text) return null
  const parts = [{ text, color: null }]
  for (const rule of LOG_HIGHLIGHT_RULES) {
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i]
      if (p.color) continue
      const segs = []
      let last = 0
      let m
      const re = new RegExp(rule.re.source, rule.re.flags)
      while ((m = re.exec(p.text)) !== null) {
        if (m.index > last) segs.push({ text: p.text.slice(last, m.index), color: null })
        segs.push({ text: m[0], color: rule.color })
        last = m.index + m[0].length
      }
      if (segs.length > 0) {
        if (last < p.text.length) segs.push({ text: p.text.slice(last), color: null })
        parts.splice(i, 1, ...segs)
      }
    }
  }
  return parts.map((p, i) => (
    <span key={i} style={p.color ? { color: p.color, fontWeight: 600 } : undefined}>{p.text}</span>
  ))
}

const LOG_LEVEL_BG = {
  INFO: '#0e639c',
  SUCCESS: '#107c10',
  WARNING: '#ca5010',
  ERROR: '#e81123',
  DEBUG: '#5c2d91',
}

function LogLine({ ev, showJson }) {
  const ts = ev._local_ts || ev.timestamp || ev.ts
  const tStr = ts ? new Date(ts).toLocaleTimeString() : ''
  const level = (ev.level || 'INFO').toUpperCase()
  const message = ev.message || `${ev.event_type || ev.type || ''}`
  return (
    <div style={{
      display: 'flex',
      gap: 12,
      padding: '4px 8px',
      marginBottom: 2,
      borderRadius: 4,
      color: '#d4d4d4',
      background: level === 'ERROR' ? 'rgba(232,17,35,0.08)'
        : level === 'WARNING' ? 'rgba(202,80,16,0.08)' : 'transparent',
      alignItems: 'flex-start',
      flexWrap: 'wrap',
    }}>
      <span style={{ color: '#858585', flexShrink: 0, fontSize: 11 }}>{tStr}</span>
      <span style={{
        display: 'inline-block',
        padding: '1px 8px',
        borderRadius: 3,
        fontSize: 10,
        fontWeight: 700,
        color: '#fff',
        minWidth: 64,
        textAlign: 'center',
        background: LOG_LEVEL_BG[level] || '#666',
        flexShrink: 0,
      }}>{level}</span>
      {ev.agent && (
        <span style={{
          color: '#6a9bce', fontWeight: 600, fontSize: 12, flexShrink: 0, minWidth: 76,
        }}>[{ev.agent}]</span>
      )}
      <span style={{ color: '#d4d4d4', flex: 1, minWidth: 0, wordBreak: 'break-word' }}>
        {highlightLogMessage(message)}
        {showJson && ev.payload && (
          <pre style={{
            margin: '4px 0 0', padding: 6,
            background: '#0d0d0d', color: '#9ccc65',
            fontSize: 10.5, lineHeight: 1.4, borderRadius: 3,
            maxHeight: 200, overflow: 'auto',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          }}>{JSON.stringify(ev.payload, null, 2)}</pre>
        )}
      </span>
    </div>
  )
}

function buildTempChart(history, transitions) {
  const data = (history || []).slice(-2000).map((p) => [p.timestamp, p.value])
  const targets = (history || []).slice(-2000).filter(p => p.target != null).map((p) => [p.timestamp, p.target])
  const marks = (transitions || []).map((t) => ({
    xAxis: t.timestamp,
    label: { formatter: '相变', position: 'end', color: '#E6A23C' },
    lineStyle: { color: '#E6A23C', type: 'dashed' },
  }))
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 26, bottom: 30 },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', name: '°C' },
    series: [
      { name: 'current', type: 'line', data, smooth: true, showSymbol: false, color: '#3b82f6',
        markLine: marks.length > 0 ? { silent: true, data: marks } : undefined },
      ...(targets.length > 0 ? [{ name: 'target', type: 'line', data: targets, smooth: true, showSymbol: false, color: '#f59e0b', lineStyle: { type: 'dashed' } }] : []),
    ],
    legend: { top: 0, right: 10, textStyle: { fontSize: 10 } },
  }
}

/**
 * Arrhenius 实时数据点：每条 measurement → (1000/T_K, ln(σ·T))。
 * 不做分段拟合，只是让点逐步出现，呈现实时积累过程。
 */
function buildArrLiveChart(measurements) {
  const pts = (measurements || [])
    .filter(m => m.temperature != null && m.conductivity != null && m.conductivity > 0)
    .map((m) => {
      const T_K = m.temperature + 273.15
      return [1000 / T_K, Math.log(m.conductivity * T_K), m.temperature]
    })
  return {
    tooltip: { trigger: 'item', formatter: (p) => `T=${p.value[2].toFixed(1)}°C<br/>1000/T=${p.value[0].toFixed(3)}<br/>ln(σT)=${p.value[1].toFixed(3)}` },
    grid: { left: 60, right: 20, top: 26, bottom: 38 },
    xAxis: { type: 'value', name: '1000/T (1/K)', nameLocation: 'center', nameGap: 24, nameTextStyle: { fontSize: 10 } },
    yAxis: { type: 'value', name: 'ln(σT)', nameLocation: 'center', nameGap: 38, nameTextStyle: { fontSize: 10 } },
    series: [{
      type: 'scatter', data: pts, symbolSize: 6, color: '#8b5cf6',
      // 让最新一点突出
      itemStyle: { borderColor: '#fff', borderWidth: 1 },
    }],
  }
}

export default Monitor
