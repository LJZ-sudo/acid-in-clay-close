import { STUDIO_FILES } from '../../../analysis/studioPaths'
import { useStageOutputLoader } from '../../../hooks/useStageOutputLoader'
import { StudioEmpty } from '../StudioEmpty'

/**
 * Renders primary_validation_track.json body (shared by Candidate Space tab and Validation Loop page).
 */
export function PrimaryValidationTrackContent({ d }) {
  const sub = d.validation_subfamily ?? d.subfamily ?? d.branch_name
  const whyBranch = d.why_this_branch ?? d.selection_reason ?? d.rationale
  const diff = d.generic_best_exemplar_vs_primary ?? d.exemplar_gap ?? d.primary_vs_generic
  const mechanismProbe =
    d.mechanism_discrimination_value ?? d.mechanism_probe_value ?? d.route_discrimination ?? d.discrimination_value

  return (
    <div className="space-y-2 text-sm">
      {sub && (
        <p>
          <span className="font-semibold">Branch name:</span>{' '}
          {typeof sub === 'string' ? sub : JSON.stringify(sub)}
        </p>
      )}
      {whyBranch && (
        <p className="text-xs text-gray-700">
          <span className="font-semibold">Reason:</span>{' '}
          {typeof whyBranch === 'string' ? whyBranch : JSON.stringify(whyBranch)}
        </p>
      )}
      {mechanismProbe != null && (
        <p className="text-xs text-gray-700">
          <span className="font-semibold">Mechanism discrimination / route role signal:</span>{' '}
          {typeof mechanismProbe === 'object' ? JSON.stringify(mechanismProbe) : String(mechanismProbe)}
        </p>
      )}
      {diff && (
        <div className="text-xs border-l-4 border-amber-300 pl-3 py-1 bg-amber-50/50 rounded-r">
          <span className="font-semibold">Generic best exemplar vs primary validation subfamily:</span>{' '}
          {typeof diff === 'string' ? diff : JSON.stringify(diff)}
        </div>
      )}
      {!sub && !whyBranch && !diff && mechanismProbe == null && (
        <pre className="text-xs whitespace-pre-wrap max-h-56 overflow-auto">{JSON.stringify(d, null, 2)}</pre>
      )}
      <p className="text-[11px] text-gray-500 not-italic">
        This is the primary validation thread for the current study design. It is not asserted as the only scientifically
        valid route in the broader candidate space.
      </p>
    </div>
  )
}

/** Tab wrapper: load file + empty state */
export function PrimaryValidationTrackSection() {
  const { loading, result } = useStageOutputLoader(STUDIO_FILES.primaryValidationTrack, { kindHint: 'json' })
  if (loading) return <p className="text-xs text-gray-500">Loading…</p>
  if (result?.status !== 'ok') {
    return <StudioEmpty title="primary_validation_track.json unavailable" detail={result?.message} />
  }
  return <PrimaryValidationTrackContent d={result.data} />
}
