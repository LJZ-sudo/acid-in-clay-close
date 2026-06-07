export function formatR2OrNA(value, locale) {
  if (value === null || value === undefined || value === '') {
    return 'N/A'
  }

  const n = Number(value)
  if (!Number.isFinite(n)) {
    return 'N/A'
  }

  return new Intl.NumberFormat(locale || undefined, {
    minimumFractionDigits: 3,
    maximumFractionDigits: 4,
  }).format(n)
}

export default formatR2OrNA
