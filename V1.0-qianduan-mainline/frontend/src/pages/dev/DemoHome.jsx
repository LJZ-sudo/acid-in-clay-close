import { Link } from 'react-router-dom'
import { useAgentStore } from '../../stores'
import {
  MechanismCoreWalkthroughSummary,
  PrimaryDirectionWalkthroughSummary,
  PrimaryValidationWalkthroughSummary,
  ValidationRecipeWalkthroughSummary,
} from '../../components/demo/WalkthroughFileSummaries'

function CtaLink({ to, children }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center px-3 py-1.5 rounded-lg text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
    >
      {children}
    </Link>
  )
}

function SectionCard({ title, subtitle, children, footer }) {
  return (
    <section className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
        {subtitle ? <p className="text-sm text-gray-500 mt-1 leading-relaxed">{subtitle}</p> : null}
      </div>
      {children}
      {footer ? <div className="pt-2 flex flex-wrap gap-2">{footer}</div> : null}
    </section>
  )
}

function DemoHome() {
  const runId = useAgentStore((s) => s.runId)

  return (
    <div className="space-y-6 pb-10 max-w-4xl">
      <header className="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-900 to-indigo-950 text-white p-6 space-y-3">
        <h1 className="text-2xl font-bold tracking-tight">Guided Walkthrough</h1>
        <p className="text-sm text-indigo-100/95 leading-relaxed max-w-2xl">
          Understand the current CLOSE system from the physical measurement loop to the validation loop.
        </p>
        <p className="text-xs text-indigo-200/90 border-t border-white/10 pt-3">
          This page is a guided overview -not live control, not the primary evidence workspace, and not a discovery autoplay.
        </p>
      </header>

      <div className="rounded-xl border-2 border-amber-200 bg-amber-50/90 p-4 text-sm text-amber-950 space-y-2">
        <p className="font-semibold">Scope</p>
        <ul className="list-disc pl-5 text-xs space-y-1 leading-relaxed">
          <li>This is a guided overview, not the live experiment page.</li>
          <li>This is not the primary place for interacting with evidence -use Analysis for file-backed studio blocks.</li>
          <li>
            Real working routes:{' '}
            <code className="text-[10px] bg-white/80 px-1 rounded">/</code>,{' '}
            <code className="text-[10px] bg-white/80 px-1 rounded">/experiment</code>,{' '}
            <code className="text-[10px] bg-white/80 px-1 rounded">/analysis</code>,{' '}
            <code className="text-[10px] bg-white/80 px-1 rounded">/validation</code>,{' '}
            <code className="text-[10px] bg-white/80 px-1 rounded">/agent</code>, and{' '}
            <code className="text-[10px] bg-white/80 px-1 rounded">/runs/:id</code> for run-centric replay.
          </li>
        </ul>
      </div>

      <SectionCard
        title="1 -Physical inner loop"
        subtitle="Hardware automation, phase-related signals from measurements, and agent runtime decisions during an active run."
        footer={
          <>
            <CtaLink to="/">Open Command Center</CtaLink>
            <CtaLink to="/experiment">Open Runtime Cockpit</CtaLink>
          </>
        }
      >
        <p className="text-sm text-gray-700 leading-relaxed">
          The runtime cockpit ties physical control (temperature, EIS) to agent decisions. The command center summarizes
          system-level status. Neither is replaced by this walkthrough.
        </p>
      </SectionCard>

      <SectionCard
        title="2 -Evidence to mechanism"
        subtitle="Current narrative: evidence digest â†?mechanism core â†?transferable design conditions (file-backed where indexed)."
        footer={<CtaLink to="/analysis">Open Analysis</CtaLink>}
      >
        <p className="text-sm text-gray-700 leading-relaxed">
          Analysis is organized as Evidence &amp; Discovery Studio tabs (Evidence, Mechanism, Candidate Space, Validation).
          Below is a tiny snapshot from indexed outputs when available.
        </p>
        <MechanismCoreWalkthroughSummary />
      </SectionCard>

      <SectionCard
        title="3 -Candidate space"
        subtitle="Broader host-family space and the primary validation branch focus -the latter is not the only scientifically valid family."
        footer={<CtaLink to="/analysis?tab=candidates">Open Analysis â†?Candidate Space</CtaLink>}
      >
        <p className="text-sm text-gray-700 leading-relaxed">
          The studio separates broad candidates from the branch chosen for primary validation. A starch-rich branch may be
          primary for validation without invalidating other routes in the wider pool.
        </p>
        <div className="space-y-2">
          <PrimaryDirectionWalkthroughSummary />
          <PrimaryValidationWalkthroughSummary />
        </div>
      </SectionCard>

      <SectionCard
        title="4 -Validation path"
        subtitle="Selected validation branch context, human-selected instance (when saved), and in-branch recipe -not a global AI winner."
        footer={<CtaLink to="/validation">Open Validation Loop</CtaLink>}
      >
        <p className="text-sm text-gray-700 leading-relaxed">
          Routes are generated by the AI-assisted pipeline; the concrete validation instance is a researcher boundary when
          recorded; recipes are completed within the selected branch. Use the Validation Loop page for the full structured
          view.
        </p>
        <ValidationRecipeWalkthroughSummary />
      </SectionCard>

      <SectionCard
        title="5 -Agent OS and run traceability"
        subtitle="Decision transparency vs run-centric audit trail."
        footer={<CtaLink to="/agent">Open Agent OS</CtaLink>}
      >
        <p className="text-sm text-gray-700 leading-relaxed">
          Agent OS surfaces plannerâ€“criticâ€“orchestrator status, decisions, and human-gate context. Run Replay loads a
          specific run id for read-only traceability (no list page yet).
        </p>
        <div className="flex flex-col gap-2">
          {runId ? (
            <CtaLink to={`/runs/${encodeURIComponent(String(runId))}`}>Open Run Replay (current run id)</CtaLink>
          ) : (
            <p className="text-xs text-gray-500 border border-dashed rounded-lg px-3 py-2 bg-gray-50">
              Run Replay is available at <code className="text-[10px]">/runs/:id</code>. No run id is set in this browser
              session -open Agent OS after starting a run, or paste a known id in the address bar.
            </p>
          )}
        </div>
      </SectionCard>

      <p className="text-[11px] text-gray-400 px-1">
        Archived UI (legacy paper-style team replay, not the current product narrative):{' '}
        <Link to="/demo/agent-team" className="text-indigo-600 hover:underline">
          /demo/agent-team
        </Link>
      </p>
    </div>
  )
}

export default DemoHome
