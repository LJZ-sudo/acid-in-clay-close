import { useCallback, useEffect, useMemo, useState } from 'react'
import { Card, Row, Col, Statistic, Table, Tag, Tooltip, Empty, Space, Typography, Select, Button } from 'antd'
import { SafetyCertificateOutlined, ReloadOutlined } from '@ant-design/icons'
import client from '../../api/client'
import { useAgentStore } from '../../stores'

const { Text } = Typography

const GOV_TYPES = new Set(['SHADOW_VERDICT', 'RBACT_DECISION', 'TXN_ADMISSION'])

/** 从某个 run 拉全量事件并回放治理事件（历史回放核心）。 */
async function fetchRunEvents(runId) {
  const res = await client.get(`/runs/${encodeURIComponent(runId)}/events`, { params: { limit: 5000 } })
  const events = res?.data?.events
  return Array.isArray(events) ? events : []
}

/**
 * GovernancePanel — ESAS-OS 2.0 / B 轨「运行时治理」可观测面板（Phase 2，纯加法）。
 *
 * 订阅后端实时回路逐点旁路产生的三类治理事件：
 *   - SHADOW_VERDICT  影子三重提交：live vs shadow 准入是否一致、盲重试数
 *   - RBACT_DECISION  Rb-ACT 双跑：REPORT/ABSTAIN、|Δlog10 Rb|、未解释翻转
 *   - TXN_ADMISSION   measurement_txn 逐点准入：entered_bo、U1–U6 裁决
 *
 * 数据来自 agentStore.governanceByStep / governanceSummary（由 handleSSEEvent 喂入）。
 * 该面板只读，不触发任何控制，永远与正常测量解耦。
 */
const ADM_COLOR = { ADMIT: 'green', REJECT: 'default', INSUFFICIENT: 'orange', PENDING: 'blue' }

function AdmissionTags({ admissions }) {
  const keys = Object.keys(admissions || {}).sort()
  if (!keys.length) return <Text type="secondary">—</Text>
  return (
    <Space size={2} wrap>
      {keys.map((k) => (
        <Tag key={k} color={ADM_COLOR[String(admissions[k]).toUpperCase()] || 'default'} style={{ margin: 0, fontSize: 11 }}>
          {k}
        </Tag>
      ))}
    </Space>
  )
}

export default function GovernancePanel() {
  const byStep = useAgentStore((s) => s.governanceByStep) || {}
  const sum = useAgentStore((s) => s.governanceSummary) || {}
  const governanceRunId = useAgentStore((s) => s.governanceRunId)
  const loadGovernanceHistory = useAgentStore((s) => s.loadGovernanceHistory)

  const [runOptions, setRunOptions] = useState([])
  const [selectedRun, setSelectedRun] = useState(null)
  const [loading, setLoading] = useState(false)
  const [replaySource, setReplaySource] = useState(null) // 'history' | 'live' | null

  // 回放指定 run 的治理历史（先 reset 再重放，幂等、不与实时重复计数）。
  const replayRun = useCallback(async (runId) => {
    if (!runId) return
    setLoading(true)
    try {
      const events = await fetchRunEvents(runId)
      loadGovernanceHistory(runId, events)
      setSelectedRun(runId)
      setReplaySource('history')
    } catch {
      // fail-safe：拉取失败保持现状，不抛错打断面板
    } finally {
      setLoading(false)
    }
  }, [loadGovernanceHistory])

  // 挂载时：拉最近 run 列表 + 当前/最近 run；只有逐点为空（无实时数据）时才自动回放，
  // 避免覆盖正在实时填充的运行。
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      let currentRunId = null
      try {
        const st = await client.get('/control/status')
        currentRunId = st?.data?.run_id || null
      } catch { /* ignore */ }

      let runs = []
      try {
        const rs = await client.get('/runs', { params: { limit: 30 } })
        runs = Array.isArray(rs?.data?.runs) ? rs.data.runs : []
      } catch { /* ignore */ }

      if (cancelled) return
      setRunOptions(runs.map((r) => ({
        value: r.run_id,
        label: `${r.run_id}${r.status ? ` · ${r.status}` : ''}`,
      })))

      const targetRun = currentRunId || (runs[0] && runs[0].run_id) || null
      const hasLive = Object.keys(useAgentStore.getState().governanceByStep || {}).length > 0
      if (hasLive) {
        // 已有实时数据：标记为实时，不自动覆盖。
        setSelectedRun(useAgentStore.getState().governanceRunId || targetRun)
        setReplaySource('live')
      } else if (targetRun) {
        await replayRun(targetRun)
      }
    })()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const rows = useMemo(() => {
    return Object.values(byStep)
      .sort((a, b) => (a.step_idx ?? 0) - (b.step_idx ?? 0))
      .map((r) => ({ key: r.step_idx, ...r }))
  }, [byStep])

  const agreementPct = sum.shadowAgreementRate != null
    ? `${(Number(sum.shadowAgreementRate) * 100).toFixed(1)}%`
    : '—'

  const columns = [
    {
      title: '步', dataIndex: 'step_idx', width: 48,
      render: (v) => <Text style={{ fontFamily: 'monospace' }}>{v}</Text>,
    },
    {
      title: 'T (°C)', dataIndex: 'temperature_C', width: 72,
      render: (v) => (v != null ? Number(v).toFixed(1) : '—'),
    },
    {
      title: <Tooltip title="影子三重提交：live 与 shadow 准入是否一致">Shadow</Tooltip>,
      dataIndex: 'shadow', width: 90,
      render: (sd) => {
        if (!sd) return <Text type="secondary">—</Text>
        return <Tag color={sd.agree ? 'green' : 'red'} style={{ margin: 0 }}>{sd.agree ? '一致' : '不一致'}</Tag>
      },
    },
    {
      title: <Tooltip title="Rb-ACT 双跑决策与 legacy 的 |Δlog10 Rb|">Rb-ACT</Tooltip>,
      dataIndex: 'rbact', width: 170,
      render: (rb) => {
        if (!rb) return <Text type="secondary">—</Text>
        const isAbstain = String(rb.decision || '').toUpperCase().includes('ABSTAIN')
        return (
          <Space size={4} wrap>
            <Tag color={isAbstain ? 'orange' : 'green'} style={{ margin: 0 }}>
              {isAbstain ? 'ABSTAIN' : 'REPORT'}
            </Tag>
            {rb.dlog != null && (
              <Text style={{ fontFamily: 'monospace', fontSize: 11 }}>Δ={Number(rb.dlog).toFixed(3)}</Text>
            )}
            {rb.flip && <Tag color="red" style={{ margin: 0 }}>翻转</Tag>}
          </Space>
        )
      },
    },
    {
      title: <Tooltip title="measurement_txn 是否进入 BO（准入）">准入</Tooltip>,
      dataIndex: 'txn', width: 70,
      render: (tx) => {
        if (!tx) return <Text type="secondary">—</Text>
        return <Tag color={tx.enteredBo ? 'blue' : 'default'} style={{ margin: 0 }}>{tx.enteredBo ? 'BO' : 'no'}</Tag>
      },
    },
    {
      title: <Tooltip title="逐点准入 U1–U6（ADMIT/REJECT/INSUFFICIENT）">U1–U6</Tooltip>,
      dataIndex: 'txn',
      render: (tx) => <AdmissionTags admissions={tx?.admissions} />,
    },
  ]

  return (
    <div style={{ padding: 16 }}>
      <Card type="inner" size="small"
        title={
          <Space>
            <SafetyCertificateOutlined />运行时治理（ESAS-OS 2.0 / B 轨）
            {replaySource === 'history' && <Tag color="geekblue" style={{ margin: 0 }}>历史回放</Tag>}
            {replaySource === 'live' && <Tag color="green" style={{ margin: 0 }}>实时</Tag>}
          </Space>
        }
        extra={
          <Space size={8}>
            <Select
              size="small"
              style={{ minWidth: 240 }}
              placeholder="选择 run 回放历史"
              value={selectedRun || undefined}
              options={runOptions}
              onChange={(v) => replayRun(v)}
              showSearch
              optionFilterProp="label"
              notFoundContent="无历史 run"
            />
            <Button
              size="small"
              icon={<ReloadOutlined />}
              loading={loading}
              onClick={() => replayRun(selectedRun || governanceRunId)}
              disabled={!selectedRun && !governanceRunId}
            >
              刷新
            </Button>
          </Space>
        }
        style={{ marginBottom: 12 }}>
        <Row gutter={12}>
          <Col span={6}>
            <Statistic title="Shadow 一致率" value={agreementPct}
              valueStyle={{ fontSize: 18, color: sum.shadowAgree === sum.nShadow ? '#3f8600' : '#cf1322' }} />
            <Text type="secondary" style={{ fontSize: 11 }}>盲重试 {sum.shadowBlindRetry ?? 0}（目标 0）</Text>
          </Col>
          <Col span={6}>
            <Statistic title="Rb-ACT REPORT" value={sum.rbactReport ?? 0}
              suffix={`/ ${sum.nRbact ?? 0}`} valueStyle={{ fontSize: 18 }} />
            <Text type="secondary" style={{ fontSize: 11 }}>ABSTAIN {sum.rbactAbstain ?? 0}</Text>
          </Col>
          <Col span={6}>
            <Statistic title="未解释翻转" value={sum.rbactFlips ?? 0}
              valueStyle={{ fontSize: 18, color: (sum.rbactFlips ?? 0) === 0 ? '#3f8600' : '#cf1322' }} />
            <Text type="secondary" style={{ fontSize: 11 }}>目标 0</Text>
          </Col>
          <Col span={6}>
            <Statistic title="准入(BO)" value={sum.txnEnteredBo ?? 0}
              suffix={`/ ${sum.nTxn ?? 0}`} valueStyle={{ fontSize: 18 }} />
            <Text type="secondary" style={{ fontSize: 11 }}>逐点 U1–U6</Text>
          </Col>
        </Row>
      </Card>

      <Card type="inner" size="small"
        title="逐点治理裁决"
        extra={selectedRun && <Text type="secondary" style={{ fontSize: 11, fontFamily: 'monospace' }}>{selectedRun}</Text>}>
        {rows.length > 0
          ? <Table size="small" columns={columns} dataSource={rows} pagination={false} scroll={{ y: 420 }} />
          : <Empty description="无治理记录（启动一次实时运行后逐点产生，或从右上角选择历史 run 回放）" style={{ padding: 30 }} />}
      </Card>
    </div>
  )
}
