import ReactECharts from 'echarts-for-react'

function ChartCard({ title, option, height = 240, toolbar = null }) {
  return (
    <div className="card p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="font-semibold">{title}</div>
        {toolbar}
      </div>
      <ReactECharts option={option} style={{ height }} />
    </div>
  )
}

export default ChartCard
