import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Row, Col, Tag, Button, Space, Divider } from 'antd'
import {
  PlayCircleOutlined,
  MonitorOutlined,
  FileTextOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { useUIStore, useDataStore } from '../../stores'
import { samplesApi } from '../../api/samples'
import { campaignsApi } from '../../api/campaigns'
import { DEFAULT_CAMPAIGN_SLUG } from '../../config/mainline'

const DEFAULT_CAMPAIGN = DEFAULT_CAMPAIGN_SLUG

function Home() {
  const navigate = useNavigate()
  const { t } = useTranslation('v3')
  const wsConnected = useUIStore((s) => s.wsConnected)
  const isControllerConnected = useUIStore((s) => s.controllerConnected)
  const isRunning = useUIStore((s) => s.experimentRunning)
  const isPaused = useUIStore((s) => s.experimentPaused)
  const currentTemp = useDataStore((s) => s.currentTemperature)

  const [nSamples, setNSamples] = useState(null)
  const [nClosure, setNClosure] = useState(null)
  const [campaign, setCampaign] = useState(null)
  const [recipe, setRecipe] = useState(null)
  const [trialsBundle, setTrialsBundle] = useState(null)
  const [healthBundle, setHealthBundle] = useState(null)

  useEffect(() => {
    samplesApi.list({ limit: 500 }).then((r) => {
      const all = r?.data?.samples || []
      setNSamples(all.length)
      setNClosure(all.filter(s => s.has_closure_report).length)
    }).catch(() => {})

    const tryLoad = async (slug) => {
      const [m, t, h, r] = await Promise.allSettled([
        campaignsApi.getMeta(slug),
        campaignsApi.getTrials(slug),
        campaignsApi.getHealth(slug),
        campaignsApi.getNextRecipe(slug),
      ])
      const meta = m.status === 'fulfilled' ? m.value?.data : null
      if (!meta) return false
      setCampaign(meta)
      setTrialsBundle(t.status === 'fulfilled' ? t.value?.data : null)
      setHealthBundle(h.status === 'fulfilled' ? h.value?.data : null)
      setRecipe(r.status === 'fulfilled' ? (r.value?.data?.recipe || null) : null)
      return true
    }
    tryLoad(DEFAULT_CAMPAIGN)
  }, [])

  const statusTag = isRunning
    ? (isPaused ? <Tag color="warning">{t('home.statusPaused')}</Tag> : <Tag color="processing">{t('home.statusRunning')}</Tag>)
    : <Tag>{t('home.statusIdle')}</Tag>
  const nextParams = recipe?.recipe?.recommended_parameters || recipe?.recommended_parameters

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto' }}>
      <Card title={t('home.systemStatus')} bordered={false} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <Row gutter={20}>
          <Col xs={24} sm={12} md={6}>
            <StatusBlock title={t('home.websocket')} content={
              <Tag color={wsConnected ? 'success' : 'error'} style={{ fontSize: 14, padding: '4px 12px' }}>
                {t(wsConnected ? 'home.statusConnected' : 'home.statusDisconnected')}
              </Tag>
            } />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <StatusBlock title={t('home.controller')} content={
              <Tag color={isControllerConnected ? 'success' : 'default'} style={{ fontSize: 14, padding: '4px 12px' }}>
                {t(isControllerConnected ? 'home.statusConnected' : 'home.statusDisconnected')}
              </Tag>
            } />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <StatusBlock title={t('home.expStatus')} content={statusTag} />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <div style={{ textAlign: 'center', padding: '16px', background: '#f5f7fa', borderRadius: 8 }}>
              <div style={{ color: '#909399', fontSize: 13, marginBottom: 8 }}>{t('home.currentTemp')}</div>
              <div style={{ fontSize: 28, fontWeight: 'bold', color: '#409EFF' }}>
                {currentTemp != null ? Number(currentTemp).toFixed(1) : '--'} °C
              </div>
            </div>
          </Col>
        </Row>

        <Divider />

        <h3 style={{ color: '#333', marginBottom: 16 }}>{t('home.quickActions')}</h3>
        <Space size={12} wrap>
          <Button type="primary" size="large" icon={<PlayCircleOutlined />} onClick={() => navigate('/control')}>
            {t('home.actStart')}
          </Button>
          <Button type="default" size="large" icon={<MonitorOutlined />} onClick={() => navigate('/monitor')}>
            {t('home.actMonitor')}
          </Button>
          <Button size="large" icon={<FileTextOutlined />} onClick={() => navigate('/report')}>
            {t('home.actReport')}
          </Button>
          <Button size="large" icon={<RocketOutlined />} onClick={() => navigate('/optimization')}>
            {t('home.actOpt')}
          </Button>
        </Space>
      </Card>

      {/* 双闭环状态 — Stage0 ↔ Stage1 */}
      <Card title={t('home.dualLoop')} bordered={false}
        style={{ marginTop: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <LoopBox
              color="#3b82f6"
              tag="Stage 0"
              title={t('home.stage0Title')}
              metrics={[
                { label: t('home.metricSamples'), value: nSamples ?? '—' },
                { label: t('home.metricClosure'), value: nClosure ?? '—' },
              ]}
              footer={t('home.stage0Footer')}
              actionLabel={t('home.actMonitor')}
              onAction={() => navigate('/monitor')}
            />
          </Col>
          <Col xs={24} md={12}>
            <LoopBox
              color="#8b5cf6"
              tag="Stage 1"
              title={t('home.stage1Title')}
              metrics={[
                { label: t('home.metricTrials'), value: trialsBundle?.n_trials ?? '—' },
                { label: t('home.metricNextRN'),
                  value: nextParams
                    ? `R=${Number(nextParams.R).toFixed(2)} N=${Number(nextParams.N).toFixed(2)}`
                    : '—' },
              ]}
              footer={
                healthBundle?.best_final_sigma_299K_S_cm != null
                  ? t('home.stage1Footer', {
                      name: campaign?.campaign_name || DEFAULT_CAMPAIGN,
                      sigma: Number(healthBundle.best_final_sigma_299K_S_cm).toExponential(2),
                    })
                  : t('home.stage1FooterEmpty', { name: campaign?.campaign_name || DEFAULT_CAMPAIGN })
              }
              actionLabel={t('home.actOpt')}
              onAction={() => navigate('/optimization')}
            />
          </Col>
        </Row>

        {/* 平台指标条 — 用统一的小卡而非衬线 Statistic */}
        <Divider />
        <Row gutter={12}>
          <Col xs={24} sm={8}><MiniMetric label={t('home.mainLoop')} value="Stage0 + Stage1" /></Col>
          <Col xs={24} sm={8}><MiniMetric label={t('home.llmModel')} value="DeepSeek v4-pro / v3.1" /></Col>
          <Col xs={24} sm={8}><MiniMetric label={t('home.rtChannel')} value="Socket.IO + SSE" /></Col>
        </Row>
      </Card>

      {/* 平台简介 */}
      <Card title={t('home.intro')} bordered={false}
        style={{ marginTop: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <p style={{ color: '#606266', lineHeight: 1.8, fontSize: 14, margin: 0 }}>{t('home.introBody')}</p>
      </Card>
    </div>
  )
}

function StatusBlock({ title, content }) {
  return (
    <div style={{ textAlign: 'center', padding: '16px', background: '#f5f7fa', borderRadius: 8 }}>
      <div style={{ color: '#909399', fontSize: 13, marginBottom: 12 }}>{title}</div>
      <div>{content}</div>
    </div>
  )
}

function MiniMetric({ label, value }) {
  return (
    <div style={{
      background: '#fafbfc', border: '1px solid #f0f0f0', borderRadius: 8,
      padding: '12px 16px',
    }}>
      <div style={{ color: '#909399', fontSize: 12, marginBottom: 6 }}>{label}</div>
      <div style={{
        color: '#303133', fontSize: 15, fontWeight: 600,
        fontFamily: 'inherit', lineHeight: 1.4,
      }}>{value}</div>
    </div>
  )
}

function LoopBox({ color, tag, title, metrics, footer, actionLabel, onAction }) {
  return (
    <div style={{
      border: `1px solid ${color}33`, borderRadius: 10, padding: 16,
      background: `linear-gradient(135deg, ${color}08, ${color}02)`,
      height: '100%', display: 'flex', flexDirection: 'column',
    }}>
      <Space style={{ marginBottom: 8 }}>
        <Tag color={color} style={{ margin: 0, fontWeight: 600 }}>{tag}</Tag>
        <span style={{ fontSize: 14, color: '#303133', fontWeight: 600 }}>{title}</span>
      </Space>
      <Row gutter={12} style={{ marginTop: 8, marginBottom: 12 }}>
        {metrics.map((m, i) => (
          <Col span={12} key={i}>
            <div style={{ background: '#fff', border: '1px solid #eef0f3', borderRadius: 6, padding: '8px 12px' }}>
              <div style={{ fontSize: 12, color: '#909399', marginBottom: 4 }}>{m.label}</div>
              <div style={{ fontSize: 16, fontWeight: 600, color: '#303133', fontFamily: 'inherit' }}>{m.value}</div>
            </div>
          </Col>
        ))}
      </Row>
      <div style={{ flex: 1, fontSize: 12, color: '#606266', lineHeight: 1.6, marginBottom: 12 }}>{footer}</div>
      <Button type="link" size="small" onClick={onAction} style={{ alignSelf: 'flex-start', padding: 0 }}>
        {actionLabel} →
      </Button>
    </div>
  )
}

export default Home
