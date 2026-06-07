import { StudioSection } from '../../components/analysis/StudioEmpty'
import { MeasuredValidationSection } from '../../components/analysis/validationLoop/MeasuredValidationSection'
import {
  ResearcherSelectionBlock,
  RoutePoolBlock,
  ValidationLoopBoundaryBanner,
  ValidationLoopBranchSections,
  ValidationRecipeBlock,
} from '../../components/analysis/validationLoop/ValidationLoopSections'

function ValidationLoopPage() {
  return (
    <div className="space-y-6 pb-10">
      <header className="bg-white rounded-xl border border-gray-200 p-5 space-y-2">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Validation Loop</h1>
        <p className="text-sm text-gray-600 max-w-3xl leading-relaxed">
          Trace the path from AI-generated candidate space to human-selected validation instance and measured validation.
        </p>
        <p className="text-xs text-gray-500">
          File-backed via <code className="text-[10px] bg-gray-100 px-1 rounded">{'GET /api/reports/download?file=...'}</code>. Each
          block fails independently — missing Stage 3 outputs do not white-screen the page.
        </p>
      </header>

      <ValidationLoopBoundaryBanner />

      <ValidationLoopBranchSections />

      <StudioSection
        title="C. Selected Instance / Human Boundary"
        subtitle="route_instance_pool.json + researcher_material_selection.json"
      >
        <p className="text-xs text-gray-600 mb-3">
          The pool is AI-generated; the highlighted instance file records the researcher boundary when present.
        </p>
        <div className="space-y-4">
          <div>
            <h4 className="text-xs font-semibold text-gray-800 mb-2">AI-generated route instance pool</h4>
            <RoutePoolBlock />
          </div>
          <div>
            <h4 className="text-xs font-semibold text-gray-800 mb-2">Researcher selection</h4>
            <ResearcherSelectionBlock />
          </div>
        </div>
      </StudioSection>

      <StudioSection title="D. Validation Recipe" subtitle="validation_recipe_space.json (+ optional stability / top-10 context)">
        <ValidationRecipeBlock />
      </StudioSection>

      <MeasuredValidationSection />
    </div>
  )
}

export default ValidationLoopPage
