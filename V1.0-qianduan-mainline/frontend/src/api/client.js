import axios from 'axios'
import i18n from '../i18n/index.js'
import { API_BASE_URL } from '../utils/constants'
import { normalizeLanguage, readPersistedLanguage } from '../i18n/lang'

function resolveAcceptLanguage() {
  const current = i18n?.resolvedLanguage || i18n?.language || readPersistedLanguage()
  return normalizeLanguage(current)
}

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

client.interceptors.request.use(
  (config) => {
    config.headers = config.headers || {}
    config.headers['Accept-Language'] = resolveAcceptLanguage()
    return config
  },
  (error) => Promise.reject(error)
)

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.message || error.response?.data?.error || error.message || 'request failed'
    console.error('API Error:', message)
    return Promise.reject(error)
  }
)

export default client

