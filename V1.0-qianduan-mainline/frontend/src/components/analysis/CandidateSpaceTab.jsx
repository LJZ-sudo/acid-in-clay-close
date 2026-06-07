import { Link } from 'react-router-dom'
import { STUDIO_FILES } from '../../analysis/studioPaths'
import { useStageOutputLoader } from '../../hooks/useStageOutputLoader'
import { StudioEmpty, StudioSection } from './StudioEmpty'
import { PrimaryValidationTrackSection } from './validationLoop/PrimaryValidationTrackSection'

const STAGE3_UNAVAILABLE = 'Stage 3 candidate-space outputs not indexed. Files are expected under output/stage3_mechanism/.'

function HostFamiliesBlock() {
  const { loading, result } = useStageOutputLoader(STUDIO_FILES.discoveredHostFamilies, { kindHint: 'json' })
  if (loading) return <p className="text-xs text-gray-500">Loading…</p>
  if (result?.status !== 'ok') {
    return <StudioEmpty title="discovered_host_families.json unavailable" detail={result?.message || STAGE3_UNAVAILABLE} />
  }
  const d = result.data
  const list = Array.isArray(d?.families) ? d.families : Array.isArray(d) ? d : d?.host_families ?? []
  if (!list.length) {
    return <pre className="text-xs bg-gray-50 p-2 rounded overflow-auto max-h-48 whitespace-pre-wrap">{JSON.stringify(d, null, 2)}</pre>
  }
  return (
    <ul className="space-y-2">
      {list.map((f, i) => (
        <li key={i} className="border rounded-lg p-3 text-sm">
          <p className="font-semibold text-gray-900">{f.family_name ?? f.name ?? f.id ?? `Family ${i + 1}`}</p>
          <p className="text-xs text-gray-600 mt-1">
            <span className="font-medium">Anti-arrest score:</span>{' '}
            {f.anti_arrest_score ?? f.anti_arrest ?? f.score ?? '—'}
          </p>
          {(f.rationale || f.short_rationale || f.notes) && (
            <p className="text-xs text-gray-600 mt-1">{f.rationale || f.short_rationale || f.notes}</p>
          )}
        </li>
      ))}
    </ul>
  )
}

function PrimaryDirectionBlock() {
  const { loading, result } = useStageOutputLoader(STUDIO_FILES.primaryMaterialDirection, { kindHint: 'json' })
  if (loading) return <p className="text-xs text-gray-500">Loading…</p>
  if (result?.status !== 'ok') {
    return <StudioEmpty title="primary_material_direction.json unavailable" detail={result?.message} />
  }
  const d = result.data
  const name = d.direction_name ?? d.name ?? d.primary_direction ?? d.title ?? 'Primary direction'
  const why = d.why_this_direction ?? d.rationale ?? d.why
  const notStarch = d.why_not_starch_only ?? d.why_this_is_not_starch_only ?? d.not_starch_only_reason

  return (
    <div className="rounded-lg border border-violet-100 bg-violet-50/30 p-4 space-y-2 text-sm">
      <h4 className="font-semibold text-gray-900">{name}</h4>
      {why && <p className="text-gray-700"><span className="font-medium">Why this direction:</span> {typeof why === 'string' ? why : JSON.stringify(why)}</p>}
      {notStarch && (
        <p className="text-xs text-violet-900 bg-violet-100/50 rounded p-2">
          <span className="font-semibold">Broader space ≠ starch-only:</span>{' '}
          {typeof notStarch === 'string' ? notStarch : JSON.stringify(notStarch)}
        </p>
      )}
      {!why && !notStarch && (
        <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(d, null, 2)}</pre>
      )}
    </div>
  )
}

function Top10Block() {
  const top = useStageOutputLoader(STUDIO_FILES.researchPriorityTop10, { kindHint: 'json' })
  const stab = useStageOutputLoader(STUDIO_FILES.researchPriorityRankStability, { kindHint: 'json' })

  if (top.loading) return <p className="text-xs text-gray-500">Loading candidate matrix…</p>
  if (top.result?.status !== 'ok') {
    return <StudioEmpty title="research_priority_top10_candidates.json unavailable" detail={top.result?.message} />
  }

  const d = top.result.data
  const rows = Array.isArray(d?.candidates)
    ? d.candidates
    : Array.isArray(d?.top_10)
      ? d.top_10
      : Array.isArray(d)
        ? d
        : d?.ranked_candidates ?? []

  const stabSummary = stab.result?.status === 'ok' ? stab.result.data : null
  const stabilityText = stabSummary
    ? (stabSummary.summary ?? stabSummary.stability_summary ?? stabSummary.notes ?? JSON.stringify(stabSummary).slice(0, 400))
    : null

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-600">
        Research prioritization snapshot — not a performance leaderboard; ranks reflect the current scoring manifest and evidence state.
      </p>
      {stab.result?.status !== 'ok' && !stab.loading && (
        <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-100 rounded px-2 py-1">Rank stability file unavailable.</p>
      )}
      {stabilityText && (
        <p className="text-xs text-gray-700 bg-gray-50 border rounded p-2"><span className="font-semibold">Stability summary:</span> {typeof stabilityText === 'string' ? stabilityText : JSON.stringify(stabilityText)}</p>
      )}
      <div className="overflow-auto max-h-[400px] border rounded-lg">
        <table className="w-full text-xs">
          <thead className="bg-gray-100 sticky top-0">
            <tr>
              <th className="text-left px-2 py-2">Rank</th>
              <th className="text-left px-2 py-2">Recipe / name</th>
              <th className="text-left px-2 py-2">Class / family</th>
              <th className="text-left px-2 py-2">Score summary</th>
              <th className="text-left px-2 py-2">Stability</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={5} className="p-3 text-gray-500">No ranked rows in file.</td></tr>
            )}
            {rows.map((row, i) => {
              const rank = row.rank ?? row.priority_rank ?? i + 1
              const recipe = row.recipe_name ?? row.name ?? row.candidate_id ?? '—'
              const cls = row.class ?? row.family ?? row.material_class ?? '—'
              const score = row.score_summary ?? row.composite_score ?? row.scores ?? row.total_score ?? '—'
              const st = row.stability ?? row.rank_stability_note ?? '—'
              return (
                <tr key={i} className="border-t">
                  <td className="px-2 py-1.5 font-mono">{rank}</td>
                  <td className="px-2 py-1.5">{recipe}</td>
                  <td className="px-2 py-1.5">{typeof cls === 'object' ? JSON.stringify(cls) : cls}</td>
                  <td className="px-2 py-1.5 max-w-[200px] truncate" title={typeof score === 'string' ? score : JSON.stringify(score)}>
                    {typeof score === 'object' ? JSON.stringify(score) : String(score)}
                  </td>
                  <td className="px-2 py-1.5 text-[10px]">{typeof st === 'object' ? JSON.stringify(st) : String(st)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function CandidateSpaceTab() {
  return (
    <div className="space-y-6">
      <StudioSection title="Broader host families" subtitle="discovered_host_families.json — candidate space is wider than a single polymer class">
        <HostFamiliesBlock />
      </StudioSection>
      <StudioSection title="Primary material direction" subtitle="primary_material_direction.json">
        <PrimaryDirectionBlock />
      </StudioSection>
      <StudioSection title="Primary validation branch" subtitle="primary_validation_track.json — validation focus vs generic exemplar">
        <PrimaryValidationTrackSection />
        <p className="text-sm mt-3">
          <Link to="/validation" className="font-medium text-indigo-600 hover:text-indigo-800 hover:underline">
            Go to Validation Loop
          </Link>
        </p>
      </StudioSection>
      <StudioSection title="Candidate matrix / top-10 appendix" subtitle="research_priority_top10_candidates.json + rank stability">
        <Top10Block />
      </StudioSection>
    </div>
  )
}
