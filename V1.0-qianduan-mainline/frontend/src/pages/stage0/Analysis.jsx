import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Card, Empty, Spin, Select, Space, Statistic, Row, Col,
  Tabs, Tag, Table, Alert, Radio, Descriptions,
} from 'antd'
import ReactECharts from 'echarts-for-react'
import { useTranslation } from 'react-i18next'
import { dataApi } from '../../api/data'
import { samplesApi } from '../../api/samples'
import { useDataStore } from '../../stores'
import { useThoughtChainRefetch, parseThoughtChainEvent } from '../../hooks/useThoughtChainRefetch'
import { wsService } from '../../services/websocket'
import { WS_EVENTS } from '../../utils/constants'

/**
 * Analysis — 实时数据分析（已移除离线 S8 demo）。
 *
 * EIS：实时模式默认跟随**最新完成**的测点，无需每次手选。
 *
 * Arrhenius：实时页测量中仅 ln(σ) 散点（与后端 points 一致）；**不在测量过程中**
 * 展示可靠的分段拟合。本炉次 ``_run_global_arrhenius`` 成功后 ``arrhenius_fit``
 * 写入 GET /data/arrhenius/realtime，此时叠加分段线与表格；事件流结束时会主动拉取一次。
 */
const SEG_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

function Analysis() {
  const { t } = useTranslation('v3')
  const currentSampleId = useDataStore((s) => s.experimentParams?.sample_id || null)

  // 输入源：'live' 实时当前 run；'sample' 查指定样品的 closure report
  const [source, setSource] = useState('live')
  const [sampleId, setSampleId] = useState(null)
  const [sampleList, setSampleList] = useState([])
  const [closure, setClosure] = useState(null)
  const [loading, setLoading] = useState(false)

  const refreshSampleList = useCallback(() => {
    samplesApi.list({ limit: 500 })
      .then((r) => setSampleList(r?.data?.samples || []))
      .catch(() => setSampleList([]))
  }, [])

  const fetchClosure = useCallback(() => {
    if (source !== 'sample' || !sampleId) {
      setClosure(null)
      setLoading(false)
      return
    }
    setLoading(true)
    samplesApi.getClosureReport(sampleId)
      .then((r) => setClosure(r?.data || null))
      .catch(() => setClosure(null))
      .finally(() => setLoading(false))
  }, [source, sampleId])

  useEffect(() => {
    refreshSampleList()
  }, [refreshSampleList])

  useEffect(() => {
    if (source === 'sample' && !sampleId && currentSampleId) {
      setSampleId(currentSampleId)
    }
  }, [source, sampleId, currentSampleId])

  useEffect(() => {
    fetchClosure()
  }, [fetchClosure])

  useThoughtChainRefetch(source === 'sample' ? sampleId : null, {
    onRefreshThisSample: fetchClosure,
    onRefreshSampleList: refreshSampleList,
  })

  return (
    <div style={{ maxWidth: 1500, margin: '0 auto' }}>
      <Card
        title={t('analysis.title')}
        extra={
          <Space size={12}>
            <Radio.Group
              size="small"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              optionType="button"
              buttonStyle="solid"
              options={[
                { label: '实时 (当前 run)', value: 'live' },
                { label: '已落盘样品', value: 'sample' },
              ]}
            />
            {source === 'sample' && (
              <Select
                showSearch
                value={sampleId}
                onChange={setSampleId}
                placeholder={sampleList.length ? '选择已落盘样品' : '样品库为空'}
                style={{ width: 260 }}
                options={sampleList.map((s) => ({
                  value: s.sample_id,
                  label: `${s.sample_id}${s.has_closure_report ? ' · closure' : ''}`,
                }))}
                disabled={!sampleList.length}
              />
            )}
            {source === 'live' && currentSampleId && (
              <Tag color="processing">当前: <code>{currentSampleId}</code></Tag>
            )}
          </Space>
        }
        bordered={false}
        bodyStyle={{ padding: 0 }}
      >
        <Tabs
          defaultActiveKey="eis"
          tabBarStyle={{ paddingLeft: 16, marginBottom: 0 }}
          items={[
            {
              key: 'eis',
              label: t('analysis.tabEis'),
              children: (
                <div style={{ padding: 16 }}>
                  <EisView source={source} sampleId={sampleId} closure={closure} loading={loading} t={t} />
                </div>
              ),
            },
            {
              key: 'arr',
              label: t('analysis.tabArrhenius'),
              children: (
                <div style={{ padding: 16 }}>
                  <ArrheniusView source={source} sampleId={sampleId} closure={closure} loading={loading} t={t} />
                </div>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}

// ============== EIS 单点 ==============
function EisView({ source, sampleId, closure, loading, t }) {
  const measurements = useDataStore((s) => s.measurements)
  const [eisIdx, setEisIdx] = useState(null)
  const [eis, setEis] = useState(null)
  const [eisLoading, setEisLoading] = useState(false)
  const prevMeasLenRef = useRef(0)
  // sample 模式下的真实 Nyquist 频谱（按温度）
  const [sampleSpectra, setSampleSpectra] = useState([])
  const [sampleSpectraErr, setSampleSpectraErr] = useState(null)
  const [sampleSpectraLoading, setSampleSpectraLoading] = useState(false)
  const [sampleTempIdx, setSampleTempIdx] = useState(0)
  useEffect(() => {
    if (source !== 'sample' || !sampleId) {
      setSampleSpectra([]); setSampleSpectraErr(null); setSampleTempIdx(0)
      return
    }
    setSampleSpectraLoading(true)
    setSampleSpectraErr(null)
    samplesApi.getEisSpectra(sampleId)
      .then((r) => {
        const list = r?.data?.spectra || []
        setSampleSpectra(list)
        // 默认显示最接近室温的频谱
        if (list.length) {
          let best = 0, bestD = Infinity
          list.forEach((s, i) => {
            const d = Math.abs((s.T_C ?? 1e9) - 25)
            if (d < bestD) { bestD = d; best = i }
          })
          setSampleTempIdx(best)
        }
      })
      .catch((e) => {
        setSampleSpectra([])
        setSampleSpectraErr(e?.response?.data?.detail || e?.message || '加载失败')
      })
      .finally(() => setSampleSpectraLoading(false))
  }, [source, sampleId])

  // 实时：新测点入库后自动切到最新一点，避免每点都要手选
  useEffect(() => {
    if (source !== 'live') return
    const n = measurements?.length ?? 0
    if (n === 0) {
      setEisIdx(null)
      prevMeasLenRef.current = 0
      return
    }
    if (n < prevMeasLenRef.current) {
      setEisIdx(n - 1)
      prevMeasLenRef.current = n
      return
    }
    if (n > prevMeasLenRef.current) {
      setEisIdx(n - 1)
    } else if (eisIdx == null || eisIdx >= n) {
      setEisIdx(n - 1)
    }
    prevMeasLenRef.current = n
  }, [source, measurements, eisIdx])
  const currentSampleId = useDataStore((s) => s.experimentParams?.sample_id || null)
  useEffect(() => {
    if (source !== 'live' || eisIdx == null) {
      setEis(null)
      return
    }
    setEisLoading(true)
    const meas = measurements?.[eisIdx]
    dataApi.getEISByIndex(eisIdx)
      .then((r) => {
        const top = r?.data
        const e = top?.eis
        const m = top?.data || {}
        if (e && Array.isArray(e.points || e.data) && (e.points || e.data).length) {
          setEis({
            ...e,
            r_squared: e.r_squared ?? m.r_squared ?? m.fit_quality,
            sigma_S_cm: e.sigma_S_cm ?? e.conductivity_S_cm ?? m.conductivity_S_cm,
            qc_grade: e.qc_grade ?? e.qc ?? m.qc_grade,
          })
          return null
        }
        // Fallback: 实时事件流不带原始频谱时，尝试用 sample bus 里的 CHI 文件
        if (currentSampleId && meas?.temperature != null) {
          return samplesApi.getEisSpectra(currentSampleId, meas.temperature)
            .then((rr) => {
              const sp = rr?.data?.spectra?.[0]
              if (!sp) { setEis(null); return }
              setEis({
                points: sp.points,
                rb_ohm: sp.rb_ohm ?? meas?.rb_ohm,
                sigma_S_cm: sp.sigma_S_cm ?? meas?.conductivity,
                r_squared: sp.rb_confidence ?? meas?.fit_quality,
                qc_grade: sp.status ?? meas?.qc_grade,
              })
            })
            .catch(() => setEis(null))
        }
        setEis(null)
        return null
      })
      .catch(() => setEis(null))
      .finally(() => setEisLoading(false))
  }, [source, eisIdx, currentSampleId, measurements])

  if (source === 'sample' && loading) {
    return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  }

  // -------- "已落盘样品" 模式：读 closure_report 的关键统计 + 真实 Stage0 bundle EIS 点 --------
  if (source === 'sample') {
    if (!sampleId) {
      return <Empty description="请在右上角选择已落盘样品" style={{ padding: 60 }} />
    }
    if (!closure) {
      return <Empty description={`样品 ${sampleId} 暂无 closure report`} style={{ padding: 60 }} />
    }
    const id = closure.identity || {}
    const pc = closure.performance_card || {}
    const q = closure.quality_card || {}

    return (
      <>
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col xs={12} sm={6}>
            <Statistic title={t('analysis.eisProgress')}
              value={`${q?.n_eis_ok ?? '—'} / ${q?.n_eis_points ?? '—'}`}
              valueStyle={{ fontSize: 22, color: '#409EFF' }} />
          </Col>
          <Col xs={12} sm={6}>
            <Statistic title="室温 σ"
              value={pc?.sigma_RT_S_per_cm != null ? Number(pc.sigma_RT_S_per_cm).toExponential(2) : '—'}
              suffix="S/cm" valueStyle={{ fontSize: 20, color: '#16a34a' }} />
          </Col>
          <Col xs={12} sm={6}>
            <Statistic title="Arrhenius 段数"
              value={pc?.n_segments ?? '—'} valueStyle={{ fontSize: 22 }} />
          </Col>
          <Col xs={12} sm={6}>
            <Statistic title="测量起止 (°C)"
              value={pc?.T_min_measured_C != null && pc?.T_max_measured_C != null
                ? `${pc.T_min_measured_C.toFixed(0)} ~ ${pc.T_max_measured_C.toFixed(0)}`
                : '—'}
              valueStyle={{ fontSize: 16 }} />
          </Col>
        </Row>

        <Card type="inner" size="small"
          title={<Space><span style={{ color: '#16a34a' }}>✓</span>样品识别 / 配方</Space>}
          style={{ marginBottom: 12 }}>
          <Descriptions size="small" column={{ xs: 1, sm: 2, md: 3 }} bordered
            labelStyle={{ color: '#666', fontSize: 12, whiteSpace: 'nowrap' }}
            contentStyle={{ fontSize: 13, fontFamily: 'monospace', wordBreak: 'break-all' }}>
            <Descriptions.Item label="sample_id">{id.sample_id || sampleId}</Descriptions.Item>
            <Descriptions.Item label="material">{id.material_system || '—'}</Descriptions.Item>
            <Descriptions.Item label="acid / clay">{id.acid_type} / {id.clay_type}</Descriptions.Item>
            <Descriptions.Item label="R">{id.R != null ? Number(id.R).toFixed(3) : '—'}</Descriptions.Item>
            <Descriptions.Item label="N">{id.N != null ? Number(id.N).toFixed(3) : '—'}</Descriptions.Item>
            <Descriptions.Item label="厚度 / 面积">
              {id.thickness_cm != null ? `${id.thickness_cm} cm` : '—'} / {id.area_cm2 != null ? `${Number(id.area_cm2).toFixed(3)} cm²` : '—'}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        <Card type="inner" size="small" title="质量卡" style={{ marginBottom: 12 }}>
          <Row gutter={16}>
            <Col span={6}><Statistic title="KK 通过率"
              value={q?.KK_pass_rate != null ? (q.KK_pass_rate * 100).toFixed(1) : '—'}
              suffix="%" valueStyle={{ fontSize: 18 }} /></Col>
            <Col span={6}><Statistic title="Rb 置信度 p50"
              value={q?.rb_confidence_p50 ?? '—'} valueStyle={{ fontSize: 18 }} /></Col>
            <Col span={6}><Statistic title="QC A 占比"
              value={q?.qc_distribution?.A ?? '—'} valueStyle={{ fontSize: 18 }} /></Col>
            <Col span={6}><Statistic title="QC C/D 占比"
              value={(q?.qc_distribution?.C ?? 0) + (q?.qc_distribution?.D ?? 0)}
              valueStyle={{ fontSize: 18, color: '#F56C6C' }} /></Col>
          </Row>
        </Card>

        <Card type="inner" size="small"
          title={<Space>📊 Nyquist 频谱（每个温度一条）{sampleSpectra.length ? <Tag color="blue">共 {sampleSpectra.length} 个 T 点</Tag> : null}</Space>}
          extra={sampleSpectra.length ? (
            <Select size="small" style={{ width: 220 }}
              value={sampleTempIdx} onChange={setSampleTempIdx}
              options={sampleSpectra.map((s, i) => ({
                value: i,
                label: `T = ${s.T_C?.toFixed?.(1) ?? s.T_C} °C  ·  Rb=${s.rb_ohm != null ? Number(s.rb_ohm).toPrecision(4) : '—'} Ω`,
              }))} />
          ) : null}
        >
          {sampleSpectraLoading ? (
            <div style={{ textAlign: 'center', padding: 40 }}><Spin tip="解析 CHI 频谱…" /></div>
          ) : sampleSpectraErr ? (
            <Alert type="warning" showIcon
              message="无法加载原始 EIS 频谱"
              description={String(sampleSpectraErr)} />
          ) : sampleSpectra.length === 0 ? (
            <Empty description="该样品没有可解析的 CHI .txt 频谱" />
          ) : (
            renderRealNyquist(
              {
                points: sampleSpectra[sampleTempIdx]?.points || [],
                rb_ohm: sampleSpectra[sampleTempIdx]?.rb_ohm,
                sigma_S_cm: sampleSpectra[sampleTempIdx]?.sigma_S_cm,
                r_squared: sampleSpectra[sampleTempIdx]?.rb_confidence,
                qc_grade: sampleSpectra[sampleTempIdx]?.status,
              },
              t,
            )
          )}
        </Card>
      </>
    )
  }

  // -------- 实时模式 --------
  const opts = (measurements || []).map((m, i) => ({
    value: i,
    label: `#${i + 1}  T=${(m.temperature ?? 0).toFixed(1)}°C  σ=${Number(m.conductivity ?? 0).toExponential(2)}`,
  }))
  const m = measurements?.[eisIdx] || null
  const hasAny = (measurements?.length || 0) > 0

  return (
    <>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Statistic title={t('analysis.eisProgress')}
            value={`${(eisIdx ?? -1) + 1} / ${measurements?.length || 0}`}
            valueStyle={{ fontSize: 22, color: '#409EFF' }} />
        </Col>
        <Col xs={12} sm={6}>
          <Statistic title={t('analysis.eisTemp')}
            value={m?.temperature != null ? `${m.temperature.toFixed(1)} °C` : '—'}
            valueStyle={{ fontSize: 22, color: '#409EFF' }} />
        </Col>
        <Col xs={12} sm={6}>
          <Statistic title="σ (S/cm)"
            value={m?.conductivity != null ? Number(m.conductivity).toExponential(3) : '—'}
            valueStyle={{ fontSize: 18, color: '#16a34a' }} />
        </Col>
        <Col xs={12} sm={6}>
          <Statistic title={t('analysis.eisStatus')}
            value={m?.qc_grade || (m ? 'OK' : '—')}
            valueStyle={{ fontSize: 18, color: m ? '#67C23A' : '#999' }} />
        </Col>
      </Row>

      {!hasAny ? (
        <Empty description="等待第一个测量点完成…" style={{ padding: 60 }} />
      ) : (
        <>
          <Space style={{ marginBottom: 12 }}>
            <span style={{ color: '#666', fontSize: 13 }}>{t('analysis.selectMeasurement')}：</span>
            <Select placeholder="—" style={{ width: 360 }} value={eisIdx} onChange={setEisIdx}
              options={opts} />
          </Space>

          {eisIdx == null ? (
            <div style={{ textAlign: 'center', padding: 40 }}><Spin tip="加载最新测点…" /></div>
          ) : eisLoading ? (
            <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
          ) : eis ? (
            renderRealNyquist(eis, t)
          ) : (
            <Alert
              type="warning" showIcon
              message="EIS 原始频率/Z 数据不可用"
              description="该测量点已上报到事件流，但 /api/data/eis 还未提供原始数据。等 Stage0 后处理跑完后可在“已落盘样品”视图查看完整曲线。"
            />
          )}
        </>
      )}
    </>
  )
}

function renderRealNyquist(eis, t) {
  const z = eis?.points || eis?.data || []
  if (!Array.isArray(z) || z.length === 0) return <Empty description={t('analysis.nyquistEmpty')} />
  const series = z.map((p) => [p.zReal ?? p.z_real ?? p.Zr ?? p[0], -(p.zImag ?? p.z_imag ?? p.Zi ?? p[1])])
  const opt = {
    tooltip: { trigger: 'item', formatter: (p) => `Z'=${p.value[0].toFixed(2)}<br/>-Z''=${p.value[1].toFixed(2)}` },
    grid: { left: 60, right: 30, top: 30, bottom: 50 },
    xAxis: { type: 'value', name: "Z' (Ω)", nameLocation: 'center', nameGap: 28 },
    yAxis: { type: 'value', name: "-Z'' (Ω)", nameLocation: 'center', nameGap: 40 },
    series: [{ type: 'scatter', data: series, symbolSize: 6, color: '#3b82f6' }],
  }
  return (
    <Row gutter={16}>
      <Col xs={24} lg={16}>
        <Card type="inner" size="small" title={`📊 ${t('analysis.nyquistTitle')}`}>
          <ReactECharts option={opt} style={{ height: 360 }} notMerge />
        </Card>
      </Col>
      <Col xs={24} lg={8}>
        <Card type="inner" size="small"
          title={<Space><span style={{ color: '#16a34a' }}>✓</span>{t('analysis.finalResult')}</Space>}
          style={{ background: 'linear-gradient(135deg,#f0fdf4,#ecfdf5)' }}>
          <div style={{ textAlign: 'center', padding: '4px 0 12px' }}>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>{t('analysis.rb')}</div>
            <div style={{ fontSize: 36, fontWeight: 'bold', color: '#16a34a', lineHeight: 1 }}>
              {typeof eis?.rb_ohm === 'number' && Number.isFinite(eis.rb_ohm)
                ? eis.rb_ohm.toPrecision(6)
                : (eis?.rb_ohm ?? '--')} <span style={{ fontSize: 18 }}>Ω</span>
            </div>
          </div>
          <Descriptions size="small" column={1} colon labelStyle={{ color: '#666', fontSize: 12 }}>
            <Descriptions.Item label={t('analysis.rSquared')}>
              {eis?.r_squared != null && Number.isFinite(Number(eis.r_squared))
                ? Number(eis.r_squared).toFixed(4)
                : '—'}
            </Descriptions.Item>
            <Descriptions.Item label={t('analysis.conductivity')}>
              {(() => {
                const sig = eis?.sigma_S_cm ?? eis?.conductivity_S_cm
                return sig != null && Number.isFinite(Number(sig))
                  ? `${Number(sig).toExponential(3)} S/cm`
                  : '—'
              })()}
            </Descriptions.Item>
            <Descriptions.Item label="QC">{eis?.qc_grade ?? eis?.qc ?? '—'}</Descriptions.Item>
          </Descriptions>
        </Card>
      </Col>
    </Row>
  )
}

function normalizeAnalyzerSegment(seg, i) {
  const tr = (seg.temp_range_K || []).map(Number).filter((x) => Number.isFinite(x))
  const tMinK = tr.length ? Math.min(...tr) : null
  const tMaxK = tr.length ? Math.max(...tr) : null
  return {
    idx: seg.segment_id ?? i,
    T_low_C: tMinK != null ? tMinK - 273.15 : null,
    T_high_C: tMaxK != null ? tMaxK - 273.15 : null,
    Ea_eV: seg.Ea_eV,
    Ea_kJ_per_mol: seg.Ea_kJ_per_mol,
    n_points: seg.n_points,
    R2: seg.r_squared,
    r_squared: seg.r_squared,
  }
}

/** Prefer backend /arrhenius/realtime points (与硬件内存一致，实验结束后仍可取). */
function scatterLnSigmaFromApi(liveRt) {
  const rows = liveRt?.points
  if (!Array.isArray(rows) || !rows.length) return null
  const pts = []
  for (const p of rows) {
    const tc = p.temperature_C ?? p.T_C
    const x = p['1000_T'] != null ? Number(p['1000_T']) : (tc != null ? 1000 / (Number(tc) + 273.15) : NaN)
    const y = p.ln_sigma != null ? Number(p.ln_sigma) : (p.sigma_S_cm != null ? Math.log(Number(p.sigma_S_cm)) : NaN)
    if (!Number.isFinite(x) || !Number.isFinite(y) || tc == null) continue
    pts.push([x, y, Number(tc)])
  }
  if (!pts.length) return null
  const tcs = pts.map((q) => q[2])
  return {
    n_points: pts.length,
    stats: {
      n_segments: '—',
      T_range: `${Math.min(...tcs).toFixed(0)} ~ ${Math.max(...tcs).toFixed(0)}`,
    },
    option: {
      tooltip: { trigger: 'item', formatter: (p) => `T=${p.value[2].toFixed(1)}°C<br/>1000/T=${p.value[0].toFixed(3)}<br/>ln(σ)=${p.value[1].toFixed(3)}` },
      grid: { left: 60, right: 30, top: 30, bottom: 50 },
      xAxis: { type: 'value', name: '1000/T (1/K)', nameLocation: 'center', nameGap: 28 },
      yAxis: { type: 'value', name: 'ln(σ)', nameLocation: 'center', nameGap: 40 },
      series: [{ type: 'scatter', data: pts, symbolSize: 8, color: '#8b5cf6' }],
    },
  }
}

/** ln(σ) vs 1000/T，来自前端事件流（API 无点时回退） */
function buildLiveLnSigmaScatter(measurements) {
  const pts = (measurements || [])
    .filter((m) => {
      const T_C = m.T_C ?? m.temperature_C ?? m.temperature
      const sigma = m.sigma_S_cm ?? m.conductivity_S_cm ?? m.conductivity
      return T_C != null && sigma != null && sigma > 0
    })
    .map((m) => {
      const T_C = m.T_C ?? m.temperature_C ?? m.temperature
      const sigma = m.sigma_S_cm ?? m.conductivity_S_cm ?? m.conductivity
      const T_K = T_C + 273.15
      return [1000 / T_K, Math.log(sigma), T_C]
    })
  if (pts.length === 0) return null
  const tCs = (measurements || []).map((m) => m.T_C ?? m.temperature_C ?? m.temperature).filter((v) => v != null)
  return {
    n_points: pts.length,
    stats: {
      n_segments: '—',
      T_range: tCs.length > 0 ? `${Math.min(...tCs).toFixed(0)} ~ ${Math.max(...tCs).toFixed(0)}` : '—',
    },
    option: {
      tooltip: { trigger: 'item', formatter: (p) => `T=${p.value[2].toFixed(1)}°C<br/>1000/T=${p.value[0].toFixed(3)}<br/>ln(σ)=${p.value[1].toFixed(3)}` },
      grid: { left: 60, right: 30, top: 30, bottom: 50 },
      xAxis: { type: 'value', name: '1000/T (1/K)', nameLocation: 'center', nameGap: 28 },
      yAxis: { type: 'value', name: 'ln(σ)', nameLocation: 'center', nameGap: 40 },
      series: [{ type: 'scatter', data: pts, symbolSize: 8, color: '#8b5cf6' }],
    },
  }
}

function buildLiveArrheniusBundle(measurements, liveRt, fit, t) {
  const scatter = scatterLnSigmaFromApi(liveRt) || buildLiveLnSigmaScatter(measurements)
  if (!scatter) return null
  if (!fit?.success || !Array.isArray(fit.segments) || fit.segments.length === 0) {
    return { ...scatter, segments: [], stats: { ...scatter.stats, fit_source: null } }
  }
  const segments = fit.segments.map(normalizeAnalyzerSegment)
  const lineSeries = fit.segments.map((seg, i) => {
    const tr = (seg.temp_range_K || []).map(Number).filter((x) => Number.isFinite(x))
    const tLo = tr.length ? Math.min(...tr) : null
    const tHi = tr.length ? Math.max(...tr) : null
    const { slope, intercept } = seg
    if (tLo == null || tHi == null || slope == null || intercept == null) return null
    const N = 32
    const data = []
    for (let j = 0; j <= N; j++) {
      const T_K = tLo + (j / N) * (tHi - tLo)
      if (!Number.isFinite(T_K) || T_K <= 0) continue
      const x = 1000 / T_K
      const y = Number(slope) * x + Number(intercept)
      data.push([x, y, T_K - 273.15])
    }
    if (!data.length) return null
    const sid = seg.segment_id ?? i
    const eav = seg.Ea_eV != null ? Number(seg.Ea_eV).toFixed(3) : '?'
    return {
      name: `${t('analysis.seg')} ${sid} (Ea=${eav} eV)`,
      type: 'line',
      smooth: false,
      showSymbol: false,
      lineStyle: { width: 2 },
      color: SEG_COLORS[sid % SEG_COLORS.length],
      data,
    }
  }).filter(Boolean)

  const fitLabel = '全局 Arrhenius（本炉次全部测点完成后）'

  return {
    n_points: scatter.n_points,
    segments,
    stats: {
      n_segments: fit.n_segments ?? segments.length,
      confidence: fit.confidence,
      T_range: scatter.stats?.T_range,
      fit_source: fitLabel,
    },
    option: {
      tooltip: { trigger: 'item', formatter: (p) => `T=${p.value[2]?.toFixed?.(1) ?? '?'}°C<br/>1000/T=${p.value[0].toFixed(3)}<br/>ln(σ)=${p.value[1].toFixed(3)}` },
      legend: { top: 4 },
      grid: { left: 60, right: 30, top: 36, bottom: 50 },
      xAxis: { type: 'value', name: '1000/T (1/K)', nameLocation: 'center', nameGap: 28 },
      yAxis: { type: 'value', name: 'ln(σ)', nameLocation: 'center', nameGap: 40 },
      series: [
        {
          name: 'ln σ (测点)',
          type: 'scatter',
          data: scatter.option.series[0].data,
          symbolSize: 9,
          color: '#8b5cf6',
          z: 2,
        },
        ...lineSeries,
      ],
    },
  }
}

// ============== Arrhenius ==============
function ArrheniusView({ source, sampleId, closure, loading, t }) {
  const [mode, setMode] = useState('live')
  const measurements = useDataStore((s) => s.measurements)
  const liveSampleId = useDataStore((s) => s.experimentParams?.sample_id || null)
  const [liveRt, setLiveRt] = useState(null)

  useEffect(() => {
    setMode(source === 'sample' ? 'fit' : 'live')
  }, [source])

  const loadLiveRt = useCallback(() => {
    if (source !== 'live') return
    dataApi.getArrheniusRealtime()
      .then((r) => setLiveRt(r?.data || null))
      .catch(() => setLiveRt(null))
  }, [source])

  useEffect(() => {
    if (source !== 'live') {
      setLiveRt(null)
      return undefined
    }
    loadLiveRt()
    const id = setInterval(loadLiveRt, 2500)
    return () => clearInterval(id)
  }, [source, loadLiveRt, measurements?.length])

  useEffect(() => {
    if (source !== 'live') return undefined
    const onThoughtChain = (data) => {
      const { type } = parseThoughtChainEvent(data)
      if (
        type === 'STAGE0_GLOBAL_ARRHENIUS_COMPLETED'
        || type === 'STAGE0_GLOBAL_ARRHENIUS_FAILED'
        || type === 'STAGE0_GLOBAL_ARRHENIUS_SKIPPED'
        || type === 'EXPERIMENT_COMPLETED'
      ) {
        loadLiveRt()
      }
    }
    return wsService.on(WS_EVENTS.THOUGHT_CHAIN_EVENT, onThoughtChain)
  }, [source, loadLiveRt])

  if (source === 'sample' && loading) {
    return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  }

  const liveData = useMemo(() => {
    if (source !== 'live') return null
    const fit = liveRt?.arrhenius_fit?.success
      ? liveRt.arrhenius_fit
      : (liveRt?.global_arrhenius?.success ? liveRt.global_arrhenius : null)
    return buildLiveArrheniusBundle(measurements, liveRt, fit, t)
  }, [source, measurements, liveRt, t])

  const fitData = useMemo(
    () => (source === 'sample' ? buildFromClosure(closure, t) : null),
    [source, closure, t],
  )

  const showLive = mode === 'live'
  const data = showLive ? liveData : fitData

  return (
    <>
      <Space style={{ marginBottom: 16 }} wrap>
        <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)} size="middle">
          <Radio.Button value="live">{t('analysis.arrModeLive')}</Radio.Button>
          <Radio.Button value="fit" disabled={source !== 'sample'}>{t('analysis.arrModeFit')}</Radio.Button>
        </Radio.Group>
        {source === 'live' && (
          <Tag color="blue">
            横轴 1000/T、纵轴 ln(σ)；测量中仅散点；本炉次 finalize 全局 Arrhenius 完成后显示分段
          </Tag>
        )}
        {mode === 'live' && source === 'live' && <Tag color="processing">{t('analysis.arrLiveHint')}</Tag>}
        {mode === 'fit' && source === 'sample' && closure?.performance_card?.n_segments && (
          <Tag color="success">{t('analysis.arrFitHint')}：{closure.performance_card.n_segments}</Tag>
        )}
      </Space>

      {!data ? (
        <Empty
          description={showLive
            ? '等待第一个 σ(T) 数据点（测量完成后自动出现）'
            : (source === 'sample'
                ? '该样品 closure report 没有 Arrhenius 分段'
                : '请切换到「已落盘样品」并选择样品，以查看 Stage0 分段拟合结果')}
          style={{ padding: 60 }}
        />
      ) : (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col xs={12} sm={6}>
              <Statistic title={t('common.sample')}
                value={source === 'sample' ? (sampleId || '—') : (liveSampleId || '—')}
                valueStyle={{ fontSize: 18 }} />
            </Col>
            <Col xs={12} sm={6}><Statistic title="N points" value={data.n_points ?? '—'} /></Col>
            <Col xs={12} sm={6}>
              <Statistic title={t('analysis.nSegments')}
                value={data.stats?.n_segments ?? '—'} valueStyle={{ fontSize: 16 }} />
            </Col>
            <Col xs={12} sm={6}>
              <Statistic title={t('analysis.tRange')} value={data.stats?.T_range || '—'}
                valueStyle={{ fontSize: 16 }} />
            </Col>
          </Row>
          {showLive && data.stats?.fit_source && (
            <Alert type="success" showIcon style={{ marginBottom: 12 }}
              message={`当前分段来源：${data.stats.fit_source}`}
              description={typeof data.stats?.confidence === 'number'
                ? `模型置信度（AIC 权重）≈ ${data.stats.confidence.toFixed(3)}`
                : undefined}
            />
          )}
          {showLive && data && !data.stats?.fit_source && (data.n_points ?? 0) >= 1 && (
            <Alert type="info" showIcon style={{ marginBottom: 12 }}
              message="分段拟合在本炉次全部测点完成后计算"
              description="测量过程中不展示过程内分段曲线。实验结束并完成全局 Arrhenius 后，上图会出现拟合线与下方表格；若点数不足或分析失败，思考链中会有 STAGE0_GLOBAL_ARRHENIUS_SKIPPED / FAILED 说明。"
            />
          )}

          <ReactECharts option={data.option} style={{ height: 380 }} notMerge lazyUpdate />

          {data.segments?.length > 0 && (
            <Table
              size="small"
              rowKey={(r) => String(r.idx)}
              style={{ marginTop: 16 }}
              dataSource={data.segments}
              pagination={false}
              columns={[
                { title: t('analysis.seg'), dataIndex: 'idx', width: 70,
                  render: (v) => <Tag color={SEG_COLORS[Number(v) % SEG_COLORS.length]}>{t('analysis.seg')} {v}</Tag> },
                { title: 'T (°C)', render: (_, r) => (
                  r.T_low_C != null && r.T_high_C != null
                    ? `${Number(r.T_low_C).toFixed(1)} ~ ${Number(r.T_high_C).toFixed(1)}`
                    : '—') },
                { title: 'Ea (eV)', dataIndex: 'Ea_eV', render: (v) => (v != null ? Number(v).toFixed(3) : '—') },
                { title: 'Ea (kJ/mol)', dataIndex: 'Ea_kJ_per_mol',
                  render: (v) => (v != null ? Number(v).toFixed(2) : '—') },
                { title: 'N', dataIndex: 'n_points', width: 70 },
                { title: 'R²', dataIndex: 'R2', render: (_, r) => {
                  const v = r.R2 ?? r.r_squared
                  return v != null && Number.isFinite(Number(v)) ? Number(v).toFixed(3) : '—'
                }, width: 80 },
              ]}
            />
          )}

          {!showLive && source === 'sample' && closure?.performance_card?.highlight_zh && (
            <Alert type="info" showIcon style={{ marginTop: 16 }}
              message={t('analysis.interpretation')} description={closure.performance_card.highlight_zh} />
          )}
        </>
      )}
    </>
  )
}

function buildFromClosure(closure, t) {
  const pc = closure?.performance_card
  if (!pc?.segments?.length) return null
  const k_B = 8.617333262e-5
  const sigmaRT = pc.sigma_RT_S_per_cm || 1e-3
  const T_RT = 298.15
  const lnSigmaRT_T = Math.log(sigmaRT * T_RT)

  const series = pc.segments.map((seg) => {
    const T_low_K = seg.T_low_C + 273.15
    const T_high_K = seg.T_high_C + 273.15
    const N = 12
    const data = []
    for (let i = 0; i <= N; i++) {
      const T_K = T_low_K + (i / N) * (T_high_K - T_low_K)
      const lnST = lnSigmaRT_T + (seg.Ea_eV / k_B) * (1 / T_RT - 1 / T_K)
      data.push([1000 / T_K, lnST, T_K - 273.15])
    }
    return {
      name: `${t('analysis.seg')} ${seg.idx} (Ea=${seg.Ea_eV.toFixed(2)} eV)`,
      type: 'line', showSymbol: true, symbolSize: 6,
      color: SEG_COLORS[seg.idx % SEG_COLORS.length], data,
    }
  })

  const totalPts = pc.segments.reduce((acc, s) => acc + (s.n_points || 0), 0)
  return {
    n_points: totalPts,
    segments: pc.segments.map((s) => ({ ...s })),
    stats: {
      n_segments: pc.n_segments,
      confidence: pc.arrhenius_confidence,
      T_range: `${pc.T_min_measured_C?.toFixed(0)} ~ ${pc.T_max_measured_C?.toFixed(0)}`,
    },
    option: {
      tooltip: { trigger: 'item', formatter: (p) => `T=${p.value[2].toFixed(1)}°C<br/>1000/T=${p.value[0].toFixed(3)}<br/>ln(σT)=${p.value[1].toFixed(3)}` },
      legend: { top: 4 },
      grid: { left: 60, right: 30, top: 36, bottom: 50 },
      xAxis: { type: 'value', name: '1000/T (1/K)', nameLocation: 'center', nameGap: 28 },
      yAxis: { type: 'value', name: 'ln(σT)', nameLocation: 'center', nameGap: 40 },
      series,
    },
  }
}

export default Analysis
