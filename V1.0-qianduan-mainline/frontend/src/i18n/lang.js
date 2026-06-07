export const LANG_STORAGE_KEY = 'lang'
export const DEFAULT_LANGUAGE = 'en-US'
export const SUPPORTED_LANGUAGES = ['zh-CN', 'en-US']

export function normalizeLanguage(raw) {
  const value = String(raw || '').trim()
  if (!value) return DEFAULT_LANGUAGE
  if (SUPPORTED_LANGUAGES.includes(value)) return value

  const lower = value.toLowerCase()
  if (lower.startsWith('zh')) return 'zh-CN'
  if (lower.startsWith('en')) return 'en-US'
  return DEFAULT_LANGUAGE
}

function getDefaultStorage() {
  if (typeof window !== 'undefined' && window.localStorage) {
    return window.localStorage
  }
  return null
}

export function readPersistedLanguage(storage = getDefaultStorage()) {
  try {
    const value = storage?.getItem?.(LANG_STORAGE_KEY)
    return value ? normalizeLanguage(value) : null
  } catch {
    return null
  }
}

export function persistLanguage(lang, storage = getDefaultStorage()) {
  const normalized = normalizeLanguage(lang)
  try {
    storage?.setItem?.(LANG_STORAGE_KEY, normalized)
  } catch {
    // ignore storage errors
  }
  return normalized
}

export function resolveInitialLanguage(opts = {}) {
  const storage = opts.storage ?? getDefaultStorage()
  const persisted = readPersistedLanguage(storage)
  if (persisted) return persisted

  if (opts.navigatorLanguage) {
    return normalizeLanguage(opts.navigatorLanguage)
  }
  if (typeof navigator !== 'undefined') {
    return normalizeLanguage(navigator.language)
  }
  return DEFAULT_LANGUAGE
}
