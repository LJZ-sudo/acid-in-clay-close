export const PAPER_OUTLINE = [
  {
    id: 'fig1_architecture_bridge',
    title: '1) Fig.1 Multi-Agent Architecture & Digital-Physical Bridge',
    short_desc: 'Architecture and Digital<->Physical command/data bridge with audit trace.',
    relevant_agents: ['Orchestrator', 'ControllerAdapter', 'Evidence Package Agent'],
    required_event_types: ['RUN_CREATED', 'SET_T', 'RAW_SAVED', 'EVIDENCE_PACKAGE_SAVED'],
    required_evidence_fields: [
      'decision_trace.orchestrator_decision',
      'raw_artifacts.raw_spectrum_path',
      'provenance.code_version',
    ],
    recommended_views: ['agent_cards', 'architecture_bridge', 'swimlane_timeline'],
  },
  {
    id: 'fig2_acquisition_qc',
    title: '2) Fig.2 Autonomous EIS Acquisition & QC Gate',
    short_desc: 'Acquisition process, Nyquist updates, Rb fitting and QC gate decisions.',
    relevant_agents: ['Acquisition Agent', 'Online Analysis', 'QC Agent', 'Planner', 'Critic'],
    required_event_types: ['WAIT_STABLE', 'EIS_RUN', 'RAW_SAVED', 'Rb_FIT', 'QC_GRADE'],
    required_evidence_fields: [
      'derived_results.rb_value',
      'derived_results.rb_method',
      'derived_results.r2',
      'derived_results.qc_grade',
    ],
    recommended_views: ['nyquist', 'qc_panel', 'deliberation_trace', 'timeline_focus_qc'],
  },
  {
    id: 'fig3_arrhenius_changepoint',
    title: '3) Fig.3 Arrhenius Segmentation & Change-Point Detection',
    short_desc: 'Segmented Arrhenius fitting and breakpoint evidence with statistical records.',
    relevant_agents: ['Change-Point Monitor', 'Online Analysis', 'Evidence Package Agent'],
    required_event_types: ['BREAKPOINT_FOUND', 'ARRHENIUS_SEGMENT_DONE'],
    required_evidence_fields: [
      'inference_results.breakpoint_candidates',
      'inference_results.selected_breakpoints',
      'inference_results.aic_bic_records',
      'inference_results.f_test_records',
      'inference_results.segment_params',
    ],
    recommended_views: ['arrhenius', 'breakpoint_list', 'evidence_stats'],
  },
  {
    id: 'fig4_adaptive_sampling',
    title: '4) Fig.4 Closed-Loop Adaptive Sampling Advantage',
    short_desc: 'Adaptive densify/backtrack strategy and cost-benefit comparison vs baseline.',
    relevant_agents: ['Planner', 'Critic', 'Orchestrator', 'ControllerAdapter'],
    required_event_types: ['PHASE_SCORE', 'TRIGGER_FINE_SCAN', 'BACKTRACK'],
    required_evidence_fields: [
      'derived_results.phase_jump_score',
      'decision_trace.planner_proposal',
      'decision_trace.critic_comment',
      'decision_trace.orchestrator_decision',
    ],
    recommended_views: ['trajectory', 'phase_score', 'adaptive_decisions', 'agent_vs_baseline'],
  },
  {
    id: 'evidence_auditability',
    title: '5) Evidence & Full Auditability (Evidence Package + JSONL log + Replay)',
    short_desc: 'Complete evidence chain, hash traceability and replay reproducibility.',
    relevant_agents: ['Evidence Package Agent', 'Report Agent', 'Orchestrator'],
    required_event_types: ['EVIDENCE_PACKAGE_SAVED', 'RUN_FINISHED'],
    required_evidence_fields: [
      'schema_version',
      'evidence_id',
      'raw_artifacts.raw_spectrum_sha256',
      'provenance.code_version',
      'provenance.bundle_hash_manifest_path',
    ],
    recommended_views: ['swimlane_timeline', 'evidence_drawer', 'downloads', 'repro_command'],
  },
  {
    id: 'prediction_next',
    title: '6) Prediction & Next Experiments (optional; minimized)',
    short_desc: 'Evidence-backed recommendation and next experiment planning.',
    relevant_agents: ['Report Agent', 'Planner', 'Critic'],
    required_event_types: [],
    required_evidence_fields: [
      'inference_results.segment_params',
      'decision_trace.orchestrator_decision',
    ],
    recommended_views: ['recommendation_card'],
  },
]

export default PAPER_OUTLINE

