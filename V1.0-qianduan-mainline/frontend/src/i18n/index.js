import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import enUS from './locales/en-US.json'
import zhCN from './locales/zh-CN.json'
import { DEFAULT_LANGUAGE, persistLanguage, resolveInitialLanguage } from './lang.js'

const resources = {
  'en-US': { translation: enUS },
  'zh-CN': { translation: zhCN },
}

const initialLanguage = resolveInitialLanguage()

if (!i18n.isInitialized) {
  i18n.use(initReactI18next).init({
    resources,
    lng: initialLanguage,
    fallbackLng: DEFAULT_LANGUAGE,
    interpolation: {
      escapeValue: false,
    },
    returnNull: false,
  })
}

i18n.on('languageChanged', (lng) => {
  persistLanguage(lng)
})

persistLanguage(initialLanguage)

export default i18n

