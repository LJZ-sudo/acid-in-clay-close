import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import runV1Api from '../../api/v1Runs'

function pretty(value) {
  return JSON.stringify(value || {}, null, 2)
}

function collectArtifacts(evidence, event) {
  const rows = []
  const fromEvent = event?.payload?.artifacts
  if (Array.isArray(fromEvent)) rows.push(...fromEvent)

  const rawPath =
    evidence?.measurement_evidence?.raw_file_path ||
    evidence?.raw_artifacts?.raw_spectrum_path ||
    evidence?.eis_raw?.file_path
  if (rawPath) rows.push(rawPath)

  const figPath = evidence?.analysis_evidence?.plot_path || evidence?.artifacts?.arrhenius_png
  if (figPath) rows.push(figPath)

  const logsPath = evidence?.artifacts?.logs_jsonl_path
  if (logsPath) rows.push(logsPath)

  return Array.from(new Set(rows.filter(Boolean)))
}

function extractSummary(evidence = {}) {
  const rawSpectrumPath =
    evidence?.measurement_evidence?.raw_file_path ||
    evidence?.raw_artifacts?.raw_spectrum_path ||
    evidence?.eis_raw?.file_path ||
    null

  const rbFit = evidence?.processing?.rb_fit || evidence?.analysis_evidence || {}
  const decision = evidence?.decision || evidence?.decision_evidence || {}
  const orchestrator = decision?.orchestrator_decision || decision?.final_decision || {}

  return {
    rawSpectrumPath,
    rawSpectrumSha:
      evidence?.measurement_evidence?.sha256 ||
      evidence?.raw_artifacts?.raw_spectrum_sha256 ||
      evidence?.eis_raw?.sha256 ||
      null,
    rbMethod: rbFit?.method_selected || rbFit?.fit_method || null,
    rbValue: rbFit?.rb_ohm ?? null,
    r2: rbFit?.r2 ?? evidence?.analysis_evidence?.r2 ?? null,
    qcGrade: rbFit?.qc_grade || evidence?.analysis_evidence?.qc?.qc_grade || null,
    qcStatus: rbFit?.qc_status || evidence?.analysis_evidence?.qc?.qc_status || null,
    decisionRationale:
      orchestrator?.reason?.code ||
      orchestrator?.reason ||
      decision?.critic_review?.review?.code ||
      decision?.critic_review?.review ||
      null,
  }
}

function EvidenceDrawer({
  runId,
  open,
  evidenceId,
  selectedEvent,
  evidence,
  onClose,
  onLoaded,
}) {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function loadEvidence() {
      if (!open || !runId || !evidenceId || evidence?.evidence_id === evidenceId) return
      setLoading(true)
      setError('')

      try {
        const resp = await runV1Api.getEvidence(runId, evidenceId)
        const row = resp?.data?.evidence || resp?.data || null
        if (!active) return
        onLoaded?.(row)
      } catch {
        if (active) setError(t('errors.requestFailed'))
      } finally {
        if (active) setLoading(false)
      }
    }

    loadEvidence()

    return () => {
      active = false
    }
  }, [evidence?.evidence_id, evidenceId, onLoaded, open, runId, t])

  const artifacts = useMemo(() => collectArtifacts(evidence, selectedEvent), [evidence, selectedEvent])
  const summary = useMemo(() => extractSummary(evidence), [evidence])

  if (!open) return null

  const handleDownloadEvidence = async () => {
    if (!runId || !evidenceId) return
    try {
      const resp = await runV1Api.downloadEvidence(runId, evidenceId)
      const blob = resp?.data instanceof Blob
        ? resp.data
        : new Blob([JSON.stringify(resp?.data || {}, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${evidenceId}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      window.open(runV1Api.evidenceDownloadUrl(runId, evidenceId), '_blank', 'noopener')
    }
  }

  return (
    <div className="fixed inset-y-0 right-0 w-[440px] max-w-[95vw] bg-white border-l border-gray-200 shadow-2xl z-50 flex flex-col">
      <div className="p-3 border-b border-gray-200 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-sm">{t('workbench.evidenceDrawer')}</h3>
          <div className="text-xs text-gray-500">{evidenceId || selectedEvent?.evidence_id || '—'}</div>
        </div>
        <button className="btn-outline text-xs" type="button" onClick={onClose}>{t('common.close')}</button>
      </div>

      <div className="p-3 flex items-center gap-2 border-b border-gray-100">
        <button className="btn-outline text-xs" type="button" onClick={handleDownloadEvidence}>
          {t('workbench.exportCurrentEvidence')}
        </button>
      </div>

      <div className="flex-1 overflow-auto p-3 space-y-3 text-xs">
        {loading && <div className="text-gray-500">{t('common.loading')}</div>}
        {error && <div className="text-red-600">{error}</div>}

        <div className="border border-gray-200 rounded p-2">
          <div className="font-semibold mb-1">{t('workbench.currentEvent')}</div>
          <div>{t('common.seq')}: {selectedEvent?.seq ?? '—'}</div>
          <div>{t('common.step')}: {selectedEvent?.step_idx ?? '—'}</div>
          <div>{t('common.actor')}: {selectedEvent?.source || selectedEvent?.actor || '—'}</div>
          <div>{t('workbench.eventType')}: {selectedEvent?.type || '—'}</div>
          <details className="mt-2">
            <summary className="cursor-pointer">{t('workbench.payload')}</summary>
            <pre className="mt-1 max-h-40 overflow-auto bg-gray-900 text-gray-100 p-2 rounded">{pretty(selectedEvent?.payload)}</pre>
          </details>
        </div>

        <div className="border border-gray-200 rounded p-2">
          <div className="font-semibold mb-1">{t('workbench.evidenceSummary')}</div>
          <div>
            {t('workbench.rawSpectrumPath')}:{' '}
            {summary.rawSpectrumPath ? (
              <a className="font-mono break-all text-blue-600 hover:underline" href={summary.rawSpectrumPath} target="_blank" rel="noreferrer">
                {summary.rawSpectrumPath}
              </a>
            ) : (
              <span className="font-mono break-all">—</span>
            )}
          </div>
          <div>{t('workbench.rawSpectrumSha')}: <span className="font-mono break-all">{summary.rawSpectrumSha || '—'}</span></div>
          <div>{t('qc.fitMethod')}: <span className="font-mono">{summary.rbMethod || '—'}</span></div>
          <div>{t('qc.rbOhm')}: <span className="font-mono">{summary.rbValue ?? '—'}</span></div>
          <div>{t('qc.r2')}: <span className="font-mono">{summary.r2 ?? t('arrhenius.r2DisplayNull')}</span></div>
          <div>{t('qc.grade')}: <span className="font-mono">{summary.qcGrade || t('common.unknown')}</span></div>
          <div>{t('workbench.decisionRationale')}: <span className="font-mono break-all">{summary.decisionRationale || '—'}</span></div>
        </div>

        <div className="border border-gray-200 rounded p-2">
          <div className="font-semibold mb-1">{t('workbench.evidencePackage')}</div>
          <div>{t('workbench.evidenceIdLabel')}: {evidence?.evidence_id || evidenceId || '—'}</div>
          <div>{t('workbench.schemaVersionLabel')}: {evidence?.schema_version || selectedEvent?.payload?.schema_version || '—'}</div>
          <div>{t('workbench.codeVersionLabel')}: {evidence?.provenance?.code_version || evidence?.code_version || selectedEvent?.payload?.code_version || '—'}</div>
          <details className="mt-2">
            <summary className="cursor-pointer">{t('workbench.json')}</summary>
            <pre className="mt-1 max-h-64 overflow-auto bg-gray-900 text-gray-100 p-2 rounded">{pretty(evidence)}</pre>
          </details>
        </div>

        <div className="border border-gray-200 rounded p-2">
          <div className="font-semibold mb-1">{t('workbench.artifacts')}</div>
          {artifacts.length === 0 ? <div className="text-gray-400">{t('common.empty')}</div> : artifacts.map((path) => (
            <div key={path} className="font-mono break-all">{path}</div>
          ))}
        </div>

        <div className="border border-gray-200 rounded p-2">
          <div className="font-semibold mb-1">{t('workbench.hashes')}</div>
          <pre className="max-h-40 overflow-auto bg-gray-900 text-gray-100 p-2 rounded">{pretty(evidence?.hashes || selectedEvent?.payload?.hashes || {})}</pre>
        </div>
      </div>
    </div>
  )
}

export default EvidenceDrawer

