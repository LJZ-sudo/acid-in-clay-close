import i18n from '../i18n/index.js'

function locale() {
  return i18n?.resolvedLanguage || i18n?.language || 'en-US'
}

function finiteNumber(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export function formatTemperature(temp, decimals = 1) {
  const n = finiteNumber(temp)
  if (n === null) return '--'
  return `${new Intl.NumberFormat(locale(), { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(n)}°C`
}

export function formatConductivity(conductivity) {
  const n = finiteNumber(conductivity)
  if (n === null) return '--'
  if (Math.abs(n) < 0.001) {
    return `${n.toExponential(2)} S/cm`
  }
  return `${new Intl.NumberFormat(locale(), { maximumFractionDigits: 4 }).format(n)} S/cm`
}

export function formatTimestamp(timestamp) {
  if (!timestamp) return '--'
  const date = timestamp instanceof Date ? timestamp : new Date(timestamp)
  if (Number.isNaN(date.getTime())) return '--'
  return new Intl.DateTimeFormat(locale(), {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

export function formatDateTime(datetime) {
  return formatTimestamp(datetime)
}

export function formatDuration(seconds) {
  const n = finiteNumber(seconds)
  if (n === null || n < 0) return '--'

  const hours = Math.floor(n / 3600)
  const minutes = Math.floor((n % 3600) / 60)
  const secs = Math.floor(n % 60)

  if (hours > 0) return `${hours}h ${minutes}m ${secs}s`
  if (minutes > 0) return `${minutes}m ${secs}s`
  return `${secs}s`
}

export function formatPercent(value, decimals = 1) {
  const n = finiteNumber(value)
  if (n === null) return '--'
  return new Intl.NumberFormat(locale(), {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n)
}
