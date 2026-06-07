import { useDataStore } from '../../stores'

function TemperatureDisplay() {
  const { currentTemperature, targetTemperature } = useDataStore()

  return (
    <div className="bg-white rounded-xl border p-4">
      <h3 className="font-semibold mb-2 text-sm">Temperature</h3>
      <div className="flex items-end gap-4">
        <div>
          <div className="text-xs text-gray-500">Current</div>
          <div className="text-3xl font-bold font-mono text-blue-700">
            {currentTemperature != null ? `${currentTemperature.toFixed(1)}°C` : '--'}
          </div>
        </div>
        {targetTemperature != null && (
          <div>
            <div className="text-xs text-gray-500">Target</div>
            <div className="text-lg font-mono text-gray-500">
              {targetTemperature.toFixed(1)}°C
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default TemperatureDisplay
