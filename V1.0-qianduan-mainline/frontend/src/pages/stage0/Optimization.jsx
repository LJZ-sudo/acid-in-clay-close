import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, Tag, Select, Space, Row, Col, Empty, App as AntdApp } from 'antd'
import { useTranslation } from 'react-i18next'
import { campaignsApi } from '../../api/campaigns'
import LandscapeScatter from '../../components/campaign/LandscapeScatter'
import BORecipeCard from '../../components/campaign/BORecipeCard'
import Top3Table from '../../components/campaign/Top3Table'
import ParetoMini from '../../components/campaign/ParetoMini'
import CampaignHealthBar from '../../components/campaign/CampaignHealthBar'
import TerminationPanel from '../../components/campaign/TerminationPanel'
import { DEFAULT_CAMPAIGN_SLUG } from '../../config/mainline'

/**
 * 性能优化（Stage1 BO Dashboard）
 *
 * 默认加载 attapulgite_aice_campaign；通过下拉切换其他项目。
 * BO landscape + next recipe + Top3 + Pareto + Health 五个区块全保留。
 */
const DEFAULT_SLUG = DEFAULT_CAMPAIGN_SLUG
const POLL_INTERVAL_MS = 60_000

function Optimization() {
  const { t } = useTranslation('v3')
  const { message } = AntdApp.useApp()
  const [params] = useSearchParams()
  const anchorSampleId = params.get('anchor') || null

  const [list, setList] = useState([])
  const [slug, setSlug] = useState(DEFAULT_SLUG)
  const [meta, setMeta] = useState(null)
  const [trialsBundle, setTrialsBundle] = useState(null)
  const [recipeWrapper, setRecipeWrapper] = useState(null)
  const [recipeMissing, setRecipeMissing] = useState(false)
  const [health, setHealth] = useState(null)
  const [termination, setTermination] = useState(null)

  useEffect(() => {
    campaignsApi.list()
      .then((r) => {
        const rows = r?.data?.campaigns || []
        setList(rows)
        if (!rows.some((c) => c.slug === DEFAULT_SLUG) && rows.length > 0) {
          setSlug(rows[0].slug)
        }
      })
      .catch((e) => message.error('Load campaigns failed: ' + e.message))
  }, [message])

  useEffect(() => {
    if (!slug) return undefined
    let cancelled = false
    const load = async () => {
      try {
        const [m, t, h, term] = await Promise.allSettled([
          campaignsApi.getMeta(slug),
          campaignsApi.getTrials(slug),
          campaignsApi.getHealth(slug),
          campaignsApi.getTermination(slug),
        ])
        const r = await campaignsApi.getNextRecipe(slug).catch((err) => err)
        if (cancelled) return
        if (m.status === 'fulfilled') setMeta(m.value.data); else setMeta(null)
        if (t.status === 'fulfilled') setTrialsBundle(t.value.data); else setTrialsBundle(null)
        if (h.status === 'fulfilled') setHealth(h.value.data); else setHealth(null)
        if (term.status === 'fulfilled') setTermination(term.value.data); else setTermination(null)
        if (r && !(r instanceof Error) && r?.data) { setRecipeWrapper(r.data); setRecipeMissing(false) }
        else { setRecipeWrapper(null); setRecipeMissing(true) }
      } catch (err) {
        message.error('Load campaign data failed: ' + err.message)
      }
    }
    load()
    const id = setInterval(load, POLL_INTERVAL_MS)
    return () => { cancelled = true; clearInterval(id) }
  }, [slug, message])

  const trials = trialsBundle?.trials ?? []
  const paretoIds = trialsBundle?.pareto_trial_ids ?? []
  const anchorTrialId = useMemo(() => {
    if (!anchorSampleId) return null
    const hit = trials.find((t) => t?.metadata?.sample_id === anchorSampleId)
    return hit?.trial_id ?? null
  }, [trials, anchorSampleId])

  const objective = meta?.objective || {}
  const bounds = meta?.bounds || {}

  const slugOptions = useMemo(() => {
    const seen = new Set()
    const out = []
    if (!list.some((c) => c.slug === DEFAULT_SLUG)) {
      out.push({ value: DEFAULT_SLUG, label: `${DEFAULT_SLUG} (新主线)` })
      seen.add(DEFAULT_SLUG)
    }
    list.forEach((c) => {
      if (seen.has(c.slug)) return
      seen.add(c.slug)
      out.push({
        value: c.slug,
        label: `${c.campaign_name || c.slug}${c.slug === DEFAULT_SLUG ? ' (default)' : ''}`,
      })
    })
    return out
  }, [list])

  return (
    <div style={{ maxWidth: 1500, margin: '0 auto' }}>
      <Card
        title={<Space>
          <span>{t('opt.title')}</span>
          {meta?.campaign_name && <span style={{ color: '#666', fontWeight: 'normal' }}>· {meta.campaign_name}</span>}
          {objective.formula && <Tag color="blue">{objective.goal} · {objective.formula}</Tag>}
        </Space>}
        extra={
          <Space>
            <span style={{ fontSize: 13, color: '#666' }}>{t('opt.project')}：</span>
            <Select value={slug} onChange={setSlug} style={{ width: 280 }}
              options={slugOptions} />
          </Space>
        }
        bordered={false}
      >
        <Space size="large" wrap style={{ fontSize: 12, color: '#666' }}>
          {Object.entries(bounds).map(([k, v]) => (
            <span key={k}><code>{k} ∈ [{v.low}, {v.high}]</code></span>
          ))}
          <Tag>{t('opt.trials')}: {trialsBundle?.n_trials ?? 0}</Tag>
          <Tag>{t('opt.pareto')}: {paretoIds.length}</Tag>
        </Space>
      </Card>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <Card title={t('opt.landscape')} bordered={false}>
            {trials.length === 0
              ? <Empty description={t('opt.noTrials')} style={{ padding: 60 }} />
              : <LandscapeScatter trials={trials} paretoIds={paretoIds}
                  recommended={recipeWrapper?.recipe} anchorTrialId={anchorTrialId} height={460}
                  bounds={bounds} />}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          {recipeMissing && !recipeWrapper ? (
            <Card title={t('opt.noRecipe')} bordered={false}>
              <Empty description={t('opt.noRecipeBody')} />
            </Card>
          ) : (
            <BORecipeCard wrapper={recipeWrapper} anchorSampleId={anchorSampleId} campaignSlug={slug} />
          )}
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}><Top3Table trials={trials} /></Col>
        <Col xs={24} lg={10}><ParetoMini trials={trials} paretoIds={paretoIds} height={200} /></Col>
      </Row>

      <div style={{ marginTop: 16 }}>
        <TerminationPanel payload={termination} />
      </div>

      <div style={{ marginTop: 16 }}>
        <CampaignHealthBar health={health} />
      </div>
    </div>
  )
}

export default Optimization
