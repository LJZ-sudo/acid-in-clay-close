export function StudioEmpty({ title = 'Unavailable', detail }) {
  return (
    <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-center text-sm text-gray-600">
      <p className="font-medium text-gray-800">{title}</p>
      {detail ? <p className="mt-2 text-xs text-gray-500 leading-relaxed">{detail}</p> : null}
    </div>
  )
}

export function StudioSection({ title, subtitle, children }) {
  return (
    <section className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        {subtitle ? <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  )
}
