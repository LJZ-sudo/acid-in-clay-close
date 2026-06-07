import { STUDIO_FILES } from '../../../analysis/studioPaths'
import { useStageOutputLoader } from '../../../hooks/useStageOutputLoader'
import { StudioSection } from '../StudioEmpty'

const OVERALL_LABELS = {
  support: 'Support',
  partial_support: 'Partial support',
  weaken: 'Weaken',
  unavailable: 'Unavailable',
  inconclusive: 'Inconclusive',
}

function isAdjudicationContract(d) {
  if (!d || typeof d !== 'object') return false
  if (typeof d.status !== 'string') return false
  if (!d.validation_subject || typeof d.validation_subject !== 'object') return false
  if (!Array.isArray(d.predictions_tested)) return false
  return true
}

function deriveOverallAdjudication(d) {
  const explicit = d.overall_adjudication
  if (explicit && OVERALL_LABELS[explicit]) return explicit

  const st = d.status
  if (st === 'unavailable') return 'unavailable'

  const preds = d.predictions_tested || []
  const levels = preds.map((p) => p?.observed_support || p?.support_level || '').filter(Boolean)

  if (levels.length === 0) {
    if (st === 'partial') return 'partial_support'
    if (st === 'measured') return 'inconclusive'
    return 'unavailable'
  }

  if (levels.some((x) => x === 'weaken')) {
    if (levels.some((x) => x === 'support' || x === 'partial_support')) return 'partial_support'
    return 'weaken'
  }
  if (levels.every((x) => x === 'inconclusive')) return 'inconclusive'
  if (levels.some((x) => x === 'inconclusive')) return 'partial_support'
  if (levels.every((x) => x === 'support')) return 'support'
  if (levels.some((x) => x === 'partial_support')) return 'partial_support'
  return 'partial_support'
}

function fmt(v) {
  if (v === null || v === undefined || v === '') return 'Unavailable'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

function ContractPlaceholder() {
  return (
    <div className="space-y-4 text-sm text-gray-700">
      <div className="rounded-lg border border-amber-200 bg-amber-50/90 p-4 space-y-2">
        <p className="font-semibold text-amber-950">Measured validation artifact not yet indexed</p>
        <p className="text-xs leading-relaxed">
          The canonical file <code className="text-[10px] bg-white px-1 rounded">output/stage3_mechanism/measured_validation_adjudication.json</code>{' '}
          was not found or could not be loaded. No measured results are fabricated on this page.
        </p>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-2">
        <p className="text-xs font-semibold text-gray-900">Expected contract (summary)</p>
        <ul className="text-xs list-disc pl-5 space-y-1 text-gray-600">
          <li>
            <strong>Required:</strong> <code className="text-[10px]">validation_subject</code>,{' '}
            <code className="text-[10px]">status</code> (<code>measured | partial | unavailable</code>),{' '}
            <code className="text-[10px]">predictions_tested</code> (array of statements with{' '}
            <code className="text-[10px]">observed_support</code>: support / partial_support / weaken / inconclusive).
          </li>
          <li>
            <strong>Optional:</strong> <code className="text-[10px]">overall_adjudication</code>,{' '}
            <code className="text-[10px]">quantitative_summary</code>, <code className="text-[10px]">comparison</code>,{' '}
            <code className="text-[10px]">notes</code>.
          </li>
          <li>Full schema: <code className="text-[10px]">docs/STEP7_MEASURED_VALIDATION_CONTRACT.md</code></li>
        </ul>
      </div>

      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 text-xs text-gray-600 space-y-2">
        <p className="font-medium text-gray-800">What Section E will show once the file exists</p>
        <ol className="list-decimal pl-5 space-y-1">
          <li>Validation subject (route, instance, recipe, experiment id, source).</li>
          <li>Predictions tested — each with expected signature and observed support level.</li>
          <li>Quantitative summary — σ, Eₐ window, onset, retention (only if present in file).</li>
          <li>Overall adjudication — support / partial support / weaken / unavailable / inconclusive; experiment adjudicates prediction.</li>
        </ol>
      </div>
    </div>
  )
}

function LegacyTraceCard({ data }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-gray-700 space-y-2 mt-4">
      <p className="font-semibold text-gray-900">Legacy pipeline trace only</p>
      <p className="leading-relaxed">
        Loaded <code className="text-[10px] bg-white px-1 rounded">selected_candidate_validation_trace.json</code> (Step 4 helper). This file does{' '}
        <strong>not</strong> contain per-prediction adjudication or quantitative summaries. Prefer{' '}
        <code className="text-[10px] bg-white px-1 rounded">measured_validation_adjudication.json</code> for Section E.
      </p>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 font-mono text-[11px]">
        <div>
          <dt className="text-gray-500">candidate</dt>
          <dd>{fmt(data.candidate)}</dd>
        </div>
        <div>
          <dt className="text-gray-500">has_measured_data</dt>
          <dd>{data.has_measured_data === true ? 'true' : data.has_measured_data === false ? 'false' : 'Unavailable'}</dd>
        </div>
        <div>
          <dt className="text-gray-500">selection_mode</dt>
          <dd>{fmt(data.selection_mode)}</dd>
        </div>
        <div>
          <dt className="text-gray-500">generated_at</dt>
          <dd>{fmt(data.generated_at)}</dd>
        </div>
      </dl>
    </div>
  )
}

function AdjudicationBody({ d }) {
  const sub = d.validation_subject || {}
  const routeId = sub.route_id ?? sub.route ?? sub.routeId
  const instanceId = sub.instance_id ?? sub.instance ?? sub.instanceId
  const recipeId = sub.recipe_id ?? sub.recipe ?? sub.recipeId
  const experimentId = sub.experiment_id ?? sub.experimentId ?? sub.run_id
  const source = sub.source ?? sub.provenance

  const q = d.quantitative_summary && typeof d.quantitative_summary === 'object' ? d.quantitative_summary : {}
  const ea = q.effective_ea_window && typeof q.effective_ea_window === 'object' ? q.effective_ea_window : {}

  const overall = deriveOverallAdjudication(d)
  const cmp = d.comparison && typeof d.comparison === 'object' ? d.comparison : {}
  const routeExpect = cmp.against_predicted_route_expectation ?? cmp.route_consistency

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-600 leading-relaxed border-l-4 border-slate-300 pl-3">
        Laboratory measurement adjudicates predictions. Outcomes can be partial, inconclusive, or weakening — not an AI self-proof.
      </p>

      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-2">
        <h4 className="text-xs font-semibold text-gray-900 uppercase tracking-wide">1. Validation subject</h4>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <div><dt className="text-gray-500">Route</dt><dd className="font-mono text-gray-900">{fmt(routeId)}</dd></div>
          <div><dt className="text-gray-500">Instance</dt><dd className="font-mono text-gray-900">{fmt(instanceId)}</dd></div>
          <div><dt className="text-gray-500">Recipe</dt><dd className="font-mono text-gray-900">{fmt(recipeId)}</dd></div>
          <div><dt className="text-gray-500">Experiment id</dt><dd className="font-mono text-gray-900">{fmt(experimentId)}</dd></div>
          <div className="sm:col-span-2"><dt className="text-gray-500">Source</dt><dd className="font-mono text-gray-900">{fmt(source)}</dd></div>
        </dl>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-2">
        <h4 className="text-xs font-semibold text-gray-900 uppercase tracking-wide">2. Predictions tested</h4>
        {d.predictions_tested.length === 0 ? (
          <p className="text-xs text-gray-500">No prediction rows in file.</p>
        ) : (
          <ul className="space-y-3">
            {d.predictions_tested.map((p, i) => {
              const id = p.id ?? p.prediction_id ?? `row_${i + 1}`
              const stmt = p.statement ?? p.claim ?? p.text
              const exp = p.expected_signature ?? p.expected ?? p.signature
              const obs = p.observed_support ?? p.support_level ?? p.verdict
              const ref = p.evidence_ref ?? p.evidence ?? p.ref
              return (
                <li key={id} className="text-xs border border-gray-100 rounded-lg p-3 bg-gray-50/80">
                  <p className="font-mono font-semibold text-gray-800">{fmt(id)}</p>
                  <p className="mt-1 text-gray-700"><span className="font-medium text-gray-600">Statement:</span> {fmt(stmt)}</p>
                  <p className="mt-0.5 text-gray-600"><span className="font-medium">Expected signature:</span> {fmt(exp)}</p>
                  <p className="mt-0.5"><span className="font-medium">Observed support:</span> {fmt(obs)}</p>
                  <p className="mt-0.5 text-gray-500"><span className="font-medium">Evidence ref:</span> {fmt(ref)}</p>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-2">
        <h4 className="text-xs font-semibold text-gray-900 uppercase tracking-wide">3. Quantitative summary</h4>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <div>
            <dt className="text-gray-500">σ ref T (°C)</dt>
            <dd className="font-mono">{fmt(q.sigma_ref_temperature_c)}</dd>
          </div>
          <div>
            <dt className="text-gray-500">σ ref (S/cm)</dt>
            <dd className="font-mono">{fmt(q.sigma_ref_s_cm)}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-gray-500">Effective Eₐ window</dt>
            <dd className="font-mono">
              {ea.range_c != null || ea.value_eV != null || ea.method
                ? `${fmt(ea.range_c)} | ${fmt(ea.value_eV)} eV | ${fmt(ea.method)}`
                : 'Unavailable'}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Collapse onset (°C)</dt>
            <dd className="font-mono">{fmt(q.collapse_onset_c)}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Retention ratio</dt>
            <dd className="font-mono">{fmt(q.retention_ratio)}</dd>
          </div>
        </dl>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-2">
        <h4 className="text-xs font-semibold text-gray-900 uppercase tracking-wide">4. Overall adjudication</h4>
        <p className="text-sm text-gray-900">
          <span className="font-semibold">{OVERALL_LABELS[overall] || overall}</span>
          {d.overall_adjudication && (
            <span className="text-xs text-gray-500 ml-2">(explicit field in file)</span>
          )}
        </p>
        <p className="text-xs text-gray-600">
          File <code className="text-[10px] bg-gray-100 px-1 rounded">status</code>: {fmt(d.status)}
        </p>
        {routeExpect && (
          <p className="text-xs text-gray-700">
            <span className="font-medium">Vs predicted route expectation:</span> {fmt(routeExpect)}
          </p>
        )}
        {Array.isArray(d.notes) && d.notes.length > 0 && (
          <ul className="text-xs list-disc pl-5 text-gray-600 space-y-0.5">
            {d.notes.map((n, i) => (
              <li key={i}>{typeof n === 'string' ? n : JSON.stringify(n)}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export function MeasuredValidationSection() {
  const adj = useStageOutputLoader(STUDIO_FILES.measuredValidationAdjudication, { kindHint: 'json' })
  const leg = useStageOutputLoader(STUDIO_FILES.legacySelectedCandidateValidationTrace, { kindHint: 'json' })

  const adjOk = adj.result?.status === 'ok' && isAdjudicationContract(adj.result.data)
  const legOk = leg.result?.status === 'ok' && leg.result.data && typeof leg.result.data === 'object'

  const loading = adj.loading || (!adjOk && leg.loading)

  if (loading) {
    return (
      <StudioSection title="E. Measured Validation" subtitle="Laboratory adjudication of predictions">
        <p className="text-xs text-gray-500">Loading measured validation sources…</p>
      </StudioSection>
    )
  }

  if (adjOk) {
    return (
      <StudioSection title="E. Measured Validation" subtitle="measured_validation_adjudication.json">
        <AdjudicationBody d={adj.result.data} />
      </StudioSection>
    )
  }

  const malformed =
    adj.result?.status === 'ok' && adj.result.data && !isAdjudicationContract(adj.result.data)

  return (
    <StudioSection title="E. Measured Validation" subtitle="Laboratory adjudication of predictions">
      {malformed && (
        <div className="rounded-lg border border-red-200 bg-red-50/80 p-3 text-xs text-red-900 mb-4">
          File <code className="text-[10px] bg-white/80 px-1 rounded">measured_validation_adjudication.json</code> is present but
          does not match the required shape (needs <code className="text-[10px]">validation_subject</code>,{' '}
          <code className="text-[10px]">status</code>, <code className="text-[10px]">predictions_tested</code>). No values are
          invented below.
        </div>
      )}
      <ContractPlaceholder />
      {legOk && <LegacyTraceCard data={leg.result.data} />}
    </StudioSection>
  )
}
