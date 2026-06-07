import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { persistLanguage } from '../../i18n/lang'

const OPTIONS = [
  { value: 'zh-CN', labelKey: 'language.zhLabel' },
  { value: 'en-US', labelKey: 'language.enLabel' },
]

/** Header keeps English-only chrome; options use EN / ZH codes (not translated labels). */
function LanguageToggle({ headerEnglishChrome = false }) {
  const { i18n, t } = useTranslation()

  const value = useMemo(() => (i18n.language === 'zh-CN' ? 'zh-CN' : 'en-US'), [i18n.language])

  const handleChange = (event) => {
    const next = event.target.value
    persistLanguage(next)
    void i18n.changeLanguage(next)
  }

  const aria = headerEnglishChrome ? 'Interface language' : t('language.label')

  return (
    <label className="inline-flex items-center gap-2 text-xs text-gray-600">
      <span className="sr-only">{aria}</span>
      <select
        className="input !w-auto !py-1 !px-2 text-xs"
        value={value}
        onChange={handleChange}
        aria-label={aria}
      >
        {OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {headerEnglishChrome ? (option.value === 'en-US' ? 'EN' : 'ZH') : t(option.labelKey)}
          </option>
        ))}
      </select>
    </label>
  )
}

export default LanguageToggle
