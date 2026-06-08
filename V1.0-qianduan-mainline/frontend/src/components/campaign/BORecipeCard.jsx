import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

/**
 * BORecipeCard maps the campaign next recipe returned by /api/campaigns/:slug/next-recipe.
 *
 * Surfaces the four pieces of evidence the paper relies on:
 *   - recommended R / N (LLM) and confidence
 *   - the BO raw suggestion + delta (so reviewers see what the LLM changed and why)
 *   - safety_box (passed / violations / warnings)
 *   - provenance (BO acq_func + seed, prompt sha256, LLM model)
 */
function fmtNum(v, digits = 4) {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  return Number(v).toFixed(digits)
}

function Section({ title, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-t border-gray-200">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50"
      >
        <span>{title}</span>
        <span className="text-gray-400">{open ? '−' : '+'}</span>
      </button>
      {open && <div className="px-4 pb-3 pt-1 text-xs text-gray-700">{children}</div>}
    </div>
  )
}

function BORecipeCard({ wrapper, anchorSampleId = null, campaignSlug = null }) {
  const navigate = useNavigate()
  if (!wrapper || !wrapper.recipe) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 text-sm text-gray-400">
        next_experiment_recipe.json not generated yet — run
        <code className="mx-1 px-1 bg-gray-100 rounded">stage1_optimization/run_optimization_loop.py</code>
        to produce a recommendation.
      </div>
    )
  }
  const root = wrapper.recipe
  const rec = root.recipe || {}
  const opt = root.optimizer_suggestion || {}
  const delta = root.optimizer_vs_llm_delta || {}
  const safety = root.safety_box || {}
  const meta = root.metadata || {}
  const params = rec.recommended_parameters || {}
  const conf = rec.confidence_score
  const safetyOk = safety.passed !== false
  const adjusted = delta.adjusted

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden flex flex-col">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between gap-2">
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">Next Experiment</div>
          <div className="text-sm font-semibold text-gray-900">LLM-adjusted recipe</div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
              safetyOk ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
            }`}
            title={safetyOk ? 'safety_box.passed = true' : safety.violations?.join('; ')}
          >
            Safety {safetyOk ? '✓' : '✗'}
          </span>
          {adjusted && (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
              LLM adjusted
            </span>
          )}
        </div>
      </div>

      <div className="px-4 py-4">
        <div className="grid grid-cols-2 gap-3">
          {Object.entries(params).map(([k, v]) => (
            <div key={k} className="bg-gray-50 border border-gray-100 rounded p-2">
              <div className="text-[10px] uppercase text-gray-500 tracking-wide">{k}</div>
              <div className="text-2xl font-semibold text-gray-900 tabular-nums">{fmtNum(v, 2)}</div>
            </div>
          ))}
        </div>

        {conf != null && (
          <div className="mt-3">
            <div className="flex items-center justify-between text-[11px] text-gray-500">
              <span>confidence</span>
              <span className="tabular-nums">{fmtNum(conf, 2)}</span>
            </div>
            <div className="h-1.5 bg-gray-100 rounded mt-1 overflow-hidden">
              <div
                className="h-full bg-primary-600"
                style={{ width: `${Math.max(0, Math.min(1, Number(conf))) * 100}%` }}
              />
            </div>
          </div>
        )}

        {anchorSampleId && (
          <div className="mt-3 text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1">
            Anchored to <span className="font-mono">{anchorSampleId}</span> from sample card.
          </div>
        )}

        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              const qs = new URLSearchParams()
              if (params.R != null) qs.set('R', String(params.R))
              if (params.N != null) qs.set('N', String(params.N))
              if (campaignSlug) qs.set('campaign', campaignSlug)
              if (anchorSampleId) qs.set('parent', anchorSampleId)
              navigate(`/control?${qs.toString()}`)
            }}
            disabled={!safetyOk}
            className={`text-xs font-semibold px-3 py-1.5 rounded ${
              safetyOk
                ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
            }`}
            title={safetyOk ? 'Pre-fill the Run Wizard with this R/N' : 'Recipe failed safety_box'}
          >
            ▶ 采纳推荐 → 启动测量
          </button>
          {campaignSlug && (
            <span className="text-[10px] text-gray-400 font-mono">campaign: {campaignSlug}</span>
          )}
        </div>
      </div>

      <Section title="BO ↔ LLM delta" defaultOpen>
        <table className="w-full text-[11px] tabular-nums">
          <thead>
            <tr className="text-gray-500">
              <th className="text-left font-normal">param</th>
              <th className="text-right font-normal">BO raw</th>
              <th className="text-right font-normal">LLM</th>
              <th className="text-right font-normal">Δ</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(delta.parameters || {}).map(([k, v]) => (
              <tr key={k} className="border-t border-gray-100">
                <td className="py-1 font-mono">{k}</td>
                <td className="py-1 text-right">{fmtNum(v.optimizer, 2)}</td>
                <td className="py-1 text-right font-semibold">{fmtNum(v.llm, 2)}</td>
                <td className={`py-1 text-right ${Number(v.delta) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                  {Number(v.delta) >= 0 ? '+' : ''}
                  {fmtNum(v.delta, 2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {delta.adjustment_reason && (
          <p className="mt-2 leading-relaxed text-gray-700 whitespace-pre-line">{delta.adjustment_reason}</p>
        )}
      </Section>

      <Section title="Expected outcome & warnings">
        {rec.expected_outcome && <p className="leading-relaxed">{rec.expected_outcome}</p>}
        {Array.isArray(rec.warnings) && rec.warnings.length > 0 && (
          <ul className="mt-2 space-y-1 list-disc list-inside text-amber-700">
            {rec.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        )}
        {Array.isArray(safety.warnings) && safety.warnings.length > 0 && (
          <div className="mt-2">
            <div className="font-semibold text-gray-700">Safety advisories</div>
            <ul className="mt-1 space-y-1 list-disc list-inside text-amber-700">
              {safety.warnings.map((w, i) => (
                <li key={`s${i}`}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </Section>

      <Section title="Provenance">
        <dl className="grid grid-cols-1 gap-y-1">
          <div className="flex justify-between gap-2">
            <dt className="text-gray-500">BO optimizer</dt>
            <dd className="font-mono text-right">{meta.bo_provenance?.optimizer ?? '—'}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-gray-500">acq_func / seed</dt>
            <dd className="font-mono text-right">
              {meta.bo_provenance?.acq_func ?? '—'} / {meta.bo_provenance?.random_state ?? '—'}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-gray-500">n_train_points</dt>
            <dd className="font-mono text-right">{meta.bo_provenance?.n_train_points ?? '—'}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-gray-500">LLM model</dt>
            <dd className="font-mono text-right">{meta.llm_model_info?.model ?? '—'}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-gray-500">LLM temperature</dt>
            <dd className="font-mono text-right">{meta.llm_model_info?.temperature ?? '—'}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-gray-500">prompt sys sha</dt>
            <dd className="font-mono text-right">
              {(meta.prompt_metadata?.system_template?.template_sha256 || '').slice(0, 8) || '—'}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-gray-500">prompt user sha</dt>
            <dd className="font-mono text-right">
              {(meta.prompt_metadata?.user_template?.template_sha256 || '').slice(0, 8) || '—'}
            </dd>
          </div>
        </dl>
        {root.timestamp && (
          <div className="mt-2 text-[10px] text-gray-400">generated at {root.timestamp}</div>
        )}
      </Section>
    </div>
  )
}

export default BORecipeCard
