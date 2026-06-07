export const DEFAULT_CAMPAIGN_SLUG = 'attapulgite_aice_campaign'

const viteEnv = import.meta.env || {}

export const ENABLE_DEV_ROUTES =
  viteEnv.DEV || viteEnv.VITE_ENABLE_DEV_ROUTES === '1'
