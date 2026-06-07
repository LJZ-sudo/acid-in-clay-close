import { Select } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { persistLanguage } from '../../i18n/lang'

/**
 * Language switcher — antd Select on the brand-gradient header.
 * 真正调 i18next.changeLanguage + 持久化到 localStorage。
 */
function LanguageSwitcher() {
  const { i18n } = useTranslation()
  const value = i18n.language === 'zh-CN' ? 'zh-CN' : 'en-US'

  const handleChange = (next) => {
    persistLanguage(next)
    void i18n.changeLanguage(next)
  }

  return (
    <Select
      size="small"
      value={value}
      onChange={handleChange}
      suffixIcon={<GlobalOutlined style={{ color: '#fff' }} />}
      style={{ width: 90 }}
      options={[
        { value: 'zh-CN', label: '中文' },
        { value: 'en-US', label: 'EN' },
      ]}
    />
  )
}

export default LanguageSwitcher
