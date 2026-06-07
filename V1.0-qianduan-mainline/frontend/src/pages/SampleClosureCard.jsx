import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { App as AntdApp } from 'antd'
import { samplesApi } from '../api/samples'
import { useThoughtChainRefetch, useClosureOrPostProcessPending } from '../hooks/useThoughtChainRefetch'

function fmt(v, digits = 3) {
  if (v == null || Number.isNaN(v)) return '--'
  if (typeof v !== 'number') return v
  if (Math.abs(v) !== 0 && (Math.abs(v) < 1e-2 || Math.abs(v) >= 1e4)) return v.toExponential(digits)
  return v.toFixed(digits)
}

function fmtSigma(v) {
  if (v == null || Number.isNaN(v)) return '--'
  return Number(v).toExponential(3)
}

function fmtPct(v) {
  if (v == null || Number.isNaN(v)) return '--'
  return `${(v * 100).toFixed(1)}%`
}

const RISK_COLOR = {
  info: 'bg-blue-50 text-blue-700 border-blue-200',
  warn: 'bg-amber-50 text-amber-700 border-amber-200',
  error: 'bg-red-50 text-red-700 border-red-200',
}

function Section({ title, subtitle, children, right }) {
  return (
    <section className="bg-white rounded-xl border p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-gray-900">{title}</h3>
          {subtitle && <div className="text-xs text-gray-500">{subtitle}</div>}
        </div>
        {right}
      </div>
      {children}
    </section>
  )
}

function MiniSigmaT({ eis }) {
  // 极简 SVG sparkline 显示 σ vs T_C
  const ok = (eis || []).filter(p => p.status === 'OK' && p.sigma_S_cm != null && p.T_C != null)
  if (ok.length < 2) {
    return <div className="text-xs text-gray-500">点数不足</div>
  }
  const xs = ok.map(p => p.T_C)
  const ys = ok.map(p => Math.log10(p.sigma_S_cm))
  const minX = Math.min(...xs); const maxX = Math.max(...xs)
  const minY = Math.min(...ys); const maxY = Math.max(...ys)
  const W = 320; const H = 96; const PAD = 6
  const sx = x => PAD + ((x - minX) / (maxX - minX || 1)) * (W - 2 * PAD)
  const sy = y => H - PAD - ((y - minY) / (maxY - minY || 1)) * (H - 2 * PAD)
  const sorted = [...ok].sort((a, b) => a.T_C - b.T_C)
  const path = sorted.map((p, i) => `${i === 0 ? 'M' : 'L'} ${sx(p.T_C).toFixed(1)} ${sy(Math.log10(p.sigma_S_cm)).toFixed(1)}`).join(' ')
  return (
    <svg width={W} height={H} className="block">
      <path d={path} fill="none" stroke="#4f46e5" strokeWidth={1.5} />
      {sorted.map((p, i) => (
        <circle key={i} cx={sx(p.T_C)} cy={sy(Math.log10(p.sigma_S_cm))} r={2} fill="#4f46e5" />
      ))}
      <text x={PAD} y={H - 1} fontSize="9" fill="#6b7280">T_min={fmt(minX, 1)}°C</text>
      <text x={W - 70} y={H - 1} fontSize="9" fill="#6b7280">T_max={fmt(maxX, 1)}°C</text>
    </svg>
  )
}

export default function SampleClosureCard({ sampleId: sampleIdProp, hideBreadcrumb = false } = {}) {
  const params = useParams()
  const sampleId = sampleIdProp || params.sampleId
  const { message } = AntdApp.useApp()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [generating, setGenerating] = useState(false)

  const load = useCallback(async () => {
    if (!sampleId) {
      setLoading(false)
      setData(null)
      setError('缺少 sample_id')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const resp = await samplesApi.get(sampleId)
      setData(resp.data)
    } catch (e) {
      setData(null)
      setError(e?.response?.data?.detail || e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [sampleId])

  useEffect(() => {
    load()
  }, [load])

  useThoughtChainRefetch(sampleId, { onRefreshThisSample: load })
  const remotePending = useClosureOrPostProcessPending(sampleId)

  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === 'visible') load()
    }
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [load])

  const handleRegen = async (useLlm) => {
    setGenerating(true)
    try {
      await samplesApi.generateClosureReport(sampleId, { use_llm: useLlm })
      await load()
    } catch (e) {
      message.error('生成失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setGenerating(false)
    }
  }

  const closure = data?.closure_report
  const bundle = data?.bundle
  const summary = data?.summary
  const meta = closure?.meta
  const identity = closure?.identity
  const perf = closure?.performance_card
  const qual = closure?.quality_card
  const transitions = closure?.phase_transitions || []
  const mech = closure?.mechanism_note
  const risks = closure?.risks_warnings || []
  const cmp = closure?.campaign_comparison
  const compAnalysis = closure?.comprehensive_analysis_zh || ''

  const llmBadge = useMemo(() => {
    if (!closure) return null
    if (meta?.llm_used) {
      return <span className="px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-700">LLM · {meta.llm_model || ''}</span>
    }
    return <span className="px-2 py-0.5 rounded text-xs bg-blue-100 text-blue-700">仅事实（无 LLM）</span>
  }, [closure, meta])

  if (loading) return <div className="p-6 text-gray-500">Loading sample…</div>
  if (error) return <div className="p-6 text-red-600">{error}</div>
  if (!data) return null

  return (
    <div className="space-y-4">
      {!hideBreadcrumb && (
        <nav className="text-xs text-gray-500 flex items-center gap-1.5">
          <Link to="/" className="hover:text-primary-600 hover:underline">Home</Link>
          <span className="text-gray-300">›</span>
          <Link to="/report" className="hover:text-primary-600 hover:underline">Report</Link>
          <span className="text-gray-300">›</span>
          <span className="text-gray-700 font-mono">{sampleId}</span>
        </nav>
      )}

      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-900 to-indigo-700 rounded-xl p-5 text-white flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold">{sampleId}</h1>
          <div className="text-indigo-200 text-sm mt-1">
            {identity?.material_system || bundle?.material_system || '—'}
            {identity?.R != null && <> · R={identity.R.toFixed(3)}</>}
            {identity?.N != null && <> · N={identity.N.toFixed(3)}</>}
            {identity?.acid_type && <> · {identity.acid_type}</>}
            {identity?.clay_type && <> · {identity.clay_type}</>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {llmBadge}
          <Link
            to={`/optimization?anchor=${encodeURIComponent(sampleId)}`}
            className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-xs"
            title="Open the BO landscape with this sample highlighted"
          >
            在 BO landscape 中查看 →
          </Link>
          <button
            disabled={generating}
            onClick={() => handleRegen(false)}
            className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-xs disabled:opacity-50"
            title="Re-generate with code-only (no LLM call)"
          >
            {generating ? '...' : 'Rebuild (facts)'}
          </button>
          <button
            disabled={generating}
            onClick={() => handleRegen(true)}
            className="px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-400 text-white text-xs disabled:opacity-50"
            title="Re-generate with LLM (DeepSeek-V4-Pro default)"
          >
            {generating ? '...' : 'Rebuild (LLM)'}
          </button>
          <button
            type="button"
            onClick={() => {
              const blob = new Blob([JSON.stringify(closure ?? data, null, 2)], { type: 'application/json' })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = `${sampleId}_closure_report.json`
              a.click()
              URL.revokeObjectURL(url)
            }}
            disabled={!closure}
            className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-xs disabled:opacity-40"
            title="Download closure report JSON"
          >
            ⇣ JSON
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-xs"
            title="Print or save as PDF (browser print dialog)"
          >
            🖨 PDF
          </button>
        </div>
      </div>

      {/* No closure report yet */}
      {!closure && remotePending && (
        <div className="bg-sky-50 border border-sky-200 rounded-xl p-4 text-sky-900 text-sm">
          后处理或 Closure 报告正在生成中，完成后将自动刷新。也可切换页面再返回，或切到浏览器其他标签再回来。
        </div>
      )}
      {!closure && !remotePending && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-800 text-sm">
          该样品尚未生成 Closure Report。点右上角「重建」按钮即可生成。
        </div>
      )}

      {/* Comprehensive analysis (v4-pro 主笔；只供研究者阅读) */}
      {closure && (
        <section className="bg-white rounded-xl border border-indigo-200 p-5">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h3 className="font-semibold text-gray-900">综合分析</h3>
              <div className="text-xs text-gray-500">
                跨卡片推理 · LLM 主笔 · 仅供研究者阅读 · 不流入下游 BO / Stage2 / Stage3
              </div>
            </div>
            {meta?.llm_model && (
              <span className="px-2 py-0.5 rounded text-xs bg-indigo-50 text-indigo-700 font-mono">
                {meta.llm_model}
              </span>
            )}
          </div>
          {compAnalysis ? (
            <p className="text-sm leading-relaxed text-gray-800 whitespace-pre-wrap">{compAnalysis}</p>
          ) : (
            <div className="text-sm text-gray-500 italic">
              {meta?.llm_used === false
                ? '此报告未启用 LLM（仅事实），故无综合分析段。点右上角"重建（含 LLM）"生成。'
                : '（LLM 未给出综合分析段）'}
            </div>
          )}
        </section>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Performance card */}
        <Section title="Performance Card" subtitle="室温 σ / 最佳输运模型 / 各段 Ea">
          {perf ? (
            <>
              <div className="text-sm text-gray-700 italic">{perf.highlight_zh || (closure ? '（LLM 未给出，或未启用）' : '')}</div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><div className="text-xs text-gray-500">σ@RT (S/cm)</div><div className="font-mono">{fmtSigma(perf.sigma_RT_S_per_cm)}</div></div>
                <div><div className="text-xs text-gray-500">σ_max (S/cm)</div><div className="font-mono">{fmtSigma(perf.sigma_max_S_per_cm)}</div></div>
                <div><div className="text-xs text-gray-500">T@σ_max</div><div className="font-mono">{fmt(perf.T_at_sigma_max_C, 1)} °C</div></div>
                <div><div className="text-xs text-gray-500">T_min 测得</div><div className="font-mono">{fmt(perf.T_min_measured_C, 1)} °C</div></div>
                <div className="col-span-2"><div className="text-xs text-gray-500">最佳模型</div><div className="font-mono">{perf.transport_model || '--'} ({perf.n_segments} 段, conf {fmt(perf.arrhenius_confidence, 3)})</div></div>
              </div>
              <MiniSigmaT eis={bundle?.eis_points} />
              <table className="w-full text-xs mt-2">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="text-left px-2 py-1">idx</th>
                    <th className="text-right px-2 py-1">T_low</th>
                    <th className="text-right px-2 py-1">T_high</th>
                    <th className="text-right px-2 py-1">Ea (eV)</th>
                    <th className="text-right px-2 py-1">Ea (kJ/mol)</th>
                    <th className="text-right px-2 py-1">n_pts</th>
                  </tr>
                </thead>
                <tbody>
                  {(perf.segments || []).map(s => (
                    <tr key={s.idx} className="border-t">
                      <td className="px-2 py-1 font-mono">{s.idx}</td>
                      <td className="px-2 py-1 text-right font-mono">{fmt(s.T_low_C, 1)}</td>
                      <td className="px-2 py-1 text-right font-mono">{fmt(s.T_high_C, 1)}</td>
                      <td className="px-2 py-1 text-right font-mono">{fmt(s.Ea_eV, 3)}</td>
                      <td className="px-2 py-1 text-right font-mono">{fmt(s.Ea_kJ_per_mol, 1)}</td>
                      <td className="px-2 py-1 text-right font-mono">{s.n_points ?? '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <div className="text-sm text-gray-500">无 Closure Report</div>
          )}
        </Section>

        {/* Quality card */}
        <Section title="Quality Card" subtitle="KK / Rb 置信度 / Nyquist 形态">
          {qual ? (
            <>
              <div className="text-sm text-gray-700 italic">{qual.verdict_zh || (closure ? '（LLM 未给出，或未启用）' : '')}</div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><div className="text-xs text-gray-500">EIS 点 (OK / 总)</div><div className="font-mono">{qual.n_eis_ok}/{qual.n_eis_points}</div></div>
                <div><div className="text-xs text-gray-500">KK pass-rate</div><div className="font-mono">{fmtPct(qual.KK_pass_rate)}</div></div>
                <div><div className="text-xs text-gray-500">Rb conf p25/p50/p75</div><div className="font-mono">{fmt(qual.rb_confidence_p25, 2)}/{fmt(qual.rb_confidence_p50, 2)}/{fmt(qual.rb_confidence_p75, 2)}</div></div>
                <div><div className="text-xs text-gray-500">Nyquist</div><div className="font-mono">{qual.nyquist_morphology_auto || '--'}</div></div>
              </div>
              <div className="grid grid-cols-4 gap-1 text-center text-xs">
                {Object.entries(qual.qc_distribution || {}).map(([g, n]) => (
                  <div key={g} className="rounded bg-gray-50 py-1">
                    <div className="font-bold">{g}</div>
                    <div className="font-mono">{n}</div>
                  </div>
                ))}
              </div>
              {qual.drt_peaks && qual.drt_peaks.length > 0 && (
                <div className="text-xs text-gray-600">DRT τ peaks: {qual.drt_peaks.length}</div>
              )}
            </>
          ) : (
            <div className="text-sm text-gray-500">无 Closure Report</div>
          )}
        </Section>

        {/* Phase transitions + mechanism */}
        <Section title="相变 + 机理浅评" subtitle="LLM 只能翻译已测特征，不能新增数字">
          {closure ? (
            <>
              <div className="text-sm">
                <div className="text-xs text-gray-500 mb-1">检出相变 ({transitions.length})</div>
                {transitions.length === 0 ? (
                  <div className="text-gray-500 text-xs">未检出</div>
                ) : (
                  <ul className="space-y-1">
                    {transitions.map((pt, i) => (
                      <li key={i} className="border rounded p-2 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="font-mono">T = {fmt(pt.T_C, 2)} °C</span>
                          <span className="text-gray-500">conf {pt.confidence}</span>
                        </div>
                        <div className="mt-1">类型：<span className="font-medium">{pt.type_zh}</span> ({pt.type_code})</div>
                        {pt.note_zh && <div className="text-gray-600 mt-0.5">{pt.note_zh}</div>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="border-t pt-2 text-sm">
                <div className="text-xs text-gray-500 mb-1">机理浅评</div>
                <p className="leading-relaxed text-gray-800">{mech?.primary_zh || '--'}</p>
                {mech?.supporting_segment_ids?.length > 0 && (
                  <div className="text-xs text-gray-500 mt-1">引用段 idx: {mech.supporting_segment_ids.join(', ')}</div>
                )}
                {mech?.caveat_zh && (
                  <div className="text-xs text-amber-700 mt-1">{mech.caveat_zh}</div>
                )}
              </div>
            </>
          ) : (
            <div className="text-sm text-gray-500">无 Closure Report</div>
          )}
        </Section>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Section title="风险与异常" subtitle="代码扫硬规则 + LLM 友好措辞">
          {risks.length === 0 ? (
            <div className="text-sm text-gray-500">未发现风险</div>
          ) : (
            <ul className="space-y-2">
              {risks.map((r, i) => (
                <li key={i} className={`border rounded p-2 text-xs ${RISK_COLOR[r.severity] || 'bg-gray-50'}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-mono">{r.code}</span>
                    <span className="uppercase text-[10px]">{r.severity}</span>
                  </div>
                  {r.human_zh && <div className="mt-1">{r.human_zh}</div>}
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Campaign 浅对比" subtitle="不显示邻居样品 / Pareto 前沿，避免 LLM 编故事">
          {cmp ? (
            <div className="space-y-2 text-sm">
              <div>{cmp.one_liner_zh || '--'}</div>
              <div className="text-xs text-gray-500">
                Δ vs best: <span className="font-mono">{cmp.delta_vs_best_pct != null ? `${cmp.delta_vs_best_pct.toFixed(2)}%` : '--'}</span>
              </div>
              {summary?.sigma_RT_S_per_cm != null && (
                <div className="text-xs text-gray-500">
                  本样品 σ_RT = <span className="font-mono">{fmtSigma(summary.sigma_RT_S_per_cm)}</span>
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-500">无 Closure Report</div>
          )}
        </Section>

        <Section title="元数据" subtitle="prompt / model / 时间戳 / 输入哈希">
          {meta ? (
            <ul className="text-xs text-gray-700 space-y-1 font-mono">
              <li>generated_at: {meta.generated_at}</li>
              <li>schema: {meta.schema_version}</li>
              <li>llm_used: {String(meta.llm_used)}</li>
              {meta.llm_model && <li>llm_model: {meta.llm_model}</li>}
              <li>prompt_version: {meta.prompt_version}</li>
              <li>prompt_sha256: {meta.prompt_sha256}</li>
              <li>input_summary_sha256: {meta.input_summary_sha256}</li>
              {meta.fallback_reason && <li className="text-amber-700">fallback_reason: {meta.fallback_reason}</li>}
            </ul>
          ) : (
            <div className="text-sm text-gray-500">无 Closure Report</div>
          )}
          {closure?.do_not_overclaim?.length > 0 && (
            <div className="border-t pt-2 text-xs text-gray-600">
              <div className="font-semibold mb-1">do_not_overclaim</div>
              <ul className="list-disc pl-4 space-y-0.5">
                {closure.do_not_overclaim.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
        </Section>
      </div>
    </div>
  )
}
