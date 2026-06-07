import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { DEFAULT_CAMPAIGN_SLUG } from '../config/mainline.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcRoot = path.resolve(__dirname, '..')

test('default campaign slug is centralized for mainline pages', () => {
  assert.equal(DEFAULT_CAMPAIGN_SLUG, 'attapulgite_aice_campaign')

  for (const rel of [
    'pages/stage0/Control.jsx',
    'pages/stage0/Home.jsx',
    'pages/stage0/Optimization.jsx',
  ]) {
    const text = fs.readFileSync(path.join(srcRoot, rel), 'utf8')
    assert.match(text, /DEFAULT_CAMPAIGN_SLUG/)
    assert.equal(text.includes("= 'attapulgite_aice_campaign'"), false)
  }
})
