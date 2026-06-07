import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import runsAuditApi from '../../api/runsAudit'
import RunEventList from '../../components/runReplay/RunEventList'
import { loadRunReplay } from '../../utils/runReplayLoader'

function EmptyState({ title, body }) {
  return (
    <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-8 text-center max-w-lg mx-auto">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      <p className="text-sm text-gray-600 mt-2 leading-relaxed">{body}</p>
    </div>
  )
}

function highlightPayload(payload) {
  if (!payload || typeof payload !== 'object') return null
  const keys = ['action', 'phase', 'measurement', 'evidence_id', 'evidence_ref', 'evidence_refs', 'step_idx', 'sample_id']
  const priority = {}
  const rest = { ...payload }
  for (const k of keys) {
    if (k in rest) {
      priority[k] = rest[k]
      delete rest[k]
    }
  }
  return { priority, rest }
}

function SelectedEventDetail({ event }) {
  if (!event) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
        Select an event from the timeline to inspect its payload.
      </div>
    )
  }

  const { priority } = highlightPayload(event.payload) || { priority: {}, rest: {} }

  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      <div className="bg-gray-100 px-3 py-2 text-xs font-semibold text-gray-700">Selected event detail</div>
      <div className="p-3 space-y-3 text-xs">
        <div className="grid grid-cols-2 gap-2">
          <div><span className="text-gray-500">Type:</span> <span className="font-mono">{event.type || event.event_type || '-'}</span></div>
          <div><span className="text-gray-500">Seq:</span> <span className="font-mono">{event.seq ?? '-'}</span></div>
          <div className="col-span-2"><span className="text-gray-500">Timestamp:</span> <span className="font-mono">{event.timestamp || event.ts || '-'}</span></div>
        </div>
        {Object.keys(priority).length > 0 && (
          <div>
            <div className="font-semibold text-gray-800 mb-1">Highlighted fields</div>
            <pre className="bg-amber-50 border border-amber-100 rounded p-2 overflow-auto max-h-40 whitespace-pre-wrap font-mono text-[11px]">
              {JSON.stringify(priority, null, 2)}
            </pre>
          </div>
        )}
        <div>
          <div className="font-semibold text-gray-800 mb-1">Full payload</div>
          <pre className="bg-gray-900 text-gray-100 rounded p-2 overflow-auto max-h-64 whitespace-pre-wrap font-mono text-[11px]">
            {JSON.stringify(event.payload ?? {}, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  )
}

function EvidenceSection({ evidenceList, indexError }) {
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadErr, setLoadErr] = useState(null)

  const loadDetail = useCallback(async (id) => {
    if (!id) return
    setSelectedId(id)
    setLoading(true)
    setLoadErr(null)
    setDetail(null)
    try {
      const res = await runsAuditApi.getEvidence(id)
      setDetail(res?.data ?? res)
    } catch (e) {
      setLoadErr(e.response?.data?.detail || e.message || 'Failed to load evidence.')
    } finally {
      setLoading(false)
    }
  }, [])

  const items = Array.isArray(evidenceList) ? evidenceList : []

  if (indexError) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
        {indexError} No evidence bundle could be indexed for this run.
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
        No evidence bundle available for this run (empty evidence directory or index).
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      <div className="bg-gray-100 px-3 py-2 text-xs font-semibold text-gray-700">Evidence</div>
      <div className="p-3 grid grid-cols-1 md:grid-cols-2 gap-3">
        <ul className="space-y-1 max-h-48 overflow-y-auto text-xs border rounded-md p-2 bg-white">
          {items.map((it) => {
            const id = it.id ?? it.evidence_id ?? it.filename
            const label = it.filename || id
            return (
              <li key={String(id)}>
                <button
                  type="button"
                  onClick={() => loadDetail(id)}
                  className={`w-full text-left px-2 py-1.5 rounded font-mono truncate ${
                    selectedId === id ? 'bg-blue-100 text-blue-900' : 'hover:bg-gray-100'
                  }`}
                  title={label}
                >
                  {label}
                </button>
              </li>
            )
          })}
        </ul>
        <div className="min-h-[120px] text-xs border rounded-md p-2 bg-gray-50 overflow-auto">
          {loading && <p className="text-gray-500">Loading evidence...</p>}
          {loadErr && <p className="text-red-600">{loadErr}</p>}
          {!loading && !loadErr && detail && (
            <pre className="whitespace-pre-wrap font-mono text-[11px] text-gray-800">{JSON.stringify(detail, null, 2)}</pre>
          )}
          {!loading && !loadErr && !detail && selectedId == null && (
            <p className="text-gray-500">Click an evidence file for a JSON summary.</p>
          )}
        </div>
      </div>
    </div>
  )
}

function RunReplay() {
  const { id: routeId } = useParams()
  const runId = routeId != null ? decodeURIComponent(routeId) : ''

  const [loading, setLoading] = useState(true)
  const [bundle, setBundle] = useState(null)
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [selectedSeq, setSelectedSeq] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setSelectedEvent(null)
    setSelectedSeq(null)
    loadRunReplay(runId).then((b) => {
      if (!cancelled) {
        setBundle(b)
        setLoading(false)
      }
    })
    return () => {
      cancelled = true
    }
  }, [runId])

  const onSelectEvent = useCallback((raw, seq) => {
    setSelectedEvent(raw)
    setSelectedSeq(seq)
  }, [])

  const summary = useMemo(() => {
    if (!bundle?.ok || !bundle.manifest) return null
    const m = bundle.manifest
    const fromEvents = Array.isArray(bundle.events)
      ? bundle.events.find((e) => e?.payload?.sample_id)?.payload?.sample_id
      : null
    return {
      runId: m.run_id || runId,
      sampleId: m.sample_id || m.sampleId || fromEvents || selectedEvent?.payload?.sample_id || '-',
      mode: m.mode || m.profile || '-',
      createdAt: m.created_at || m.createdAt || '-',
      status: m.status || '-',
      totalEvents: bundle.events?.length ?? 0,
    }
  }, [bundle, runId, selectedEvent])

  if (!runId.trim()) {
    return (
      <div className="space-y-4">
        <header>
          <h1 className="text-2xl font-bold text-gray-900">Run Replay</h1>
          <p className="text-sm text-gray-600 mt-1">Review one run across physical events, agent decisions, and scientific outcomes.</p>
        </header>
        <EmptyState title="Missing run id" body="Open this page from a valid /runs/{id} link with a non-empty run identifier." />
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] gap-3">
        <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
        <p className="text-sm text-gray-600">Loading run...</p>
      </div>
    )
  }

  if (!bundle?.ok) {
    return (
      <div className="space-y-4">
        <header>
          <h1 className="text-2xl font-bold text-gray-900">Run Replay</h1>
          <p className="text-sm text-gray-600 mt-1">Review one run across physical events, agent decisions, and scientific outcomes.</p>
        </header>
        <EmptyState
          title={bundle?.phase === 'manifest_404' ? 'Run unavailable' : 'Could not load run'}
          body={bundle?.message || 'Unknown error.'}
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-gray-900">Run Replay</h1>
        <p className="text-sm text-gray-600 mt-1 max-w-3xl leading-relaxed">
          Review one run across physical events, agent decisions, and scientific outcomes. This page is a{' '}
          <strong>read-only skeleton</strong> -it does not play, seek, or stream live replay.
        </p>
      </header>

      {bundle.eventsLoadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 text-red-900 text-sm px-4 py-2">
          Events endpoint failed: {bundle.eventsLoadError}. Run summary may still be shown; timeline may be empty.
        </div>
      )}

      {!bundle.eventsLoadError && bundle.events.length === 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 text-amber-900 text-sm px-4 py-2">
          This run has no recorded events yet (empty events.jsonl).
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <RunEventList events={bundle.events} selectedSeq={selectedSeq} onSelect={onSelectEvent} />

        <div className="space-y-4">
          <section className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Run summary</h2>
            {summary ? (
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <div><dt className="text-gray-500">Run id</dt><dd className="font-mono font-medium">{summary.runId}</dd></div>
                <div><dt className="text-gray-500">Sample id</dt><dd className="font-mono">{summary.sampleId}</dd></div>
                <div><dt className="text-gray-500">Mode</dt><dd>{summary.mode}</dd></div>
                <div><dt className="text-gray-500">Status</dt><dd>{summary.status}</dd></div>
                <div className="sm:col-span-2"><dt className="text-gray-500">Created at</dt><dd className="font-mono">{summary.createdAt}</dd></div>
                <div><dt className="text-gray-500">Total events</dt><dd>{summary.totalEvents}</dd></div>
              </dl>
            ) : (
              <p className="text-sm text-gray-500">No manifest fields to display.</p>
            )}
          </section>

          <SelectedEventDetail event={selectedEvent} />

          <EvidenceSection evidenceList={bundle.evidenceList} indexError={bundle.evidenceIndexError} />
        </div>
      </div>
    </div>
  )
}

export default RunReplay
