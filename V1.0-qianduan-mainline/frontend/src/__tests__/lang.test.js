import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeLanguage, persistLanguage, readPersistedLanguage, resolveInitialLanguage } from '../i18n/lang.js'

function createStorage() {
  const map = new Map()
  return {
    getItem(key) {
      return map.has(key) ? map.get(key) : null
    },
    setItem(key, value) {
      map.set(key, String(value))
    },
  }
}

test('normalizeLanguage supports zh/en variants', () => {
  assert.equal(normalizeLanguage('en'), 'en-US')
  assert.equal(normalizeLanguage('en-US'), 'en-US')
  assert.equal(normalizeLanguage('zh'), 'zh-CN')
  assert.equal(normalizeLanguage('zh-Hans-CN'), 'zh-CN')
})

test('persist and resolve language from local storage', () => {
  const storage = createStorage()
  const saved = persistLanguage('en', storage)
  assert.equal(saved, 'en-US')
  assert.equal(readPersistedLanguage(storage), 'en-US')
  assert.equal(resolveInitialLanguage({ storage, navigatorLanguage: 'zh-CN' }), 'en-US')
})

test('resolveInitialLanguage falls back to browser language when no saved value', () => {
  const storage = createStorage()
  assert.equal(resolveInitialLanguage({ storage, navigatorLanguage: 'en-GB' }), 'en-US')
  assert.equal(resolveInitialLanguage({ storage, navigatorLanguage: 'zh-TW' }), 'zh-CN')
})
