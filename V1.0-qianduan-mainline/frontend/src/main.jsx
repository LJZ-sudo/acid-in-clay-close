import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider, App as AntdApp, theme as antdTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './index.css'
import i18n from './i18n/index.js'
import { v3ZH, v3EN } from './i18n/v3.js'

// Register v3 namespace (新主线 6 项的翻译) — 不动 zh-CN.json/en-US.json
i18n.addResourceBundle('zh-CN', 'v3', v3ZH, true, true)
i18n.addResourceBundle('en-US', 'v3', v3EN, true, true)

/**
 * Ant Design 5 ConfigProvider — Element-Plus 同色 (#409EFF)，
 * 圆角 6, 默认中文。AntdApp 包一层好让 message/notification 能拿到主题。
 */
const themeConfig = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    colorPrimary: '#409EFF',
    colorSuccess: '#67C23A',
    colorWarning: '#E6A23C',
    colorError:   '#F56C6C',
    colorInfo:    '#909399',
    borderRadius: 6,
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
  },
  components: {
    Layout: {
      headerBg: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      headerHeight: 60,
      headerColor: '#fff',
      siderBg: '#304156',
    },
    Menu: {
      darkItemBg: '#304156',
      darkSubMenuItemBg: '#263445',
      darkItemHoverBg: '#263445',
      darkItemSelectedBg: '#409EFF',
    },
  },
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ConfigProvider theme={themeConfig} locale={zhCN}>
      <AntdApp>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AntdApp>
    </ConfigProvider>
  </React.StrictMode>,
)
