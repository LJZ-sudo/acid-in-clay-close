import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Tabs, Select, Space, Tag, Table, Input, Switch, Button, App as AntdApp,
} from 'antd'
import { useTranslation } from 'react-i18next'
import { samplesApi } from '../../api/samples'
import client from '../../api/client'
import SampleClosureCard from '../SampleClosureCard'
import { useDataStore } from '../../stores'
import { useThoughtChainRefetch } from '../../hooks/useThoughtChainRefetch'

/**
 * Report — 实验报告（3 Tab）
 *
 * Tab 1 样品报告：默认指向当前 run 的 sample_id（如有），否则提示选择
 * Tab 2 样品库  ：跨样品 antd Table（搜索 + 过滤）
 * Tab 3 运行历史：runs 列表 + CSV 导出
 */

function Report() {
  const { t } = useTranslation('v3')
  return (
    <div style={{ maxWidth: 1500, margin: '0 auto' }}>
      <Card title={t('report.title')} bordered={false} bodyStyle={{ padding: 0 }}>
        <Tabs
          defaultActiveKey="card"
          tabBarStyle={{ paddingLeft: 16, marginBottom: 0 }}
          items={[
            { key: 'card', label: t('report.tabCard'), children: <div style={{ padding: 16 }}><SampleReportTab t={t} /></div> },
            { key: 'list', label: t('report.tabLib'),  children: <div style={{ padding: 16 }}><SamplesLibraryTab t={t} /></div> },
            { key: 'runs', label: t('report.tabRuns'), children: <div style={{ padding: 16 }}><RunsHistoryTab t={t} /></div> },
          ]}
        />
      </Card>
    </div>
  )
}

// ---- Tab 1: 样品报告 ----
function SampleReportTab({ t }) {
  const currentSampleId = useDataStore((s) => s.experimentParams?.sample_id || null)
  const expR = useDataStore((s) => s.experimentParams?.R)
  const expN = useDataStore((s) => s.experimentParams?.N)
  const [sampleId, setSampleId] = useState(currentSampleId)
  const [list, setList] = useState([])

  const refreshList = useCallback(() => {
    samplesApi.list({ limit: 500 })
      .then((r) => setList(r?.data?.samples || []))
      .catch(() => setList([]))
  }, [])

  useEffect(() => {
    refreshList()
  }, [refreshList])

  useThoughtChainRefetch(sampleId || currentSampleId, {
    onRefreshSampleList: refreshList,
  })

  useEffect(() => {
    if (!sampleId && currentSampleId) setSampleId(currentSampleId)
  }, [currentSampleId, sampleId])

  // 下拉选项里是 Stage0 canonical id（如 ATA-2026-5-12-R0.35-N0.95），而实验里常用 CHI 名（R0.35-N0.95-1）——对齐到同一行
  useEffect(() => {
    if (!list.length || !sampleId) return
    if (list.some((s) => s.sample_id === sampleId)) return
    if (expR != null && expN != null) {
      const hit = list.find((s) => s.R != null && s.N != null
        && Math.abs(Number(s.R) - Number(expR)) < 0.04
        && Math.abs(Number(s.N) - Number(expN)) < 0.04)
      if (hit) setSampleId(hit.sample_id)
    }
  }, [list, sampleId, expR, expN])

  const options = useMemo(() => list.map((s) => {
    const tag = s.has_closure_report ? (s.closure_llm_used ? ' · LLM' : ' · facts') : ''
    return { value: s.sample_id, label: `${s.sample_id}${tag}` }
  }), [list])

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <span style={{ color: '#666', fontSize: 13 }}>{t('report.sampleSelect')}：</span>
        <Select
          showSearch
          value={sampleId}
          onChange={setSampleId}
          placeholder={list.length ? '选择已落盘样品' : '样品库为空（先跑一次实验）'}
          style={{ width: 320 }}
          options={options}
          optionFilterProp="label"
          disabled={!list.length}
        />
      </Space>
      {sampleId
        ? <SampleClosureCard sampleId={sampleId} hideBreadcrumb />
        : <div style={{ padding: 40, color: '#999', textAlign: 'center' }}>
            尚未选择样品。请先完成一次实验，或从样品库选择已有样品。
          </div>}
    </>
  )
}

// ---- Tab 2: 样品库 ----
function fmtSigma(v) { return v == null || Number.isNaN(v) ? '—' : Number(v).toExponential(2) }
function fmtNum(v, d = 3) { return v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toFixed(d) }

function SamplesLibraryTab({ t }) {
  const navigate = useNavigate()
  const { message } = AntdApp.useApp()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [closureOnly, setClosureOnly] = useState(false)

  const refreshRows = useCallback(() => {
    setLoading(true)
    samplesApi.list({ limit: 500, ...(closureOnly ? { has_closure: true } : {}) })
      .then((r) => setRows(r?.data?.samples || []))
      .catch((e) => message.error('Load samples failed: ' + e.message))
      .finally(() => setLoading(false))
  }, [closureOnly, message])

  useEffect(() => {
    refreshRows()
  }, [refreshRows])

  useThoughtChainRefetch(null, { onRefreshSampleList: refreshRows })

  const filtered = useMemo(() => rows.filter((r) => {
    if (!filter) return true
    const q = filter.trim().toLowerCase()
    return (r.sample_id || '').toLowerCase().includes(q)
        || (r.material_system || '').toLowerCase().includes(q)
  }), [rows, filter])

  const columns = [
    { title: t('report.colSampleId'), dataIndex: 'sample_id', sorter: (a, b) => (a.sample_id || '').localeCompare(b.sample_id || ''),
      render: (v) => <a onClick={() => navigate(`/sample/${encodeURIComponent(v)}`)}><code>{v}</code></a> },
    { title: t('report.colMaterial'), dataIndex: 'material_system', render: (v) => v || '—' },
    { title: 'R', dataIndex: 'R', sorter: (a, b) => (a.R ?? -Infinity) - (b.R ?? -Infinity), render: (v) => fmtNum(v, 3) },
    { title: 'N', dataIndex: 'N', sorter: (a, b) => (a.N ?? -Infinity) - (b.N ?? -Infinity), render: (v) => fmtNum(v, 3) },
    { title: t('report.colSigma'), dataIndex: 'sigma_RT_S_per_cm',
      sorter: (a, b) => (a.sigma_RT_S_per_cm ?? -Infinity) - (b.sigma_RT_S_per_cm ?? -Infinity),
      defaultSortOrder: 'descend', render: fmtSigma },
    { title: t('report.colSegments'), dataIndex: 'n_segments', sorter: (a, b) => (a.n_segments ?? -Infinity) - (b.n_segments ?? -Infinity), render: (v) => v ?? '—' },
    { title: t('report.colClosure'), key: 'closure',
      render: (_, r) => !r.has_closure_report ? <Tag>—</Tag>
        : r.closure_llm_used ? <Tag color="orange">LLM</Tag> : <Tag color="blue">facts</Tag> },
  ]

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Input.Search placeholder={t('report.libSearch')} value={filter}
          onChange={(e) => setFilter(e.target.value)} style={{ width: 260 }} allowClear />
        <Space size={4}>
          <span style={{ fontSize: 12, color: '#666' }}>{t('report.libClosureOnly')}</span>
          <Switch size="small" checked={closureOnly} onChange={setClosureOnly} />
        </Space>
      </Space>
      <Table rowKey="sample_id" loading={loading} dataSource={filtered} columns={columns} size="middle"
        pagination={{ pageSize: 20, showTotal: (n) => `${n} / ${rows.length}` }} />
    </>
  )
}

// ---- Tab 3: 运行历史 ----
const STATUS_COLOR = {
  completed: 'success', cancelled: 'default', archived: 'default',
  running: 'processing', paused: 'warning', error: 'error',
}
function fmtDate(iso) { try { return iso ? new Date(iso).toLocaleString() : '—' } catch { return iso } }

function RunsHistoryTab({ t }) {
  const navigate = useNavigate()
  const { message } = AntdApp.useApp()
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get('/runs', { params: { limit: 100 } })
      .then((r) => setRuns(r?.data?.runs || []))
      .catch((e) => message.error('Load runs failed: ' + e.message))
      .finally(() => setLoading(false))
  }, [message])

  const exportCSV = () => {
    if (runs.length === 0) return
    const header = 'run_id,status,profile,sample_id,created_at\n'
    const lines = runs.map((r) => [r.run_id, r.status || '', r.profile || '', r.sample_id || '', r.created_at || '']
      .map((v) => `"${String(v).replace(/"/g, '""')}"`).join(','))
    const blob = new Blob([header + lines.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `runs_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const columns = [
    { title: t('report.colRunId'), dataIndex: 'run_id', render: (v) => <code>{v}</code> },
    { title: t('report.colStatus'), dataIndex: 'status', render: (v) => <Tag color={STATUS_COLOR[v] || 'default'}>{v || '—'}</Tag> },
    { title: t('report.colProfile'), dataIndex: 'profile', render: (v) => v || '—' },
    { title: t('common.sample'), dataIndex: 'sample_id', render: (v) => v || '—' },
    { title: t('report.colCreated'), dataIndex: 'created_at', render: fmtDate },
    { title: t('report.colOps'), key: 'op',
      render: (_, r) => <Button size="small" type="link"
        onClick={() => navigate(`/dev/replay/${encodeURIComponent(r.run_id)}`)}>{t('report.runReplay')}</Button> },
  ]

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Button onClick={exportCSV} disabled={runs.length === 0}>{t('report.runsExport')}</Button>
        <span style={{ color: '#999', fontSize: 12 }}>{t('report.runsTotal', { n: runs.length })}</span>
      </Space>
      <Table rowKey="run_id" loading={loading} dataSource={runs} columns={columns} size="middle"
        pagination={{ pageSize: 20 }} />
    </>
  )
}

export default Report
