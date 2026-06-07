import client from '../api/client'

/**
 * @typedef {'json'|'jsonl'|'markdown'|'text'} StageOutputKind
 */

/**
 * @typedef {{
 *   status: 'ok',
 *   kind: StageOutputKind,
 *   filePath: string,
 *   data?: unknown,
 *   rows?: unknown[],
 *   markdown?: string,
 *   text?: string,
 * } | {
 *   status: 'unavailable'|'error',
 *   filePath: string,
 *   message: string,
 * }} StageOutputResult
 */

const cache = new Map()

function inferKind(filePath, kindHint) {
  if (kindHint) return kindHint
  const l = filePath.toLowerCase()
  if (l.endsWith('.jsonl')) return 'jsonl'
  if (l.endsWith('.md') || l.endsWith('.markdown')) return 'markdown'
  if (l.endsWith('.json')) return 'json'
  return 'text'
}

/**
 * Parse JSONL into array of objects (skip invalid lines).
 * @param {string} text
 * @returns {unknown[]}
 */
export function parseJsonlLines(text) {
  const rows = []
  const lines = text.split(/\n/)
  for (const line of lines) {
    const t = line.trim()
    if (!t) continue
    try {
      rows.push(JSON.parse(t))
    } catch {
      /* skip */
    }
  }
  return rows
}

/**
 * @param {string} text
 * @param {string} filePath
 * @param {StageOutputKind} kind
 * @returns {Omit<StageOutputResult, 'status'> & { status: 'ok'|'error' }}
 */
function parseBody(text, filePath, kind) {
  if (kind === 'markdown') {
    return { status: 'ok', kind: 'markdown', filePath, markdown: text }
  }
  if (kind === 'jsonl') {
    return { status: 'ok', kind: 'jsonl', filePath, rows: parseJsonlLines(text) }
  }
  if (kind === 'json') {
    try {
      const data = JSON.parse(text)
      return { status: 'ok', kind: 'json', filePath, data }
    } catch {
      return { status: 'error', filePath, message: 'Invalid JSON payload' }
    }
  }
  return { status: 'ok', kind: 'text', filePath, text }
}

/**
 * Load a stage output file via /api/reports/download.
 * @param {string} filePath - e.g. output/stage3_mechanism/mechanism_core.json
 * @param {{ kindHint?: StageOutputKind, useCache?: boolean, signal?: AbortSignal }} [options]
 * @returns {Promise<StageOutputResult>}
 */
export async function loadStageOutput(filePath, options = {}) {
  const { kindHint, useCache = true, signal } = options
  if (!filePath) {
    return { status: 'error', filePath: '', message: 'Missing file path' }
  }

  if (useCache && cache.has(filePath)) {
    return Promise.resolve(cache.get(filePath))
  }

  try {
    const res = await client.get('/reports/download', {
      params: { file: filePath },
      responseType: 'text',
      signal,
    })
    const text = typeof res.data === 'string' ? res.data : String(res.data ?? '')
    const kind = inferKind(filePath, kindHint)
    const parsed = parseBody(text, filePath, kind)
    if (parsed.status === 'error') {
      const out = { status: 'error', filePath, message: parsed.message }
      if (useCache) cache.set(filePath, out)
      return out
    }
    const out = { status: 'ok', ...parsed }
    if (useCache) cache.set(filePath, out)
    return out
  } catch (e) {
    const statusCode = e.response?.status
    if (statusCode === 404) {
      const out = {
        status: 'unavailable',
        filePath,
        message: 'File not found or not indexed (404).',
      }
      if (useCache) cache.set(filePath, out)
      return out
    }
    const out = {
      status: 'error',
      filePath,
      message: e.response?.data?.message || e.response?.data?.error || e.message || 'Request failed',
    }
    return out
  }
}

export function clearStageOutputCacheEntry(filePath) {
  cache.delete(filePath)
}
