import { Layout, Tag, Space } from 'antd'
import { SettingOutlined, ApiOutlined, LinkOutlined, DisconnectOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { useUIStore } from '../../stores'
import LanguageSwitcher from '../common/LanguageSwitcher'

const { Header: AntHeader } = Layout

/**
 * Header — 紫蓝渐变 (#667eea → #764ba2)，复刻旧 Vue MainLayout.vue。
 *
 * 内容三段：
 *   logo + 产品名  ······  WebSocket / 控制器 状态  ······  语言切换
 */
function Header() {
  const { t } = useTranslation('v3')
  const wsConnected = useUIStore((s) => s.wsConnected)
  const isControllerConnected = useUIStore((s) => s.controllerConnected)

  return (
    <AntHeader
      style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        height: 60,
        lineHeight: '60px',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        zIndex: 1000,
      }}
    >
      <h1 style={{ color: '#fff', fontSize: 22, fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
        <SettingOutlined /> {t('app.name')}
      </h1>

      <Space size={12} align="center">
        <Tag
          color={wsConnected ? 'success' : 'error'}
          icon={wsConnected ? <LinkOutlined /> : <DisconnectOutlined />}
          style={{ fontSize: 13, padding: '4px 10px' }}
        >
          {t(wsConnected ? 'app.wsConnected' : 'app.wsDisconnected')}
        </Tag>
        <Tag
          color={isControllerConnected ? 'success' : 'default'}
          icon={<ApiOutlined />}
          style={{ fontSize: 13, padding: '4px 10px' }}
        >
          {t(isControllerConnected ? 'app.controllerConnected' : 'app.controllerDisconnected')}
        </Tag>
        <LanguageSwitcher />
      </Space>
    </AntHeader>
  )
}

export default Header
