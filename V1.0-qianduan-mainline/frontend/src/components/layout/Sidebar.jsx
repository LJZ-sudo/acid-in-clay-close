import { useMemo } from 'react'
import { Layout, Menu } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  HomeFilled,
  ControlOutlined,
  MonitorOutlined,
  LineChartOutlined,
  FileTextOutlined,
  RocketOutlined,
} from '@ant-design/icons'

const { Sider } = Layout

/**
 * Sidebar — 6 项主线，Element-Plus 同色深蓝灰。
 *
 * 1 首页       /
 * 2 实验控制   /control      Stage0 wizard
 * 3 实时监控   /monitor      实时温度+电导率+Agent 思考链 一处看
 * 4 数据分析   /analysis     EIS Nyquist + Arrhenius (双 Tab，实时)
 * 5 实验报告   /report       样品报告 + 样品库 + 运行历史 (3 Tab)
 * 6 性能优化   /optimization Stage1 BO landscape / next recipe
 */
function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useTranslation('v3')

  const items = useMemo(() => [
    { key: '/',             icon: <HomeFilled />,        label: t('nav.home') },
    { key: '/control',      icon: <ControlOutlined />,   label: t('nav.control') },
    { key: '/monitor',      icon: <MonitorOutlined />,   label: t('nav.monitor') },
    { key: '/analysis',     icon: <LineChartOutlined />, label: t('nav.analysis') },
    { key: '/report',       icon: <FileTextOutlined />,  label: t('nav.report') },
    { key: '/optimization', icon: <RocketOutlined />,    label: t('nav.optimization') },
  ], [t])

  const selectedKey = useMemo(() => {
    const p = location.pathname
    if (p === '/') return '/'
    const top = '/' + p.split('/').filter(Boolean)[0]
    return items.some((i) => i.key === top) ? top : '/'
  }, [location.pathname, items])

  return (
    <Sider width={210} theme="dark" style={{ background: '#304156' }}>
      <Menu
        mode="inline"
        theme="dark"
        selectedKeys={[selectedKey]}
        items={items}
        onClick={({ key }) => navigate(key)}
        style={{ background: '#304156', borderRight: 0, height: '100%' }}
      />
    </Sider>
  )
}

export default Sidebar
