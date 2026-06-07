/**
 * Evidence & Discovery Studio — file paths under output/ (served via GET /api/reports/download?file=...)
 * @see docs/FRONTEND_DATA_CONTRACTS.md
 */

const S2 = 'output/stage2_statistics/mechanism_evidence'
const S3 = 'output/stage3_mechanism'

export const STUDIO_FILES = {
  sampleEvidenceCards: `${S2}/sample_evidence_cards.jsonl`,
  patternClaims: `${S2}/pattern_claims.json`,
  signatureClaims: `${S2}/signature_claims.json`,
  s8ClaimUnits: `${S2}/s8_claim_units.jsonl`,
  alignmentDistribution: `${S2}/alignment_distribution.json`,

  mechanismCore: `${S3}/mechanism_core.json`,
  transferableDesignRules: `${S3}/transferable_design_rules.json`,
  familyMechanismReportV5: `${S3}/family_mechanism_report_v5.md`,
  familyMechanismAppendix: `${S3}/family_mechanism_appendix_simple.md`,

  discoveredHostFamilies: `${S3}/discovered_host_families.json`,
  primaryMaterialDirection: `${S3}/primary_material_direction.json`,
  primaryValidationTrack: `${S3}/primary_validation_track.json`,
  researchPriorityTop10: `${S3}/research_priority_top10_candidates.json`,
  researchPriorityRankStability: `${S3}/research_priority_rank_stability.json`,

  branchSelection: `${S3}/branch_selection.json`,
  routeInstancePool: `${S3}/route_instance_pool.json`,
  researcherMaterialSelection: `${S3}/researcher_material_selection.json`,
  validationRecipeSpace: `${S3}/validation_recipe_space.json`,

  /** Canonical measured validation adjudication — see docs/STEP7_MEASURED_VALIDATION_CONTRACT.md */
  measuredValidationAdjudication: `${S3}/measured_validation_adjudication.json`,
  /** Legacy minimal trace from step4_validate_selected_candidate.py — not a full adjudication schema */
  legacySelectedCandidateValidationTrace: `${S3}/selected_candidate_validation_trace.json`,
}
