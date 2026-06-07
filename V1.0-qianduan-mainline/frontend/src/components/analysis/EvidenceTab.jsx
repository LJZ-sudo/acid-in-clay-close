import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { dataApi } from '../../api/data'
import { STUDIO_FILES } from '../../analysis/studioPaths'
import { useStageOutputLoader } from '../../hooks/useStageOutputLoader'
import { StudioEmpty, StudioSection } from './StudioEmpty'

const STAGE2_UNAVAILABLE = 'Stage 2 evidence files not available or not yet indexed. Run Stage 2 statistics and ensure outputs are under output/stage2_statistics/mechanism_evidence/.'

function normalizeReportContent(content) {
  if (content == null || content === '') return ''
  if (typeof content === 'string') return content
  if (typeof content === 'object') {
    try {
      return JSON.stringify(content, null, 2)
    } catch {
      return String(content)
    }
  }
  return String(content)
}

function ReportViewer({ content }) {
  const text = normalizeReportContent(content)
  if (!text) return <div className="text-gray-400 text-sm p-4">Select a sample to load its report.</div>
  const isMarkdown =
    text.includes('#') || text.includes('**') || text.includes('- ')
  return (
    <div className="prose prose-sm max-w-none p-4 bg-white rounded-lg border overflow-auto max-h-[560px]">
      {isMarkdown ? (
        <ReactMarkdown>{text}</ReactMarkdown>
      ) : (
        <pre className="whitespace-pre-wrap text-sm font-sans">{text}</pre>
      )}
    </div>
  )
}

const REC_TYPE_LABELS = {
  ADJUST_RN: { label: 'Adjust R/N ratio', color: 'bg-blue-100 text-blue-800' },
  RE_MEASURE_RANGE: { label: 'Re-measure temperature range', color: 'bg-amber-100 text-amber-800' },
  SUFFICIENT: { label: 'Data sufficient', color: 'bg-green-100 text-green-800' },
}

function NextPlanCard({ plan, sampleId, onDecision }) {
  const [deciding, setDeciding] = useState(false)
  const [notes, setNotes] = useState('')
  const recInfo = REC_TYPE_LABELS[plan.recommendation_type] || { label: plan.recommendation_type, color: 'bg-gray-100 text-gray-800' }

  const handleDecision = async (decision) => {
    setDeciding(true)
    try {
      await dataApi.decideNextPlan({ decision, notes }, sampleId)
      onDecision?.(decision)
    } catch { /* ignore */ }
    setDeciding(false)
  }

  return (
    <div className="mt-4 border border-indigo-200 rounded-xl p-4 space-y-3 bg-indigo-50/50">
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-semibold text-gray-900 text-sm">Next experiment recommendation</h4>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${recInfo.color}`}>{recInfo.label}</span>
      </div>
      <p className="text-xs text-gray-600"><span className="font-semibold">Rationale:</span> {plan.rationale}</p>
      {plan.recommendation_type !== 'SUFFICIENT' && (
        <div className="space-y-2">
          <textarea
            className="w-full border rounded-lg px-2 py-1.5 text-xs"
            rows={2}
            placeholder="Optional notes…"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={deciding} onClick={() => handleDecision('approved')} className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs disabled:opacity-50">Accept</button>
            <button type="button" disabled={deciding} onClick={() => handleDecision('rejected')} className="px-3 py-1.5 bg-gray-200 rounded-lg text-xs">Reject</button>
            <button type="button" disabled={deciding} onClick={() => handleDecision('deferred')} className="px-3 py-1.5 bg-gray-100 rounded-lg text-xs">Defer</button>
          </div>
        </div>
      )}
    </div>
  )
}

function SampleReportBlock() {
  const [experiments, setExperiments] = useState([])
  const [selected, setSelected] = useState(null)
  const [report, setReport] = useState('')
  const [nextPlan, setNextPlan] = useState(null)
  const [decisionMade, setDecisionMade] = useState(null)
  const [loadingReport, setLoadingReport] = useState(false)

  useEffect(() => {
    dataApi.getExperiments().then((r) => setExperiments(r?.data?.experiments || [])).catch(() => {})
  }, [])

  const loadReport = async (expId) => {
    setSelected(expId)
    setLoadingReport(true)
    setNextPlan(null)
    setDecisionMade(null)
    try {
      const resp = await dataApi.getReport(expId)
      setReport(resp?.data?.report || resp?.data?.content || JSON.stringify(resp?.data, null, 2))
    } catch {
      setReport('Report not available for this sample.')
    }
    try {
      const planResp = await dataApi.getSavedNextPlan(expId)
      if (planResp?.data?.ok && planResp.data.next_plan) setNextPlan(planResp.data.next_plan)
    } catch {
      try {
        const planResp = await dataApi.getNextPlan(expId)
        if (planResp?.data?.plan) setNextPlan(planResp.data.plan)
      } catch { /* no plan */ }
    }
    setLoadingReport(false)
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
      <div className="lg:col-span-4 space-y-2">
        <p className="text-xs font-semibold text-gray-600">Samples (GET /data/experiments)</p>
        <div className="space-y-1 max-h-[420px] overflow-auto border rounded-lg p-1 bg-gray-50">
          {experiments.map((exp) => {
            const id = exp.sample_id || exp.id || exp
            return (
              <button
                key={id}
                type="button"
                onClick={() => loadReport(id)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                  selected === id ? 'bg-blue-100 border border-blue-300' : 'hover:bg-white border border-transparent'
                }`}
              >
                <span className="font-mono font-medium">{id}</span>
                {exp.temperature_range && <span className="block text-xs text-gray-500">{exp.temperature_range}</span>}
              </button>
            )
          })}
          {experiments.length === 0 && (
            <div className="text-xs text-gray-500 p-2">No experiments listed. Complete measurements first.</div>
          )}
        </div>
      </div>
      <div className="lg:col-span-8">
        {loadingReport ? (
          <div className="flex h-40 items-center justify-center text-sm text-gray-500">Loading report…</div>
        ) : (
          <>
            <ReportViewer content={report} />
            {nextPlan && !decisionMade && (
              <NextPlanCard plan={nextPlan} sampleId={selected} onDecision={setDecisionMade} />
            )}
            {decisionMade && (
              <div className="mt-3 rounded-lg border bg-gray-50 px-3 py-2 text-xs text-gray-700">
                Decision recorded: <strong className="capitalize">{decisionMade}</strong>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function pickCardFields(row) {
  const sampleId = row.sample_id ?? row.sampleId ?? row.id ?? '—'
  const family = row.family ?? row.material_family ?? row.family_id ?? '—'
  const morph = row.dominant_morphology ?? row.dominant_morphology_type ?? row.morphology ?? row.eis_morphology ?? '—'
  const bp = row.breakpoints ?? row.arrhenius_breakpoints ?? row.segment_breakpoints_T_K
  const breakpoints = Array.isArray(bp) ? bp.join(', ') : typeof bp === 'string' ? bp : bp != null ? String(bp) : '—'
  const weight = row.evidence_weight ?? row.weight ?? row.score ?? row.alignment_score ?? '—'
  return { sampleId, family, morph, breakpoints, weight }
}

function EvidenceCardsBlock() {
  const { loading, result } = useStageOutputLoader(STUDIO_FILES.sampleEvidenceCards, { kindHint: 'jsonl' })

  if (loading) return <p className="text-xs text-gray-500">Loading evidence cards…</p>
  if (!result || result.status !== 'ok' || !result.rows?.length) {
    return <StudioEmpty title="Evidence cards unavailable" detail={result?.message || STAGE2_UNAVAILABLE} />
  }

  return (
    <div className="overflow-auto max-h-[360px] border rounded-lg">
      <table className="w-full text-xs">
        <thead className="bg-gray-100 sticky top-0">
          <tr>
            <th className="text-left px-2 py-2 font-semibold">sample_id</th>
            <th className="text-left px-2 py-2 font-semibold">family</th>
            <th className="text-left px-2 py-2 font-semibold">dominant morphology</th>
            <th className="text-left px-2 py-2 font-semibold">breakpoints</th>
            <th className="text-left px-2 py-2 font-semibold">evidence weight</th>
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => {
            const f = pickCardFields(row)
            return (
              <tr key={i} className="border-t hover:bg-gray-50/80">
                <td className="px-2 py-1.5 font-mono">{f.sampleId}</td>
                <td className="px-2 py-1.5">{f.family}</td>
                <td className="px-2 py-1.5">{f.morph}</td>
                <td className="px-2 py-1.5 font-mono max-w-[180px] truncate" title={f.breakpoints}>{f.breakpoints}</td>
                <td className="px-2 py-1.5">{typeof f.weight === 'object' ? JSON.stringify(f.weight) : f.weight}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ClaimHierarchyBlock() {
  const p = useStageOutputLoader(STUDIO_FILES.patternClaims, { kindHint: 'json' })
  const s = useStageOutputLoader(STUDIO_FILES.signatureClaims, { kindHint: 'json' })
  const u = useStageOutputLoader(STUDIO_FILES.s8ClaimUnits, { kindHint: 'jsonl' })

  const [openId, setOpenId] = useState(null)
  const [atomicMap, setAtomicMap] = useState(() => new Map())

  useEffect(() => {
    if (u.result?.status === 'ok' && u.result.rows) {
      const m = new Map()
      for (const row of u.result.rows) {
        const id = row.claim_id ?? row.id ?? row.unit_id
        if (id) m.set(String(id), row)
      }
      setAtomicMap(m)
    }
  }, [u.result])

  const patterns = useMemo(() => {
    const data = p.result?.status === 'ok' ? p.result.data : null
    if (!data) return []
    if (Array.isArray(data.pattern_claims)) return data.pattern_claims
    if (data.pattern_claims && typeof data.pattern_claims === 'object') return [data.pattern_claims]
    if (Array.isArray(data.claims)) return data.claims
    if (Array.isArray(data)) return data
    return data.patterns ? Object.values(data.patterns) : []
  }, [p.result])

  if (p.loading || s.loading || u.loading) {
    return <p className="text-xs text-gray-500">Loading claim hierarchy…</p>
  }

  const patUnavailable = p.result?.status !== 'ok'
  const sigUnavailable = s.result?.status !== 'ok'

  if (patUnavailable && sigUnavailable && u.result?.status !== 'ok') {
    return <StudioEmpty title="Claim files unavailable" detail={STAGE2_UNAVAILABLE} />
  }

  const resolveSupporting = (refs) => {
    if (refs == null) return []
    const list = Array.isArray(refs)
      ? refs
      : typeof refs === 'string'
        ? [refs]
        : typeof refs === 'object'
          ? Object.values(refs)
          : []
    if (!list.length) return []
    return list.map((r) => {
      const id = typeof r === 'string' ? r : r.claim_id ?? r.ref ?? r.id
      return atomicMap.get(String(id)) || { claim_id: id, text: '(atomic claim not in s8_claim_units.jsonl)' }
    })
  }

  return (
    <div className="space-y-3">
      {!patUnavailable && patterns.length > 0 ? (
        <ul className="space-y-2">
          {patterns.map((claim, idx) => {
            const id = claim.claim_id ?? claim.id ?? `pattern-${idx}`
            const label = claim.statement ?? claim.representative_statement ?? claim.title ?? claim.summary ?? JSON.stringify(claim).slice(0, 120)
            const rawRefs =
              claim.supporting_atomic_claims ?? claim.atomic_refs ?? claim.supports ?? claim.evidence_refs ?? []
            const refs = Array.isArray(rawRefs)
              ? rawRefs
              : typeof rawRefs === 'string'
                ? [rawRefs]
                : rawRefs && typeof rawRefs === 'object'
                  ? Object.values(rawRefs)
                  : []
            const expanded = openId === id
            return (
              <li key={id} className="border rounded-lg overflow-hidden">
                <button
                  type="button"
                  className="w-full text-left px-3 py-2 text-sm font-medium bg-gray-50 hover:bg-gray-100 flex justify-between gap-2"
                  onClick={() => setOpenId(expanded ? null : id)}
                >
                  <span className="line-clamp-2">{label}</span>
                  <span className="text-xs text-gray-500 shrink-0">{expanded ? '▾' : '▸'}</span>
                </button>
                {expanded && (
                  <div className="px-3 py-2 text-xs bg-white border-t space-y-2">
                    <p className="font-semibold text-gray-700">Supporting atomic claims</p>
                    <ul className="list-disc pl-4 space-y-1 text-gray-600">
                      {resolveSupporting(refs).map((a, i) => (
                        <li key={i}>
                          <span className="font-mono text-[10px]">{a.claim_id ?? a.id ?? i}</span>
                          {' — '}
                          {a.text ?? a.statement ?? a.description ?? JSON.stringify(a).slice(0, 200)}
                        </li>
                      ))}
                    </ul>
                    {(!refs || refs.length === 0) && <p className="text-gray-500">No atomic refs linked in file.</p>}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      ) : (
        <StudioEmpty title="Pattern claims unavailable" detail={p.result?.message} />
      )}

      {!sigUnavailable && s.result?.data && (
        <details className="text-xs border rounded-lg p-2">
          <summary className="cursor-pointer font-semibold text-gray-800">Signature claims (JSON)</summary>
          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-[10px] bg-gray-50 p-2 rounded">{JSON.stringify(s.result.data, null, 2)}</pre>
        </details>
      )}
    </div>
  )
}

function AlignmentBlock() {
  const { loading, result } = useStageOutputLoader(STUDIO_FILES.alignmentDistribution, { kindHint: 'json' })

  if (loading) return <p className="text-xs text-gray-500">Loading alignment distribution…</p>
  if (!result || result.status !== 'ok' || !result.data) {
    return <StudioEmpty title="Alignment distribution unavailable" detail={result?.message || STAGE2_UNAVAILABLE} />
  }

  const d = result.data
  const mean = d.mean ?? d.alignment_mean ?? d.summary?.mean
  const median = d.median ?? d.alignment_median ?? d.summary?.median
  const buckets = d.buckets ?? d.histogram ?? d.bin_counts ?? d.distribution_bins

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div className="rounded-lg border bg-slate-50 p-3 text-center">
          <div className="text-[10px] uppercase text-gray-500">Mean</div>
          <div className="text-lg font-semibold text-gray-900">{mean != null ? Number(mean).toFixed(4) : '—'}</div>
        </div>
        <div className="rounded-lg border bg-slate-50 p-3 text-center">
          <div className="text-[10px] uppercase text-gray-500">Median</div>
          <div className="text-lg font-semibold text-gray-900">{median != null ? Number(median).toFixed(4) : '—'}</div>
        </div>
      </div>
      {Array.isArray(buckets) && buckets.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-700 mb-2">Buckets</p>
          <div className="flex items-end gap-1 h-24">
            {buckets.map((b, i) => {
              const label = b.label ?? b.bin ?? b.range ?? String(i)
              const count = b.count ?? b.n ?? b.value ?? 0
              const max = Math.max(...buckets.map((x) => x.count ?? x.n ?? x.value ?? 0), 1)
              const h = `${(Number(count) / max) * 100}%`
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-1 min-w-0">
                  <div className="w-full bg-indigo-200 rounded-t relative flex-1 flex items-end min-h-[4px]">
                    <div className="w-full bg-indigo-600 rounded-t transition-all" style={{ height: h }} title={`${label}: ${count}`} />
                  </div>
                  <span className="text-[9px] text-gray-500 truncate w-full text-center" title={label}>{label}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}
      {(!buckets || !Array.isArray(buckets) || buckets.length === 0) && (
        <pre className="text-[10px] bg-gray-50 p-2 rounded max-h-40 overflow-auto whitespace-pre-wrap">{JSON.stringify(d, null, 2)}</pre>
      )}
    </div>
  )
}

export function EvidenceTab() {
  return (
    <div className="space-y-6">
      <StudioSection title="Sample report viewer" subtitle="Per-sample markdown from GET /data/report/{sample_id}">
        <SampleReportBlock />
      </StudioSection>
      <StudioSection title="Evidence cards" subtitle="From sample_evidence_cards.jsonl (Stage 2 mechanism evidence)">
        <EvidenceCardsBlock />
      </StudioSection>
      <StudioSection title="Claim hierarchy" subtitle="Pattern claims with supporting atomic units">
        <ClaimHierarchyBlock />
      </StudioSection>
      <StudioSection title="EIS–Arrhenius alignment" subtitle="alignment_distribution.json summary">
        <AlignmentBlock />
      </StudioSection>
    </div>
  )
}
