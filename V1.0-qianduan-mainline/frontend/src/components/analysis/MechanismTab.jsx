import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { STUDIO_FILES } from '../../analysis/studioPaths'
import { useStageOutputLoader } from '../../hooks/useStageOutputLoader'
import { StudioEmpty, StudioSection } from './StudioEmpty'

const STAGE3_UNAVAILABLE = 'Stage 3 mechanism outputs not available or not indexed under output/stage3_mechanism/.'

function ZoneCard({ title, data }) {
  if (data == null || (typeof data === 'object' && !Object.keys(data).length)) return null
  return (
    <div className="rounded-lg border border-gray-200 p-3 bg-gray-50/80">
      <h4 className="text-xs font-semibold text-gray-800 mb-2">{title}</h4>
      {typeof data === 'string' || typeof data === 'number' ? (
        <p className="text-sm text-gray-700">{String(data)}</p>
      ) : (
        <pre className="text-[11px] whitespace-pre-wrap font-sans text-gray-700 max-h-48 overflow-auto">{JSON.stringify(data, null, 2)}</pre>
      )}
    </div>
  )
}

function MechanismCoreSummary({ data }) {
  if (!data || typeof data !== 'object') return null
  const name = data.mechanism_name ?? data.name ?? data.title ?? 'Working mechanism'
  const warm = data.warm_zone ?? data.warm ?? data.zones?.warm
  const transition = data.transition_zone ?? data.transition ?? data.zones?.transition
  const deep = data.deep_cold_zone ?? data.deep_cold ?? data.zones?.deep_cold
  const eis = data.eis_manifestation ?? data.eis ?? data.EIS_manifestation
  const arr = data.arrhenius_manifestation ?? data.arrhenius ?? data.Arrhenius_manifestation
  const picture = data.physical_picture ?? data.one_paragraph_physical_picture ?? data.narrative_summary ?? data.summary

  return (
    <div className="space-y-3">
      <h4 className="text-base font-semibold text-gray-900">{name}</h4>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
        <ZoneCard title="Warm region" data={warm} />
        <ZoneCard title="Transition region" data={transition} />
        <ZoneCard title="Deep-cold region" data={deep} />
      </div>
      {(eis || arr) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <ZoneCard title="EIS manifestation" data={eis} />
          <ZoneCard title="Arrhenius manifestation" data={arr} />
        </div>
      )}
      {picture && (
        <div className="rounded-lg border border-indigo-100 bg-indigo-50/40 p-3">
          <h4 className="text-xs font-semibold text-indigo-900 mb-1">Physical picture (summary)</h4>
          <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{typeof picture === 'string' ? picture : JSON.stringify(picture, null, 2)}</p>
        </div>
      )}
    </div>
  )
}

function DesignRulesBlock({ data }) {
  if (!data) return <StudioEmpty title="Design rules unavailable" detail={STAGE3_UNAVAILABLE} />

  const rules = Array.isArray(data.rules)
    ? data.rules
    : Array.isArray(data.transferable_design_rules)
      ? data.transferable_design_rules
      : Array.isArray(data)
        ? data
        : data.items
          ? data.items
          : []

  if (!rules.length) {
    return <pre className="text-xs bg-gray-50 p-2 rounded max-h-60 overflow-auto whitespace-pre-wrap">{JSON.stringify(data, null, 2)}</pre>
  }

  return (
    <ul className="space-y-2">
      {rules.map((r, i) => {
        const principle = r.principle ?? r.principle_summary ?? r.title ?? r.rule_name ?? `Rule ${i + 1}`
        const cond = r.conditions ?? r.design_conditions ?? r.when ?? r.condition
        const summary = r.summary ?? r.rationale ?? r.description
        return (
          <li key={i} className="rounded-lg border border-gray-200 p-3 text-sm bg-white">
            <p className="font-semibold text-gray-900">{principle}</p>
            {cond && <p className="text-xs text-gray-600 mt-1"><span className="font-medium">Conditions:</span> {typeof cond === 'string' ? cond : JSON.stringify(cond)}</p>}
            {summary && <p className="text-xs text-gray-600 mt-1">{typeof summary === 'string' ? summary : JSON.stringify(summary)}</p>}
          </li>
        )
      })}
    </ul>
  )
}

function CollapsibleMarkdown({ title, loading, result }) {
  const [open, setOpen] = useState(false)
  if (loading) return <p className="text-xs text-gray-500">Loading {title}…</p>
  if (!result || result.status !== 'ok') {
    return (
      <p className="text-xs text-gray-500">
        {title} not available{result?.message ? `: ${result.message}` : '.'}
      </p>
    )
  }
  const raw = result.markdown ?? result.text ?? ''
  const md = typeof raw === 'string' ? raw : raw != null ? JSON.stringify(raw, null, 2) : ''
  return (
    <div className="border rounded-lg">
      <button type="button" className="w-full text-left px-3 py-2 text-sm font-medium bg-gray-50 hover:bg-gray-100 flex justify-between" onClick={() => setOpen(!open)}>
        {title}
        <span>{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="prose prose-sm max-w-none p-3 border-t max-h-[480px] overflow-auto">
          <ReactMarkdown>{md}</ReactMarkdown>
        </div>
      )}
    </div>
  )
}

export function MechanismTab() {
  const core = useStageOutputLoader(STUDIO_FILES.mechanismCore, { kindHint: 'json' })
  const rules = useStageOutputLoader(STUDIO_FILES.transferableDesignRules, { kindHint: 'json' })
  const reportV5 = useStageOutputLoader(STUDIO_FILES.familyMechanismReportV5, { kindHint: 'markdown' })
  const appendix = useStageOutputLoader(STUDIO_FILES.familyMechanismAppendix, { kindHint: 'markdown' })

  return (
    <div className="space-y-6">
      <StudioSection title="Working mechanism" subtitle="Structured summary from mechanism_core.json (before long-form reports)">
        {core.loading ? (
          <p className="text-xs text-gray-500">Loading mechanism core…</p>
        ) : core.result?.status === 'ok' && core.result.data ? (
          <MechanismCoreSummary data={core.result.data} />
        ) : (
          <StudioEmpty title="Mechanism core unavailable" detail={core.result?.message || STAGE3_UNAVAILABLE} />
        )}
      </StudioSection>

      <StudioSection title="Design rules / conditions" subtitle="transferable_design_rules.json">
        {rules.loading ? <p className="text-xs text-gray-500">Loading…</p> : <DesignRulesBlock data={rules.result?.status === 'ok' ? rules.result.data : null} />}
      </StudioSection>

      <StudioSection title="Mechanism report & appendix" subtitle="Optional long markdown; collapsed by default">
        <div className="space-y-2">
          <CollapsibleMarkdown title="family_mechanism_report_v5.md" loading={reportV5.loading} result={reportV5.result} />
          <CollapsibleMarkdown title="family_mechanism_appendix_simple.md" loading={appendix.loading} result={appendix.result} />
        </div>
      </StudioSection>
    </div>
  )
}
