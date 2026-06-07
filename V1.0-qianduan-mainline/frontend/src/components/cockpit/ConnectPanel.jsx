import { useCallback, useEffect, useMemo, useState } from 'react'
import { controlApi } from '../../api/control'
import { useUIStore } from '../../stores'
import {
  deriveSystemTruthModel,
  getExecutionModeSentence,
  getHardwareCapabilitySentence,
  getSessionConnectionSentence,
  getTruthCompactLabels,
} from '../../utils/systemTruthModel'

const DEFAULT_PARAMS = {
  port: 'COM3',
  sample_name: '',
  T_start: 25,
  T_end: -100,
  coarse_step: 3,
  fine_step: 1,
  simulate: true,
}

function ConnectPanel() {
  const wsConnected = useUIStore((s) => s.wsConnected)
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [status, setStatus] = useState(null)
  const [busy, setBusy] = useState(false)
  const [apiReachable, setApiReachable] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const resp = await controlApi.getStatus()
      setStatus(resp?.data)
      setApiReachable(true)
    } catch {
      setApiReachable(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 4000)
    return () => clearInterval(interval)
  }, [refresh])

  const truth = useMemo(
    () => deriveSystemTruthModel({ wsConnected, apiReachable, hwStatus: status }),
    [wsConnected, apiReachable, status]
  )
  const compact = getTruthCompactLabels(truth)

  const connect = async () => {
    setBusy(true)
    try {
      await controlApi.connect(params)
      await refresh()
    } catch (e) { alert('Connect failed: ' + (e?.message || '')) }
    setBusy(false)
  }

  const disconnect = async () => {
    setBusy(true)
    try { await controlApi.disconnect(); await refresh() } catch { /* ignore */ }
    setBusy(false)
  }

  const startExperiment = async () => {
    setBusy(true)
    try { await controlApi.start({}); await refresh() } catch (e) { alert('Start failed: ' + (e?.message || '')) }
    setBusy(false)
  }

  const stopExperiment = async () => {
    setBusy(true)
    try { await controlApi.stop(); await refresh() } catch { /* ignore */ }
    setBusy(false)
  }

  const connected = status?.connected
  const running = status?.running

  return (
    <div className="bg-white rounded-xl border p-4 space-y-4">
      <div className="text-xs text-gray-700 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 space-y-1 leading-relaxed">
        <p className="font-semibold text-gray-800">Instrument path (truth model)</p>
        <p>{getHardwareCapabilitySentence(truth)}</p>
        <p>{getSessionConnectionSentence(truth)}</p>
        <p>{getExecutionModeSentence(truth)}</p>
        <p className="text-gray-500 pt-1 border-t border-slate-200 mt-1">
          WS {wsConnected ? 'reachable' : 'unreachable'} · Control API {apiReachable ? 'reachable' : 'unreachable'} · Header chips: {compact.hardware.abbr}, {compact.session.abbr}, {compact.execution.abbr}
        </p>
      </div>

      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Hardware Control</h3>
        <span
          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
            connected
              ? (status?.simulate ? 'bg-amber-100 text-amber-800' : 'bg-green-100 text-green-700')
              : 'bg-gray-100 text-gray-600'
          }`}
          title={compact.execution.title}
        >
          {connected
            ? (status?.simulate ? 'Session: simulation' : 'Session: live instrument')
            : 'Session: disconnected'}
        </span>
      </div>

      {!connected ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <label className="space-y-1">
              <span className="text-gray-500">Sample ID</span>
              <input className="w-full border rounded px-2 py-1.5" value={params.sample_name} onChange={e => setParams(p => ({ ...p, sample_name: e.target.value }))} placeholder="e.g. S8-3-9-4" />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500">Port</span>
              <input className="w-full border rounded px-2 py-1.5" value={params.port} onChange={e => setParams(p => ({ ...p, port: e.target.value }))} />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500">T start (C)</span>
              <input type="number" className="w-full border rounded px-2 py-1.5" value={params.T_start} onChange={e => setParams(p => ({ ...p, T_start: Number(e.target.value) }))} />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500">T end (C)</span>
              <input type="number" className="w-full border rounded px-2 py-1.5" value={params.T_end} onChange={e => setParams(p => ({ ...p, T_end: Number(e.target.value) }))} />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500">Coarse step (C)</span>
              <input type="number" className="w-full border rounded px-2 py-1.5" value={params.coarse_step} onChange={e => setParams(p => ({ ...p, coarse_step: Number(e.target.value) }))} />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500">Fine step (C)</span>
              <input type="number" className="w-full border rounded px-2 py-1.5" value={params.fine_step} onChange={e => setParams(p => ({ ...p, fine_step: Number(e.target.value) }))} />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={params.simulate} onChange={e => setParams(p => ({ ...p, simulate: e.target.checked }))} />
            <span>Simulation mode (software stand-in; does not prove absence of a physical instrument)</span>
          </label>
          <button onClick={connect} disabled={busy} className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {busy ? 'Connecting...' : 'Connect'}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3 text-sm text-center">
            <div className="bg-blue-50 rounded-lg p-2">
              <div className="text-xs text-gray-500">Temperature</div>
              <div className="font-mono font-semibold text-lg">{status?.current_temperature?.toFixed(1) ?? '--'}°C</div>
            </div>
            <div className="bg-green-50 rounded-lg p-2">
              <div className="text-xs text-gray-500">Measurements</div>
              <div className="font-mono font-semibold text-lg">{status?.measurement_count ?? 0}</div>
            </div>
            <div className="bg-purple-50 rounded-lg p-2">
              <div className="text-xs text-gray-500">Mode</div>
              <div className="font-mono font-semibold">{status?.mode || 'COARSE'}</div>
            </div>
          </div>
          <div className="flex gap-2">
            {!running ? (
              <button onClick={startExperiment} disabled={busy} className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50">Start</button>
            ) : (
              <button onClick={stopExperiment} disabled={busy} className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50">Stop</button>
            )}
            <button onClick={disconnect} disabled={busy} className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50">Disconnect</button>
          </div>
        </div>
      )}
    </div>
  )
}

export default ConnectPanel
