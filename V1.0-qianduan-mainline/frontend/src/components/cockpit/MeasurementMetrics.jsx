function MeasurementMetrics({ latestMeasurement }) {
  const m = latestMeasurement
  if (!m) {
    return (
      <div className="bg-white rounded-xl border p-4">
        <h3 className="font-semibold mb-2 text-sm">Latest Metrics</h3>
        <div className="text-sm text-gray-500 text-center py-4 px-2 leading-relaxed">
          No latest measurement row yet.
          <span className="text-xs text-gray-400 mt-1 block">
            Values mirror the most recent row in Recent Measurements (HTTP poll).
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border p-4">
      <h3 className="font-semibold mb-3 text-sm">Latest Metrics</h3>
      <div className="grid grid-cols-3 gap-2 text-center text-sm">
        <div className="bg-blue-50 rounded-lg p-2">
          <div className="text-xs text-gray-500">Rb</div>
          <div className="font-mono font-semibold">{m.rb_ohm?.toFixed(1) ?? '--'} Ω</div>
        </div>
        <div className="bg-green-50 rounded-lg p-2">
          <div className="text-xs text-gray-500">QC</div>
          <div className="font-mono font-semibold">
            <span className={
              m.qc_grade === 'A' ? 'text-green-700' :
              m.qc_grade === 'B' ? 'text-blue-700' :
              m.qc_grade === 'C' ? 'text-amber-700' :
              'text-red-700'
            }>{m.qc_grade || '--'}</span>
            {m.r2 != null && <span className="text-gray-400 text-xs ml-1">(R²={m.r2.toFixed(3)})</span>}
          </div>
        </div>
        <div className="bg-purple-50 rounded-lg p-2 min-w-0">
          <div className="text-xs text-gray-500">Method</div>
          <div className="font-mono font-semibold text-xs truncate" title={m.fit_method || ''}>{m.fit_method || '--'}</div>
        </div>
      </div>
    </div>
  )
}

export default MeasurementMetrics
