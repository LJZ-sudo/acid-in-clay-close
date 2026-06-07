import { Card, Tag, Tooltip, Progress, Alert, Space } from 'antd'
import {
  CheckCircleFilled,
  ClockCircleFilled,
  WarningFilled,
  StopFilled,
} from '@ant-design/icons'

/**
 * TerminationPanel — 闭环终止判据 v3 仪表。
 *
 * 对应后端 GET /api/campaigns/{name}/termination 的返回结构：
 *   { verdict, performance:{...}, convergence:{rules:[...], ...}, budget:{...}, anomaly:{rules:[...]} }
 *
 * 设计原则：
 *   - 4 个象限并列展示（A 性能 / B 收敛 / C 预算 / D 异常）
 *   - 每个象限给出"当前值 / 阈值 / 是否触发"
 *   - 顶部根据 verdict 给一句明确的"还能不能停"
 */

const QUADRANTS = [
  { key: 'performance', icon: '🎯', label: 'A · 性能目标' },
  { key: 'convergence', icon: '📉', label: 'B · BO 收敛' },
  { key: 'budget', icon: '⏳', label: 'C · 预算兜底' },
  { key: 'anomaly', icon: '🚨', label: 'D · 异常熔断' },
]

function fmt(v, digits = 3) {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  const n = Number(v)
  if (Math.abs(n) < 1e-3 && n !== 0) return n.toExponential(2)
  return n.toFixed(digits)
}

function StatusTag({ triggered, status }) {
  if (triggered) return <Tag color="success" icon={<CheckCircleFilled />}>已触发</Tag>
  if (status === 'alert') return <Tag color="error" icon={<WarningFilled />}>异常</Tag>
  if (status === 'exhausted') return <Tag color="error" icon={<StopFilled />}>耗尽</Tag>
  return <Tag color="default" icon={<ClockCircleFilled />}>未达</Tag>
}

function PerformanceQuadrant({ data }) {
  if (!data) return <span className="text-gray-400">no data</span>
  const th = data.thresholds || {}
  const best = data.current_best || {}
  const rows = [
    { id: 'sigma', label: 'σ_RT (S/cm)', value: best.sigma_rt, limit: th.sigma_rt_min_S_cm, op: '≥' },
    { id: 'ea_h', label: 'Ea_high (eV)', value: best.ea_high, limit: th.ea_high_max_eV, op: '≤' },
    { id: 'ea_lex', label: 'ea_low_excess (eV)', value: best.ea_low_excess, limit: th.ea_low_excess_max_eV, op: '≤' },
    { id: 'score', label: 'combined_score', value: best.combined_score, limit: th.combined_score_min, op: '≥' },
  ]
  return (
    <div style={{ fontSize: 12 }}>
      <div style={{ marginBottom: 8, color: '#666' }}>
        当前最优 trial #{best.trial_id ?? '—'} vs 阈值：
      </div>
      {rows.map((r) => {
        const ok =
          r.value != null && r.limit != null
            ? (r.op === '≥' ? Number(r.value) >= Number(r.limit) : Number(r.value) <= Number(r.limit))
            : null
        const color = ok === true ? '#16a34a' : ok === false ? '#dc2626' : '#9ca3af'
        return (
          <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <span>{r.label}</span>
            <span style={{ fontFamily: 'monospace', color }}>
              {fmt(r.value)} {r.op} {fmt(r.limit)} {ok === true ? '✓' : ok === false ? '✗' : ''}
            </span>
          </div>
        )
      })}
      <div style={{ marginTop: 8, color: '#666' }}>
        合格 trial 数：<b>{data.n_qualifying_distinct ?? 0}</b> / 需要 {th.consecutive_distinct_recipes_required ?? 2}
        <span style={{ color: '#999' }}>
          {' '}(去重间距 ≥ {th.distinct_recipe_min_distance ?? 0.05}，归一化空间)
        </span>
      </div>
    </div>
  )
}

function RulesQuadrant({ data, requireMet }) {
  if (!data?.rules?.length) return <span className="text-gray-400">no data</span>
  return (
    <div style={{ fontSize: 12 }}>
      {data.rules.map((r) => (
        <Tooltip
          key={r.id}
          title={
            <div style={{ fontSize: 11 }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{r.label}</div>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                {JSON.stringify(r.value, null, 2)}
              </pre>
            </div>
          }
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <span style={{ color: r.ok ? '#16a34a' : '#666' }}>
              {r.ok ? '✓' : '○'} {r.label}
            </span>
          </div>
        </Tooltip>
      ))}
      {requireMet != null && (
        <div style={{ marginTop: 8, color: '#666' }}>
          已满足 <b>{data.n_ok ?? 0}</b> / 需要 {data.required_to_trigger ?? requireMet}
        </div>
      )}
    </div>
  )
}

function BudgetQuadrant({ data }) {
  if (!data) return <span className="text-gray-400">no data</span>
  const used = data.n_total_trials ?? 0
  const total = data.max_total_trials ?? 20
  const pct = Math.min(100, Math.round((used / total) * 100))
  return (
    <div style={{ fontSize: 12 }}>
      <div style={{ marginBottom: 4 }}>
        已用样品 <b>{used}</b> / 上限 {total}（剩余 {data.remaining ?? Math.max(0, total - used)}）
      </div>
      <Progress percent={pct} size="small" status={pct >= 100 ? 'exception' : 'active'} />
    </div>
  )
}

function VerdictBanner({ payload }) {
  const verdict = payload?.verdict
  const triggered = payload?.triggered_by || []
  if (verdict === 'loop_can_end') {
    return (
      <Alert
        showIcon
        type="success"
        message="闭环可结束"
        description={`已触发判据：${triggered.join('、')}`}
        style={{ marginBottom: 12 }}
      />
    )
  }
  if (verdict === 'loop_must_end_budget') {
    return (
      <Alert
        showIcon
        type="error"
        message="预算已耗尽，必须结束"
        description="样品数达到上限，请审阅 best 样品并形成报告。"
        style={{ marginBottom: 12 }}
      />
    )
  }
  return (
    <Alert
      showIcon
      type="info"
      message="闭环进行中（continue）"
      description="A/B/C/D 四象限均未触发；按推荐配方继续下一轮即可。"
      style={{ marginBottom: 12 }}
    />
  )
}

function ProgressSummary({ progress, perfTh }) {
  if (!progress) return null
  const gaps = progress.performance_gap_to_threshold || {}
  const recent = progress.recent_trials || []
  const traj = progress.score_trajectory || []
  // 简单 sparkline：用一行字符表示 score 走向（避免引入新依赖）
  const last8 = traj.slice(-8).filter((v) => v != null)
  const minS = Math.min(...last8)
  const maxS = Math.max(...last8)
  const sparkChars = '▁▂▃▄▅▆▇█'
  const spark = last8
    .map((v) => {
      if (maxS === minS) return sparkChars[3]
      const idx = Math.max(0, Math.min(sparkChars.length - 1,
        Math.round(((v - minS) / (maxS - minS)) * (sparkChars.length - 1))))
      return sparkChars[idx]
    })
    .join('')

  return (
    <div
      style={{
        background: '#f8fafc',
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        padding: '8px 12px',
        marginBottom: 12,
        fontSize: 12,
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 12,
      }}
    >
      <div>
        <div style={{ color: '#666' }}>best 轨迹（最近 {last8.length}）</div>
        <div style={{ fontFamily: 'monospace', fontSize: 16, letterSpacing: 1 }}>{spark || '—'}</div>
        <div style={{ color: '#666' }}>
          best score = <b>{progress.best_score?.toFixed(3) ?? '—'}</b>（trial #{progress.best_trial_id ?? '—'}）
          ；自 best 起又过 <b>{progress.trials_since_best_updated ?? '—'}</b> 个样品未刷新
        </div>
      </div>
      <div>
        <div style={{ color: '#666', marginBottom: 4 }}>距 A 类阈值差距（最优 trial）</div>
        {Object.keys(gaps).length === 0 ? (
          <span style={{ color: '#999' }}>—</span>
        ) : (
          <div style={{ fontFamily: 'monospace' }}>
            {gaps.sigma_rt != null && (
              <div>σ_RT 还缺 {gaps.sigma_rt > 0 ? gaps.sigma_rt.toExponential(2) : '已达 ✓'}</div>
            )}
            {gaps.ea_high != null && (
              <div>Ea_high {gaps.ea_high > 0 ? `还超 ${gaps.ea_high.toFixed(3)} eV` : '已达 ✓'}</div>
            )}
            {gaps.ea_low_excess != null && (
              <div>ea_low_excess {gaps.ea_low_excess > 0 ? `还超 ${gaps.ea_low_excess.toFixed(3)} eV` : '已达 ✓'}</div>
            )}
            {gaps.combined_score != null && (
              <div>score {gaps.combined_score > 0 ? `还缺 ${gaps.combined_score.toFixed(2)}` : '已达 ✓'}</div>
            )}
          </div>
        )}
      </div>
      <div>
        <div style={{ color: '#666', marginBottom: 4 }}>最近 {recent.length} 个 trial</div>
        {recent.map((t) => (
          <div key={t.trial_id} style={{ fontFamily: 'monospace', fontSize: 11 }}>
            #{t.trial_id} R={t.R?.toFixed(2)} N={t.N?.toFixed(2)} → score=<b>{t.combined_score?.toFixed(2)}</b>
          </div>
        ))}
      </div>
    </div>
  )
}

function TerminationPanel({ payload }) {
  if (!payload) {
    return (
      <Card title="闭环终止判据 v3" bordered={false} size="small">
        <span style={{ color: '#999' }}>loading…</span>
      </Card>
    )
  }
  return (
    <Card
      title={
        <Space>
          <span>闭环终止判据 v3</span>
          <Tag>{payload.n_history_trials ?? 0} trials</Tag>
          <Tag>{payload.n_closed_loop_rounds ?? 0} rounds</Tag>
        </Space>
      }
      bordered={false}
      size="small"
      extra={
        <Tooltip title={payload.rationale}>
          <span style={{ fontSize: 11, color: '#666' }}>📖 阈值依据 (hover)</span>
        </Tooltip>
      }
    >
      <VerdictBanner payload={payload} />
      <ProgressSummary progress={payload.progress} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
        {QUADRANTS.map(({ key, icon, label }) => {
          const data = payload[key] || {}
          return (
            <div
              key={key}
              style={{
                border: '1px solid #e5e7eb',
                borderRadius: 8,
                padding: 12,
                background: data.triggered ? '#f0fdf4' : data.status === 'alert' ? '#fef2f2' : '#ffffff',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontWeight: 600 }}>
                  {icon} {label}
                </span>
                <StatusTag triggered={data.triggered} status={data.status} />
              </div>
              {key === 'performance' && <PerformanceQuadrant data={data} />}
              {key === 'convergence' && <RulesQuadrant data={data} requireMet={data.required_to_trigger} />}
              {key === 'budget' && <BudgetQuadrant data={data} />}
              {key === 'anomaly' && <RulesQuadrant data={data} requireMet={1} />}
            </div>
          )
        })}
      </div>
    </Card>
  )
}

export default TerminationPanel
