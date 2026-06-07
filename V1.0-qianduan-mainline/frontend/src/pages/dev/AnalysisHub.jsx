import { useSearchParams } from 'react-router-dom'
import { EvidenceTab } from '../../components/analysis/EvidenceTab'
import { MechanismTab } from '../../components/analysis/MechanismTab'
import { CandidateSpaceTab } from '../../components/analysis/CandidateSpaceTab'
import { ValidationTab } from '../../components/analysis/ValidationTab'

const TABS = [
  { id: 'evidence', label: 'Evidence' },
  { id: 'mechanism', label: 'Mechanism' },
  { id: 'candidates', label: 'Candidate Space' },
  { id: 'validation', label: 'Validation' },
]

/** Map legacy ?tab= values to new studio tabs */
function normalizeTab(raw) {
  if (!raw) return 'evidence'
  if (raw === 'stage1') return 'evidence'
  if (raw === 'stage2') return 'evidence'
  if (raw === 'stage3') return 'mechanism'
  if (TABS.some((t) => t.id === raw)) return raw
  return 'evidence'
}

function AnalysisHub() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = normalizeTab(searchParams.get('tab'))

  const setTab = (id) => setSearchParams({ tab: id })

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-amber-200 bg-amber-50 text-amber-950 px-4 py-3 text-sm leading-relaxed" role="status">
        <strong className="font-semibold">Note:</strong>{' '}
        Some sections are file-backed and may be unavailable until Stage 2/3 outputs are indexed under <code className="text-xs bg-amber-100/80 px-1 rounded">output/</code>.
        Each block fails independently so the rest of the studio stays usable.
      </div>

      <div className="bg-white rounded-xl border p-4">
        <h1 className="text-xl font-bold text-gray-900">Evidence &amp; Discovery Studio</h1>
        <p className="text-sm text-gray-600 mt-2 leading-relaxed">
          This page traces the path from <strong>evidence</strong> to <strong>mechanism</strong>, <strong>candidate space</strong>, and{' '}
          <strong>validation</strong>, aligned with current Stage 2/3 file outputs and experiment reports.
        </p>
      </div>

      <div className="flex flex-wrap gap-1 bg-gray-100 rounded-lg p-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setTab(tab.id)}
            className={`flex-1 min-w-[120px] px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.id ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="min-h-[400px] pb-8">
        {activeTab === 'evidence' && <EvidenceTab />}
        {activeTab === 'mechanism' && <MechanismTab />}
        {activeTab === 'candidates' && <CandidateSpaceTab />}
        {activeTab === 'validation' && <ValidationTab />}
      </div>
    </div>
  )
}

export default AnalysisHub
