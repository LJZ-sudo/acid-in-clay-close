import { useMemo, useRef, useEffect, useState } from 'react'
import { Tag, Empty, Space, Switch, Tooltip, Button, Typography } from 'antd'
import { useAgentStore } from '../../stores'

const { Text } = Typography

/**
 * AIThinkingPanel —— React 复刻旧 Vue 版 AIThinkingPanel.vue 的思考链视图。
 *
 * 视觉特征（与旧 V1.0 一致）：
 *  - 紫色渐变 header + AI 头像 + "正在思考 / 决策完成" 标签 + 连接状态大号 tag。
 *  - 仅 LLM 调用开关：过滤只看真正调用 LLM 的事件。
 *  - 卡片列表：左侧色条按类型变色（plan / trigger / action / agent_call / result / error），
 *    顶部状态图标（loading / 已完成 / 等待），右侧 timestamp，点击展开。
 *  - 展开内容分块：推理过程、LLM 输入（user_prompt / context_json）、系统提示摘录、
 *    LLM 输出（raw_response）、解析后的结构化 JSON、附加 Payload、决策结果（action list）。
 *  - 底部：最后一次决策的时间 + confidence。
 */
const LEVEL_COLOR = {
  SUCCESS: 'green',
  WARNING: 'orange',
  ERROR: 'red',
  DEBUG: 'default',
  INFO: 'blue',
}

const STEP_BORDER = {
  plan: '#667eea',
  trigger: '#E6A23C',
  action: '#67C23A',
  agent_call: '#409EFF',
  result: '#a18cd1',
  error: '#F56C6C',
  normal: '#dcdfe6',
  safety: '#F56C6C',
  finalize: '#a18cd1',
  measurement: '#67C23A',
  temperature: '#3498db',
}

const TYPE_TO_STYLE = {
  // Agent / planner — purple/blue
  AGENT_CALL_STARTED: { kind: 'plan', title: 'Agent 调用启动', icon: '🧠' },
  AGENT_DECISION: { kind: 'action', title: 'Agent 决策', icon: '✨' },
  AGENT_DECISION_FAILED: { kind: 'error', title: 'Agent 决策失败', icon: '⚠️' },
  AGENT_FINE_SCAN: { kind: 'trigger', title: 'Agent 触发精细扫描', icon: '🔍' },
  AGENT_FINE_BAND_TICK: { kind: 'trigger', title: 'Fine band 进行中', icon: '·' },
  AGENT_FINE_BAND_EXIT: { kind: 'plan', title: '退出 Fine band', icon: '↩' },
  AGENT_ABORT: { kind: 'error', title: 'Agent 终止运行', icon: '⛔' },
  AGENT_BACKTRACK: { kind: 'trigger', title: 'Agent 回退', icon: '⤺' },
  AGENT_RE_MEASURE: { kind: 'trigger', title: 'Agent 重测', icon: '↻' },
  AGENT_CONFIG: { kind: 'plan', title: 'Agent 配置', icon: '⚙' },
  PHASE_TRANSITION_DETECTED: { kind: 'trigger', title: '🚨 相变检测', icon: '🚨' },
  // Temperature & stability
  SET_T: { kind: 'temperature', title: '下发目标温度', icon: '🌡' },
  WAIT_STABLE_ARRIVAL_START: { kind: 'temperature', title: '等待到温', icon: '⏳' },
  WAIT_STABLE_ARRIVED: { kind: 'temperature', title: '到达目标温度', icon: '✓' },
  WAIT_STABLE_DRIFT: { kind: 'trigger', title: '温度漂移', icon: '⚠' },
  WAIT_STABLE_TIMEOUT: { kind: 'error', title: '到温超时', icon: '⏱' },
  WAIT_STABLE: { kind: 'temperature', title: '稳定验证', icon: '✓' },
  COOL_TO_START_STARTED: { kind: 'temperature', title: '起点降温启动', icon: '❄' },
  COOL_TO_START_DONE: { kind: 'temperature', title: '起点降温到位', icon: '✓' },
  COOL_TO_START_FAILED: { kind: 'error', title: '起点降温失败', icon: '⚠' },
  REHEAT_SETTLE_STARTED: { kind: 'trigger', title: '回温热惰性等待', icon: '🔥' },
  REHEAT_SETTLE_DONE: { kind: 'temperature', title: '回温稳定完成', icon: '✓' },
  // Measurement
  EIS_RUN: { kind: 'measurement', title: 'EIS 测量启动', icon: '⚡' },
  CHI_MEASUREMENT_STARTED: { kind: 'measurement', title: 'CHI 测量启动', icon: '⚡' },
  CHI_MEASUREMENT_COMPLETED: { kind: 'measurement', title: 'CHI 测量完成', icon: '✓' },
  CHI_MEASUREMENT_FAILED: { kind: 'error', title: 'CHI 测量失败', icon: '✗' },
  MEASUREMENT_COMPLETED: { kind: 'measurement', title: '测量完成', icon: '📊' },
  MEASUREMENT_SKIPPED: { kind: 'trigger', title: '跳过测量', icon: '⏭' },
  Rb_FIT: { kind: 'result', title: 'Rb 拟合', icon: 'Σ' },
  QC_GRADE: { kind: 'result', title: 'QC 评级', icon: 'Q' },
  ARRHENIUS_UPDATED: { kind: 'result', title: 'Arrhenius 更新', icon: '∝' },
  // Safety
  SAFETY_RB_FUSE: { kind: 'safety', title: '⚠ Rb 熔断', icon: '⚠' },
  SAFETY_CONDUCTIVITY_FUSE: { kind: 'safety', title: '⚠ 电导率熔断', icon: '⚠' },
  SAFETY_CONSECUTIVE_FAIL_FUSE: { kind: 'safety', title: '⚠ 连续失败熔断', icon: '⚠' },
  // Finalize
  FINALIZE_REHEAT_STARTED: { kind: 'finalize', title: '回温到 18°C 启动', icon: '🛡' },
  FINALIZE_REHEAT_DONE: { kind: 'finalize', title: '回温到 18°C 完成', icon: '✓' },
  FINALIZE_REHEAT_FAILED: { kind: 'error', title: '回温到 18°C 失败', icon: '⚠' },
  FINALIZE_REHEAT_SKIPPED: { kind: 'normal', title: '回温步骤跳过', icon: '·' },
  STAGE0_GLOBAL_ARRHENIUS_STARTED: { kind: 'finalize', title: '全局 Arrhenius 启动', icon: '∝' },
  STAGE0_GLOBAL_ARRHENIUS_COMPLETED: { kind: 'finalize', title: '全局 Arrhenius 完成', icon: '∝' },
  STAGE0_GLOBAL_ARRHENIUS_FAILED: { kind: 'error', title: '全局 Arrhenius 失败', icon: '⚠' },
  STAGE0_GLOBAL_ARRHENIUS_SKIPPED: { kind: 'normal', title: '全局 Arrhenius 跳过', icon: '·' },
  RUN_MANIFEST_WRITTEN: { kind: 'finalize', title: '运行清单已写入', icon: '📝' },
  RUN_MANIFEST_FAILED: { kind: 'error', title: '运行清单写入失败', icon: '⚠' },
  RESUME_LOADED: { kind: 'plan', title: '断点续测 · 恢复', icon: '↻' },
  RESUME_SKIPPED: { kind: 'normal', title: '断点续测 · 跳过', icon: '·' },
  RESUME_CONTINUE: { kind: 'plan', title: '断点续测 · 继续', icon: '▶' },
  // Post-processing
  POST_PROCESSING_STARTED: { kind: 'plan', title: '自动后处理启动', icon: '⚙' },
  POST_PROCESSING_COPY_DONE: { kind: 'plan', title: '后处理 · 文件复制完成', icon: '📁' },
  POST_PROCESSING_COMPLETED: { kind: 'finalize', title: '自动后处理完成', icon: '✓' },
  POST_PROCESSING_FAILED: { kind: 'error', title: '自动后处理失败', icon: '⚠' },
  STAGE0_STARTED: { kind: 'plan', title: 'Stage0 处理启动', icon: '◐' },
  STAGE0_COMPLETED: { kind: 'finalize', title: 'Stage0 处理完成', icon: '✓' },
  STAGE0_FAILED: { kind: 'error', title: 'Stage0 处理失败', icon: '⚠' },
  CLOSURE_REPORT_STARTED: { kind: 'plan', title: 'Closure 报告生成中', icon: '◐' },
  CLOSURE_REPORT_COMPLETED: { kind: 'finalize', title: 'Closure 报告完成', icon: '✓' },
  CLOSURE_REPORT_FAILED: { kind: 'error', title: 'Closure 生成失败', icon: '⚠' },
  STAGE1_STARTED: { kind: 'plan', title: 'Stage1 优化启动', icon: '◑' },
  STAGE1_SKIPPED: { kind: 'normal', title: 'Stage1 BO 已跳过', icon: '⏭' },
  STAGE1_COMPLETED: { kind: 'finalize', title: 'Stage1 优化完成', icon: '✓' },
  STAGE1_FAILED: { kind: 'error', title: 'Stage1 优化失败', icon: '⚠' },
  EXPERIMENT_COMPLETED: { kind: 'finalize', title: '实验完成', icon: '🎉' },
  EVIDENCE_PACKAGE_SAVED: { kind: 'result', title: '证据包已保存', icon: '📦' },
  ERROR: { kind: 'error', title: '错误', icon: '⚠' },
}

function classifyEvent(ev) {
  const type = ev.event_type || ev.type || 'INFO'
  const style = TYPE_TO_STYLE[type] || { kind: 'normal', title: type, icon: '•' }
  return { type, style }
}

function isLlmRoundtrip(ev) {
  const type = ev.event_type || ev.type
  if (type === 'AGENT_DECISION' && ev.payload?.llm_called) return true
  if (type === 'AGENT_CALL_STARTED') return true
  if (type === 'CLOSURE_REPORT_COMPLETED' && (ev.payload?.llm_used ?? ev.llm_used)) return true
  return false
}

// 关键词高亮规则（与旧 V1.0 TerminalLog formatMessage 风格一致）
const SUMMARY_HIGHLIGHTS = [
  { re: /([-+]?\d+(?:\.\d+)?\s*°C)/g, color: '#4ec9b0' },              // 温度
  { re: /(R²\s*=\s*[-+]?\d+(?:\.\d+)?)/gi, color: '#569cd6' },          // R²
  { re: /(Rb\s*=\s*[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s*Ω)/gi, color: '#ce9178' }, // Rb
  { re: /(σ\s*=\s*[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s*S\/cm)/gi, color: '#aed581' }, // σ
  { re: /(QC\s*=\s*[ABCD])/g, color: '#ffd54f' },                       // QC 评级
  { re: /(相变|熔断|FINE_GRAINED_SCAN|ABORT|失败|错误)/g, color: '#ff6b6b' },
  { re: /(精细扫描|稳定|成功|完成)/g, color: '#6bcf7f' },
]

function highlightSummary(text) {
  if (!text) return null
  const parts = [{ text, color: null }]
  for (const rule of SUMMARY_HIGHLIGHTS) {
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

function buildSummary(type, p) {
  if (!p || typeof p !== 'object') return ''
  if (type === 'MEASUREMENT_COMPLETED') {
    const T = p.temperature_C
    const rb = p.rb_ohm != null ? Number(p.rb_ohm).toExponential(2) : '--'
    const r2 = p.r_squared != null ? Number(p.r_squared).toFixed(3) : '--'
    const sigma = p.conductivity_S_cm != null ? Number(p.conductivity_S_cm).toExponential(2) : '--'
    return `T=${T}°C   Rb=${rb} Ω   σ=${sigma} S/cm   R²=${r2}`
  }
  if (type === 'AGENT_DECISION') {
    const action = p.action || 'CONTINUE'
    const next = p.next_temp_target_C != null ? Number(p.next_temp_target_C).toFixed(1) : null
    return `${action}${next != null ? `  →  下一点 ${next}°C` : ''}`
  }
  if (type === 'WAIT_STABLE') {
    const t = p.actual_temperature_C != null ? Number(p.actual_temperature_C).toFixed(2) : '--'
    return `${p.stable ? '✓ 已稳定' : '✗ 未稳定'}  target=${p.target_temperature_C}°C  actual=${t}°C`
  }
  if (type === 'SET_T') return `target = ${p.target_temperature_C}°C`
  if (type === 'EIS_RUN') return `at ${p.temperature_C}°C`
  if (type === 'COOL_TO_START_STARTED') return `cooling to ${p.t_start_C}°C`
  if (type === 'COOL_TO_START_DONE') return `arrived in ${p.arrival_seconds?.toFixed?.(0)} s`
  if (type === 'FINALIZE_REHEAT_STARTED' || type === 'FINALIZE_REHEAT_DONE') return `target = ${p.target_C}°C`
  if (type === 'SAFETY_RB_FUSE') return `Rb=${Number(p.rb_ohm).toExponential(2)} > ${Number(p.threshold).toExponential(2)} Ω`
  if (type === 'SAFETY_CONDUCTIVITY_FUSE') return `σ=${Number(p.conductivity_S_cm).toExponential(2)} < ${Number(p.threshold).toExponential(2)} S/cm`
  if (type === 'SAFETY_CONSECUTIVE_FAIL_FUSE') return `${p.consecutive_failures} 次连续失败 ≥ ${p.threshold}`
  if (type === 'STAGE0_GLOBAL_ARRHENIUS_COMPLETED') {
    const seg = p.n_segments ?? '--'
    return `best=${p.best_model_type || '--'}, segments=${seg}, conf=${p.confidence != null ? Number(p.confidence).toFixed(2) : '--'}`
  }
  if (type === 'CLOSURE_REPORT_COMPLETED') {
    return `llm=${p.llm_used}  sample=${p.sample_id || '--'}`
  }
  if (type === 'CLOSURE_REPORT_STARTED') {
    return `use_llm=${p.use_llm}  sample=${p.sample_id || '--'}`
  }
  if (type === 'STAGE1_SKIPPED') {
    return String(p.reason || '').slice(0, 120)
  }
  if (type === 'POST_PROCESSING_COMPLETED') {
    return p.stage1_skipped ? 'Stage1 未运行（冷启动）' : `sample=${p.sample_id || '--'}`
  }
  return null
}

function StepCard({ ev, defaultExpanded }) {
  const { type, style } = classifyEvent(ev)
  const p = {
    ...(typeof ev === 'object' && ev !== null ? ev : {}),
    ...(typeof ev?.payload === 'object' && ev.payload !== null ? ev.payload : {}),
  }
  const ts = ev._local_ts || ev.timestamp || ev.ts
  const tsStr = ts ? new Date(ts).toLocaleTimeString() : ''
  const [expanded, setExpanded] = useState(defaultExpanded)

  // Backend now sends a rich Chinese narrative in ev.message — prefer it.
  // The local buildSummary stays as a fallback for older events without one.
  const summary = ev.message || buildSummary(type, p) || ev.summary || ''
  const level = ev.level || 'INFO'
  const agentName = ev.agent
  const reasoning = p.reasoning
  const warnings = Array.isArray(p.warnings) ? p.warnings : []
  const action = p.action
  const confidence = p.confidence
  const llmCalled = p.llm_called
  const nextC = p.next_temp_target_C
  const dataQuality = p.data_quality

  const isAgent = type.startsWith('AGENT_') || type === 'PHASE_TRANSITION_DETECTED'
  const isError = style.kind === 'error' || style.kind === 'safety'

  const borderColor = STEP_BORDER[style.kind] || STEP_BORDER.normal

  return (
    <div style={{
      background: '#fff',
      borderRadius: 10,
      borderLeft: `3px solid ${borderColor}`,
      marginBottom: 10,
      boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
      transition: 'all 0.2s',
      overflow: 'hidden',
    }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '10px 14px',
          cursor: 'pointer',
          gap: 10,
        }}
      >
        <span style={{
          width: 26,
          height: 26,
          borderRadius: '50%',
          background: isError ? '#ffeaea' : isAgent ? '#f3edff' : '#eef5ff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 14,
          flexShrink: 0,
        }}>{style.icon}</span>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {agentName && <Tag color="blue" style={{ margin: 0, fontSize: 10 }}>{agentName}</Tag>}
          <span style={{ fontWeight: 500, fontSize: 13, color: '#303133' }}>{style.title}</span>
          {level && level !== 'INFO' && (
            <Tag color={LEVEL_COLOR[level] || 'default'} style={{ margin: 0, fontSize: 10 }}>{level}</Tag>
          )}
          <Tag color="default" style={{ margin: 0, fontSize: 10 }}>{type}</Tag>
          {action && (
            <Tag color={action === 'ABORT' ? 'red' : action === 'FINE_GRAINED_SCAN' ? 'magenta' : 'blue'}>
              {action}
            </Tag>
          )}
          {confidence != null && <Tag color="cyan">conf={Number(confidence).toFixed(2)}</Tag>}
          {llmCalled === true && <Tag color="purple">LLM</Tag>}
          {llmCalled === false && action && <Tag color="default">rule</Tag>}
          {nextC != null && <Tag color="geekblue">→ {Number(nextC).toFixed(1)}°C</Tag>}
          {summary && (
            <span style={{ fontSize: 12, color: '#606266', flexBasis: '100%', paddingLeft: 0, lineHeight: 1.6 }}>
              {highlightSummary(summary)}
            </span>
          )}
        </div>
        <span style={{ fontSize: 11, color: '#909399', flexShrink: 0 }}>{tsStr}</span>
        <span style={{
          fontSize: 12,
          color: '#909399',
          flexShrink: 0,
          transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s',
        }}>▾</span>
      </div>

      {expanded && (
        <div style={{ padding: '0 14px 14px' }}>
          {reasoning && (
            <Section label="💭 推理过程">
              <div style={{
                fontSize: 13,
                lineHeight: 1.6,
                color: '#606266',
                padding: 12,
                background: '#f5f7fa',
                borderRadius: 8,
                whiteSpace: 'pre-wrap',
              }}>{reasoning}</div>
            </Section>
          )}

          {warnings.length > 0 && (
            <Section label="⚠ Warnings">
              <Space wrap>
                {warnings.map((w, i) => <Tag key={i} color="orange">{w}</Tag>)}
              </Space>
            </Section>
          )}

          {(action || nextC != null || p.step_size_K != null || dataQuality || p.model || p.rule_triggered) && (
            <Section label="🎯 决策结果">
              <div style={{
                padding: 12,
                background: 'linear-gradient(135deg, rgba(103,194,58,0.10) 0%, rgba(103,194,58,0.04) 100%)',
                borderRadius: 8,
                border: '1px solid rgba(103,194,58,0.20)',
                fontSize: 12,
                color: '#606266',
              }}>
                <DescRow label="action" value={action} />
                <DescRow label="下一点目标" value={nextC != null ? `${Number(nextC).toFixed(2)} °C` : null} />
                <DescRow label="step size" value={p.step_size_K != null ? `${p.step_size_K} K` : null} />
                <DescRow label="confidence" value={confidence != null ? Number(confidence).toFixed(3) : null} />
                <DescRow label="data_quality" value={dataQuality} />
                <DescRow label="model" value={p.model} />
                <DescRow label="n_points" value={p.n_points} />
                <DescRow label="rule_triggered" value={p.rule_triggered} />
                <DescRow label="llm_called" value={llmCalled == null ? null : String(llmCalled)} />
              </div>
            </Section>
          )}

          <Section label="📦 完整 Payload" defaultCollapsed={isAgent}>
            <pre style={{
              margin: 0,
              padding: 10,
              background: '#1e1e1e',
              color: '#d4d4d4',
              borderRadius: 6,
              fontSize: 11,
              lineHeight: 1.5,
              maxHeight: 220,
              overflow: 'auto',
              fontFamily: '"Fira Code", "Consolas", monospace',
            }}>{JSON.stringify(p, null, 2)}</pre>
          </Section>
        </div>
      )}
    </div>
  )
}

function Section({ label, children, defaultCollapsed = false }) {
  const [open, setOpen] = useState(!defaultCollapsed)
  return (
    <div style={{ marginTop: 12 }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          fontSize: 11,
          fontWeight: 500,
          color: '#909399',
          marginBottom: 6,
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        {open ? '▾' : '▸'} {label}
      </div>
      {open && children}
    </div>
  )
}

function DescRow({ label, value }) {
  if (value == null || value === '') return null
  return (
    <div style={{ display: 'flex', gap: 8, padding: '2px 0' }}>
      <span style={{ color: '#909399', minWidth: 100 }}>{label}:</span>
      <span style={{ color: '#303133' }}>{String(value)}</span>
    </div>
  )
}

export default function AIThinkingPanel({ connectionStatus = 'disconnected' }) {
  const events = useAgentStore((s) => s.thoughtChain) || []
  const isThinking = useAgentStore((s) => s.isThinking)
  const runId = useAgentStore((s) => s.runId)
  const clear = useAgentStore((s) => s.clearThoughtChain)
  const [llmOnly, setLlmOnly] = useState(false)
  const [filter, setFilter] = useState('all')  // all / agent / safety
  const scrollRef = useRef(null)

  const lastDecision = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      const ev = events[i]
      if ((ev.event_type || ev.type) === 'AGENT_DECISION') return ev
    }
    return null
  }, [events])

  const filtered = useMemo(() => {
    return events.filter((ev) => {
      const type = ev.event_type || ev.type || ''
      if (llmOnly && !isLlmRoundtrip(ev)) return false
      if (filter === 'agent' && !type.startsWith('AGENT_')) return false
      if (filter === 'safety' && !type.startsWith('SAFETY_')) return false
      return true
    })
  }, [events, llmOnly, filter])

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [filtered.length])

  const stats = useMemo(() => {
    const total = events.length
    let agent = 0, safety = 0, errors = 0
    events.forEach((ev) => {
      const t = ev.event_type || ev.type || ''
      if (t.startsWith('AGENT_')) agent += 1
      if (t.startsWith('SAFETY_')) safety += 1
      if (t === 'ERROR' || t.endsWith('_FAILED')) errors += 1
    })
    return { total, agent, safety, errors }
  }, [events])

  const connTagColor = connectionStatus === 'connected' ? 'success'
    : connectionStatus === 'connecting' ? 'warning' : 'default'
  const connTagLabel = connectionStatus === 'connected' ? '已连接'
    : connectionStatus === 'connecting' ? '连接中' : '未连接'

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      minHeight: 0,
      background: '#fff',
      borderRadius: 12,
      overflow: 'hidden',
      boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
    }}>
      {/* 紫色渐变 header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '14px 20px',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        flexShrink: 0,
        gap: 12,
        flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            background: 'rgba(255,255,255,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: 18,
          }}>🧠</div>
          <div>
            <div style={{ color: '#fff', fontWeight: 600, fontSize: 15 }}>
              Main Agent 思考链控制台
            </div>
            <div style={{ color: 'rgba(255,255,255,0.85)', fontSize: 11 }}>
              {isThinking
                ? '● 正在分析实验数据…'
                : lastDecision
                  ? `决策完成 · 最后 action = ${lastDecision.payload?.action || 'CONTINUE'}`
                  : '等待 Agent 调用'}
            </div>
          </div>
          {runId && (
            <Tag color="purple" bordered={false} style={{ fontFamily: 'monospace' }}>
              run: {String(runId).slice(0, 12)}…
            </Tag>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Tooltip title="仅展示真正调用了 LLM 的事件（AGENT_DECISION llm_called=true）">
            <Space size={6}>
              <span style={{ color: 'rgba(255,255,255,0.9)', fontSize: 12 }}>仅 LLM 调用</span>
              <Switch size="small" checked={llmOnly} onChange={setLlmOnly} />
            </Space>
          </Tooltip>
          <Tag color={connTagColor} style={{ fontWeight: 600, fontSize: 13, padding: '2px 10px' }}>
            ● {connTagLabel}
          </Tag>
        </div>
      </div>

      {/* 工具栏 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '8px 16px',
        background: '#fafbfc',
        borderBottom: '1px solid #f0f0f0',
        flexShrink: 0,
        flexWrap: 'wrap',
      }}>
        <Space.Compact size="small">
          {[
            { key: 'all', label: '全部' },
            { key: 'agent', label: 'Agent' },
            { key: 'safety', label: '熔断' },
          ].map((opt) => (
            <Button key={opt.key} size="small"
              type={filter === opt.key ? 'primary' : 'default'}
              onClick={() => setFilter(opt.key)}>
              {opt.label}
            </Button>
          ))}
        </Space.Compact>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {filtered.length} / {stats.total}
        </Text>
        <Tag color="purple" bordered={false}>Agent {stats.agent}</Tag>
        {stats.safety > 0 && <Tag color="red" bordered={false}>熔断 {stats.safety}</Tag>}
        {stats.errors > 0 && <Tag color="volcano" bordered={false}>错误 {stats.errors}</Tag>}
        <div style={{ flex: 1 }} />
        <Button size="small" onClick={() => clear?.()}>清空</Button>
      </div>

      {/* 步骤卡片列表 */}
      <div ref={scrollRef} style={{
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
        padding: 14,
        background: '#f5f7fa',
      }}>
        {filtered.length === 0
          ? <Empty description={isThinking ? 'AI 正在分析实验数据…' : '等待 Agent 调用'} style={{ padding: 60 }} />
          : filtered.map((ev, i) => {
            const type = ev.event_type || ev.type
            const defaultExpand = type === 'AGENT_DECISION' || type === 'PHASE_TRANSITION_DETECTED'
              || (type || '').startsWith('SAFETY_') || type === 'EXPERIMENT_COMPLETED'
            return <StepCard key={`${ev._local_ts || ev.timestamp || i}-${i}`} ev={ev} defaultExpanded={defaultExpand} />
          })}
      </div>

      {/* 底部决策摘要 */}
      {lastDecision && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 16px',
          background: '#fff',
          borderTop: '1px solid #f0f0f0',
          flexShrink: 0,
          gap: 12,
          flexWrap: 'wrap',
        }}>
          <Space size={16} style={{ fontSize: 12, color: '#909399' }}>
            <span>最后决策：{new Date(lastDecision._local_ts || lastDecision.timestamp || Date.now()).toLocaleTimeString()}</span>
            {lastDecision.payload?.confidence != null && (
              <span>置信度：{(Number(lastDecision.payload.confidence) * 100).toFixed(0)}%</span>
            )}
            {lastDecision.payload?.next_temp_target_C != null && (
              <span>下一点：{Number(lastDecision.payload.next_temp_target_C).toFixed(1)}°C</span>
            )}
          </Space>
        </div>
      )}
    </div>
  )
}
