import { STUDIO_FILES } from '../../analysis/studioPaths'
import { useStageOutputLoader } from '../../hooks/useStageOutputLoader'

function trimLine(s, max = 220) {
  if (s == null) return ''
  const t = typeof s === 'string' ? s : JSON.stringify(s)
  return t.length <= max ? t : `${t.slice(0, max)}…`
}

function SummaryShell({ label, loading, unavailable, message, children }) {
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50/80 px-3 py-2 text-xs text-gray-500" aria-live="polite">
        Loading {label}…
      </div>
    )
  }
  if (unavailable) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-3 py-2 text-xs text-gray-600">
        <span className="font-medium text-gray-700">{label}:</span> {message || 'No indexed file snapshot.'}
      </div>
    )
  }
  return <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-gray-800 space-y-1">{children}</div>
}

/** mechanism_core.json — 1–3 lines */
export function MechanismCoreWalkthroughSummary() {
  const { loading, result } = useStageOutputLoader(STUDIO_FILES.mechanismCore, { kindHint: 'json' })
  const ok = result?.status === 'ok'
  const d = ok ? result.data : null
  const lines = []
  if (d && typeof d === 'object') {
    const a = d.summary ?? d.mechanism_summary ?? d.headline ?? d.title
    if (a) lines.push(trimLine(a))
    const b = d.core_claim ?? d.primary_mechanism_claim ?? d.mechanism_thesis
    if (b) lines.push(trimLine(b))
    const c = d.design_conditions_summary ?? d.conditions_note
    if (c) lines.push(trimLine(c))
  }
  const display = lines.filter(Boolean).slice(0, 3)

  return (
    <SummaryShell
      label="mechanism_core.json"
      loading={loading}
      unavailable={!loading && !ok}
      message={result?.message}
    >
      <p className="font-semibold text-gray-900">Mechanism core (file snapshot)</p>
      {display.length > 0 ? (
        display.map((line, i) => (
          <p key={i} className="text-gray-700 leading-relaxed">
            {line}
          </p>
        ))
      ) : (
        <p className="text-gray-500">File present but no short summary fields matched; open Analysis for full context.</p>
      )}
    </SummaryShell>
  )
}

/** primary_material_direction.json */
export function PrimaryDirectionWalkthroughSummary() {
  const { loading, result } = useStageOutputLoader(STUDIO_FILES.primaryMaterialDirection, { kindHint: 'json' })
  const ok = result?.status === 'ok'
  const d = ok ? result.data : null
  const name = d?.direction_name ?? d?.name ?? d?.primary_direction ?? d?.title
  const why = d?.why_this_direction ?? d?.rationale ?? d?.why
  const notStarch = d?.why_not_starch_only ?? d?.why_this_is_not_starch_only

  return (
    <SummaryShell
      label="primary_material_direction.json"
      loading={loading}
      unavailable={!loading && !ok}
      message={result?.message}
    >
      <p className="font-semibold text-gray-900">Primary direction (file snapshot)</p>
      {name && <p>{trimLine(name)}</p>}
      {why && <p className="text-gray-700">{trimLine(why)}</p>}
      {notStarch && (
        <p className="text-violet-900 bg-violet-50 rounded px-2 py-1">
          <span className="font-semibold">Broader than starch-only:</span> {trimLine(notStarch)}
        </p>
      )}
      {!name && !why && !notStarch && ok && (
        <p className="text-gray-500">Structured data only — see Analysis → Candidate Space.</p>
      )}
    </SummaryShell>
  )
}

/** primary_validation_track.json */
export function PrimaryValidationWalkthroughSummary() {
  const { loading, result } = useStageOutputLoader(STUDIO_FILES.primaryValidationTrack, { kindHint: 'json' })
  const ok = result?.status === 'ok'
  const d = ok ? result.data : null
  const sub = d?.validation_subfamily ?? d?.subfamily ?? d?.branch_name
  const why = d?.why_this_branch ?? d?.selection_reason ?? d?.rationale

  return (
    <SummaryShell
      label="primary_validation_track.json"
      loading={loading}
      unavailable={!loading && !ok}
      message={result?.message}
    >
      <p className="font-semibold text-gray-900">Primary validation branch (file snapshot)</p>
      {sub && (
        <p>
          <span className="font-medium">Branch:</span> {trimLine(sub)}
        </p>
      )}
      {why && <p className="text-gray-700">{trimLine(why)}</p>}
      <p className="text-gray-600">
        A starch-rich route may be the primary validation branch; other host families can remain valid in the broader space.
      </p>
    </SummaryShell>
  )
}

/** validation_recipe_space.json */
export function ValidationRecipeWalkthroughSummary() {
  const { loading, result } = useStageOutputLoader(STUDIO_FILES.validationRecipeSpace, { kindHint: 'json' })
  const ok = result?.status === 'ok'
  const d = ok ? result.data : null
  const recipe = d?.selected_recipe ?? d?.recipe ?? d?.primary_recipe ?? d
  const rationale = d?.rationale ?? d?.selection_rationale ?? recipe?.rationale
  const title =
    (typeof recipe === 'object' && recipe !== null ? recipe.name ?? recipe.recipe_id : null) ||
    (typeof recipe === 'string' ? recipe : null)

  return (
    <SummaryShell
      label="validation_recipe_space.json"
      loading={loading}
      unavailable={!loading && !ok}
      message={result?.message}
    >
      <p className="font-semibold text-gray-900">Validation recipe (file snapshot, in-branch)</p>
      {title && (
        <p>
          <span className="font-medium">Recipe:</span> {trimLine(title)}
        </p>
      )}
      {rationale && <p className="text-gray-700">{trimLine(rationale)}</p>}
      <p className="text-gray-600">Routes are AI-generated; the instance is researcher-selected; the recipe is scoped to that branch.</p>
    </SummaryShell>
  )
}
