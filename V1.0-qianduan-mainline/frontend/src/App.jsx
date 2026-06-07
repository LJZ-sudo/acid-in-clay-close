import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, useParams } from 'react-router-dom'
import { Spin } from 'antd'
import MainLayout from './components/layout/MainLayout'
import { ENABLE_DEV_ROUTES } from './config/mainline'

function RunsLegacyRedirect() {
  const { id } = useParams()
  return <Navigate to={ENABLE_DEV_ROUTES ? `/dev/replay/${id ?? ''}` : '/monitor'} replace />
}

function DemoTeamRunRedirect() {
  const { run_id } = useParams()
  return <Navigate to={ENABLE_DEV_ROUTES ? `/dev/demo/agent-team/run/${run_id ?? ''}` : '/monitor'} replace />
}

function DevOnly({ children }) {
  return ENABLE_DEV_ROUTES ? children : <Navigate to="/" replace />
}

// 主线 6 项
const Home         = lazy(() => import('./pages/stage0/Home'))
const Control      = lazy(() => import('./pages/stage0/Control'))
const Monitor      = lazy(() => import('./pages/stage0/Monitor'))
const Analysis     = lazy(() => import('./pages/stage0/Analysis'))
const Report       = lazy(() => import('./pages/stage0/Report'))
const Optimization = lazy(() => import('./pages/stage0/Optimization'))

// 直链 — 单样品报告 deep link (供分享/anchor)
const SampleClosureCard = lazy(() => import('./pages/SampleClosureCard'))

// /dev/* 旧/开发者页
const DevLegacyOverview      = lazy(() => import('./pages/dev/LegacyOverview'))
const DevAgentWorkbench      = lazy(() => import('./pages/dev/AgentWorkbench'))
const DevAnalysisHub         = lazy(() => import('./pages/dev/AnalysisHub'))
const DevValidationLoop      = lazy(() => import('./pages/dev/ValidationLoopPage'))
const DevDemoHome            = lazy(() => import('./pages/dev/DemoHome'))
const DevRunReplay           = lazy(() => import('./pages/dev/RunReplay'))
const DevLegacyLiveExperiment = lazy(() => import('./pages/dev/LegacyLiveExperiment'))

function LoadingFallback() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 240 }}>
      <Spin size="large" />
    </div>
  )
}

function App() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          {/* 6 项主线 */}
          <Route index                element={<Home />} />
          <Route path="control"       element={<Control />} />
          <Route path="monitor"       element={<Monitor />} />
          <Route path="analysis"      element={<Analysis />} />
          <Route path="report"        element={<Report />} />
          <Route path="reports"       element={<Navigate to="/report" replace />} />
          <Route path="optimization"  element={<Optimization />} />

          {/* deep link：单样品报告 */}
          <Route path="sample/:sampleId" element={<SampleClosureCard />} />

          {/* /dev/* */}
          <Route path="dev/legacy-overview"  element={<DevOnly><DevLegacyOverview /></DevOnly>} />
          <Route path="dev/agent"            element={<DevOnly><DevAgentWorkbench /></DevOnly>} />
          <Route path="dev/analysis"         element={<DevOnly><DevAnalysisHub /></DevOnly>} />
          <Route path="dev/validation"       element={<DevOnly><DevValidationLoop /></DevOnly>} />
          <Route path="dev/demo"             element={<DevOnly><DevDemoHome /></DevOnly>} />
          <Route path="dev/replay/:id"       element={<DevOnly><DevRunReplay /></DevOnly>} />
          <Route path="dev/legacy-cockpit"   element={<DevOnly><DevLegacyLiveExperiment /></DevOnly>} />

          {/* 兼容旧 IA 重定向 */}
          <Route path="dashboard"      element={<Navigate to="/optimization" replace />} />
          <Route path="campaigns"      element={<Navigate to="/optimization" replace />} />
          <Route path="campaigns/:slug" element={<Navigate to="/optimization" replace />} />
          <Route path="lab/campaigns"  element={<Navigate to="/optimization" replace />} />
          <Route path="lab/campaigns/:slug" element={<Navigate to="/optimization" replace />} />
          <Route path="lab/samples"    element={<Navigate to="/report" replace />} />
          <Route path="lab/samples/:sampleId" element={<SampleClosureCard />} />
          <Route path="samples"        element={<Navigate to="/report" replace />} />
          <Route path="samples/:sampleId" element={<SampleClosureCard />} />
          <Route path="thought-chain"  element={<Navigate to="/monitor" replace />} />
          <Route path="arrhenius"      element={<Navigate to="/analysis" replace />} />
          <Route path="history"        element={<Navigate to="/report" replace />} />
          <Route path="run"            element={<Navigate to="/control" replace />} />
          <Route path="cockpit"        element={<Navigate to="/monitor" replace />} />
          <Route path="experiment"     element={<Navigate to="/control" replace />} />
          <Route path="agent"          element={<Navigate to={ENABLE_DEV_ROUTES ? '/dev/agent' : '/monitor'} replace />} />
          <Route path="validation"     element={<Navigate to={ENABLE_DEV_ROUTES ? '/dev/validation' : '/analysis'} replace />} />
          <Route path="demo"           element={<Navigate to={ENABLE_DEV_ROUTES ? '/dev/demo' : '/'} replace />} />
          <Route path="demo/agent-team" element={<Navigate to={ENABLE_DEV_ROUTES ? '/dev/demo/agent-team' : '/'} replace />} />
          <Route path="demo/agent-team/run/:run_id" element={<DemoTeamRunRedirect />} />
          <Route path="runs/:id"       element={<RunsLegacyRedirect />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default App
