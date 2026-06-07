import i18n from '../i18n/index.js'

function currentLocale() {
  return i18n?.resolvedLanguage || i18n?.language || 'en-US'
}

function toFiniteNumber(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export function formatLocaleNumber(value, options = {}) {
  const n = toFiniteNumber(value)
  if (n === null) return '—'
  return new Intl.NumberFormat(currentLocale(), options).format(n)
}

export function formatTemperature(value, unit = '°C') {
  const n = toFiniteNumber(value)
  if (n === null) return '—'
  return `${formatLocaleNumber(n, { maximumFractionDigits: 2 })}${unit}`
}

export function formatPercent(value, fractionDigits = 1) {
  const n = toFiniteNumber(value)
  if (n === null) return '—'
  return new Intl.NumberFormat(currentLocale(), {
    style: 'percent',
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(n)
}

export function formatDateTime(value) {
  if (!value) return '—'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(currentLocale(), {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

export function formatR2Display(value) {
  const n = toFiniteNumber(value)
  if (n === null) return '—'
  return formatLocaleNumber(n, { minimumFractionDigits: 3, maximumFractionDigits: 4 })
}

