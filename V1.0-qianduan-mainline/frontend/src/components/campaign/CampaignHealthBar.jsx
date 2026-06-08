function fmt(v, digits = 3) {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  return Number(v).toFixed(digits)
}

function fmtSci(v) {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  return Number(v).toExponential(2)
}

/**
 * Compact health bar — surfaces convergence (last-5 std), best-score deltas,
 * closed-loop validity (replay vs prospective), and on-disk limitations.
 */
function CampaignHealthBar({ health }) {
  if (!health) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-4 text-xs text-gray-400">
        Loading campaign health...
      </div>
    )
  }
  const validity = health.closed_loop_validity
  const validityTone =
    validity === 'prospective_real_hardware' ? 'bg-emerald-100 text-emerald-700' :
    validity === 'retrospective_replay' ? 'bg-amber-100 text-amber-700' :
    'bg-gray-100 text-gray-700'

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
      {health.metrics_stale && (
        <div className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
          ⚠️ closed_loop_metrics.json 缓存与 history_db 不一致；以下数值已**回退到 history_db 实时计算**。
          下一次 <code>run_optimization_loop.py</code> 运行会重写缓存。
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
        <div>
          <div className="text-gray-500">trials</div>
          <div className="text-base font-semibold tabular-nums">{health.n_history_trials ?? '—'}</div>
        </div>
        <div>
          <div className="text-gray-500">closed-loop rounds</div>
          <div className="text-base font-semibold tabular-nums">{health.n_closed_loop_rounds ?? 0}</div>
        </div>
        <div>
          <div className="text-gray-500">best score (overall)</div>
          <div className="text-base font-semibold tabular-nums">
            {fmt(health.best_score_overall ?? health.best_final_score, 3)}
          </div>
        </div>
        <div>
          <div className="text-gray-500">σ_RT @ best (S/cm)</div>
          <div className="text-base font-semibold tabular-nums">{fmtSci(health.best_final_sigma_299K_S_cm)}</div>
        </div>
        <div>
          <div className="text-gray-500">best R / N</div>
          <div className="text-base font-semibold tabular-nums">
            {fmt(health.best_candidate_R, 3)} / {fmt(health.best_candidate_N, 3)}
          </div>
        </div>
        <div>
          <div className="text-gray-500">last-5 score std</div>
          <div className="text-base font-semibold tabular-nums">{fmt(health.last_5_score_std, 3)}</div>
        </div>
        <div className="ml-auto">
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${validityTone}`} title={health.human_intervention_level || ''}>
            validity: {validity ?? 'unknown'}
          </span>
        </div>
      </div>

      {health.closed_loop_meta_describes === 'single_objective_bo_history' && (
        <div className="text-[11px] text-blue-700 bg-blue-50 border border-blue-200 rounded px-2 py-1">
          ℹ️ 上方「closed-loop rounds / validity / best R-N」描述的是<strong>已记录的单目标 BO 历史</strong>
          {health.generated_at ? `（缓存生成于 ${String(health.generated_at).slice(0, 10)}）` : ''}。
          当前 MOBO + LLM 前瞻闭环的下一组推荐与留痕请见<strong>优化看板的 Provenance 面板</strong>（线 B）。
        </div>
      )}

      {Array.isArray(health.limitations) && health.limitations.length > 0 && (
        <details className="text-[11px] text-gray-600">
          <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
            limitations ({health.limitations.length})
          </summary>
          <ul className="mt-2 space-y-1 list-disc list-inside">
            {health.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

export default CampaignHealthBar
