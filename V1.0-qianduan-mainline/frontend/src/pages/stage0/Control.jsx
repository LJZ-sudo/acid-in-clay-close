import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Card, Steps, Form, Input, InputNumber, Select, Button, Space,
  Descriptions, Divider, App as AntdApp, Alert, Tag, Checkbox, Progress,
  Segmented, Tooltip,
} from 'antd'
import { useTranslation } from 'react-i18next'
import { controlApi } from '../../api/control'
import { campaignsApi } from '../../api/campaigns'
import { DEFAULT_CAMPAIGN_SLUG } from '../../config/mainline'
import { useUIStore, useDataStore } from '../../stores'

/**
 * Control — 4 步实验向导，复刻旧 Vue Control.vue 但**字段严格对齐**
 * FastAPI 后端 backend_api/routers/control.py：
 *
 *   POST /api/control/connect : { port, simulate, coarse_step, fine_step, t_start, t_end }
 *   POST /api/control/start   : { sample_id, t_start, t_end, coarse_step, fine_step }
 *
 * 自 2026-05-12 起后端 schema 已扩展：第 2 步的样品几何参数（厚度/面积/材料备注）、
 * 第 3 步的 CHI 仪器参数（频率/振幅/初始电压），以及 BO recipe 溯源（R/N/campaign/parent）
 * 都会随 /api/control/start 一起落到后端 runs/<run_id>/sample_summary.json。
 * 注意：CHI 频率/振幅本身仍需要在 CHI 软件里手动设置（前端不替你下发），
 * 这里只是把"前端看到的值"持久化，便于事后核对。
 */
const COM_PORTS = ['COM1','COM2','COM3','COM4','COM5','COM6','COM7','COM8','COM9','COM10']

function Control() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { t } = useTranslation('v3')
  const { message } = AntdApp.useApp()
  const setControllerConnected = useUIStore((s) => s.setControllerConnected)
  const currentTemp = useDataStore((s) => s.currentTemperature)
  const isControllerConnected = useUIStore((s) => s.controllerConnected)
  const setExperimentParams = useDataStore((s) => s.setExperimentParams)

  const prefillR = searchParams.get('R')
  const prefillN = searchParams.get('N')
  const prefillCampaign = searchParams.get('campaign')
  const prefillParent = searchParams.get('parent')
  const hasPrefill = prefillR != null || prefillN != null

  const [step, setStep] = useState(0)
  const [connecting, setConnecting] = useState(false)
  const [starting, setStarting] = useState(false)
  // Backend-reported connection mode ('real' | 'simulation' | null) — surfaces
  // the silent ImportError fallback in hardware_adapter.connect().
  const [actualMode, setActualMode] = useState(null)

  // 1. 连接 — 仿真模式已移除，只支持真实硬件。
  const [conn, setConn] = useState({ port: 'COM3' })

  // 2. 温度 + 样品物理参数
  const [exp, setExp] = useState({
    sample_id: '',
    t_start: 18,
    t_end: -100,
    coarse_step: 3,
    fine_step: 1,
    // 仅 UI / 元数据：
    thickness_m: 0.001,
    area_m2: 0.000196,
    material_note: '',
  })

  // 3. CHI / 仪器参数（仅 UI 元数据，不发后端）
  const [chi, setChi] = useState({
    high_freq_Hz: 1e6,
    low_freq_Hz: 0.1,
    init_voltage_V: 0,
    amplitude_mV: 10,
  })

  // 4. 自动后处理（Stage0 + Stage1）
  //    runMode 显式区分两种产物：
  //      'cold_start'  : 只跑 Stage0（积累数据期，**仍会自动后处理→生成 bundle**，不跑 BO+LLM）
  //      'formal'      : Stage0 完成后自动跑 Stage1 BO+LLM，写 next_experiment_recipe.json
  //    postProc.auto 仍然控制"实验结束→复制 CHI→Stage0"这一段；如果用户关了 auto，则 mode 失去意义。
  const [postProc, setPostProc] = useState({
    auto: true,
    runMode: 'cold_start',
    ao_folder: '', // 留空 → 后端按「日期__样品ID」自动派生（同日多样品互不覆盖）
  })

  // Stage1 就绪状态（来自后端 GET /campaigns/{slug}/stage1-readiness）
  // null = 未加载；ready=true 表示去重配方数 ≥ 冷启动阈值，可正式进入 GP+EI
  const [stage1Readiness, setStage1Readiness] = useState(null)

  useEffect(() => {
    let cancelled = false
    const slug = prefillCampaign || DEFAULT_CAMPAIGN_SLUG
    campaignsApi
      .getStage1Readiness(slug)
      .then((r) => {
        if (!cancelled) setStage1Readiness(r?.data || null)
      })
      .catch(() => {
        if (!cancelled) setStage1Readiness(null)
      })
    return () => {
      cancelled = true
    }
  }, [prefillCampaign])

  // 如果就绪状态已经达标，把默认运行模式提到「正式运行」（仍可被用户改回冷启动）
  useEffect(() => {
    if (stage1Readiness?.stage1_ready) {
      setPostProc((p) => (p.runMode === 'cold_start' ? { ...p, runMode: 'formal' } : p))
    }
  }, [stage1Readiness?.stage1_ready])

  // 从 BO recipe 跳过来：自动预填 + 跳到第 2 步（已连接时直接到第 2 步）
  useEffect(() => {
    if (!hasPrefill) return
    const suggested_id = prefillR && prefillN
      ? `BO-R${Number(prefillR).toFixed(2)}-N${Number(prefillN).toFixed(2)}-${Date.now().toString(36).slice(-4)}`
      : ''
    setExp((prev) => ({
      ...prev,
      sample_id: prev.sample_id || suggested_id,
      material_note: prev.material_note
        || (prefillCampaign
          ? `${prefillCampaign}: R=${prefillR}, N=${prefillN}${prefillParent ? `, parent=${prefillParent}` : ''}`
          : `R=${prefillR}, N=${prefillN}`),
    }))
    setPostProc((p) => ({ ...p, runMode: 'formal' }))
    if (isControllerConnected && step === 0) setStep(1)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleConnect = async () => {
    setConnecting(true)
    try {
      const payload = {
        port: conn.port,
        simulate: false,
        coarse_step: exp.coarse_step,
        fine_step: exp.fine_step,
        t_start: exp.t_start,
        t_end: exp.t_end,
      }
      const r = await controlApi.connect(payload)
      if (r?.data?.ok || r?.status === 200) {
        const mode = r?.data?.mode || 'real'
        setActualMode(mode)
        message.success(t('control.msgConnected'))
        setControllerConnected(true)
        setStep(1)
      } else {
        message.error(r?.data?.error || t('control.msgConnectFail'))
      }
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'unknown'
      message.error(t('control.msgConnectFail') + '：' + detail)
    } finally {
      setConnecting(false)
    }
  }

  const handleStart = async () => {
    if (!exp.sample_id) {
      message.warning(t('control.msgNeedSampleId'))
      setStep(1)
      return
    }
    setStarting(true)
    try {
      const payload = {
        sample_id: exp.sample_id,
        t_start: Number(exp.t_start),
        t_end: Number(exp.t_end),
        coarse_step: Number(exp.coarse_step),
        fine_step: Number(exp.fine_step),
        thickness_m: exp.thickness_m != null ? Number(exp.thickness_m) : null,
        area_m2: exp.area_m2 != null ? Number(exp.area_m2) : null,
        material_note: exp.material_note || null,
        chi_high_freq_Hz: chi.high_freq_Hz != null ? Number(chi.high_freq_Hz) : null,
        chi_low_freq_Hz: chi.low_freq_Hz != null ? Number(chi.low_freq_Hz) : null,
        chi_init_voltage_V: chi.init_voltage_V != null ? Number(chi.init_voltage_V) : null,
        chi_amplitude_mV: chi.amplitude_mV != null ? Number(chi.amplitude_mV) : null,
        R: prefillR != null ? Number(prefillR) : null,
        N: prefillN != null ? Number(prefillN) : null,
        campaign: prefillCampaign || stage1Readiness?.slug || DEFAULT_CAMPAIGN_SLUG,
        parent_sample_id: prefillParent || null,
        ao_folder: postProc.ao_folder || null,
        auto_postprocess: !!postProc.auto,
        run_stage1_after_stage0: !!(postProc.auto && postProc.runMode === 'formal'),
      }
      await controlApi.start(payload)
      setExperimentParams({
        sample_id: exp.sample_id,
        t_start: payload.t_start,
        t_end: payload.t_end,
        coarse_step: payload.coarse_step,
        fine_step: payload.fine_step,
        thickness_m: payload.thickness_m,
        area_m2: payload.area_m2,
        material_note: payload.material_note,
        R: payload.R,
        N: payload.N,
        campaign: payload.campaign,
        chi: {
          high_freq_Hz: payload.chi_high_freq_Hz,
          low_freq_Hz: payload.chi_low_freq_Hz,
          init_voltage_V: payload.chi_init_voltage_V,
          amplitude_mV: payload.chi_amplitude_mV,
        },
      })
      message.success(`${t('control.msgRunStarted')}：${exp.sample_id}`)
      navigate('/monitor')
    } catch (err) {
      message.error(t('control.msgStartFail') + '：' + (err?.response?.data?.detail || err?.message || 'unknown'))
    } finally {
      setStarting(false)
    }
  }

  return (
    <div style={{ maxWidth: 980, margin: '0 auto' }}>
      <Card title={t('control.title')} bordered={false}>
        {actualMode === 'real' && (
          <Alert
            type="success"
            showIcon
            style={{ marginBottom: 16 }}
            message={
              <Space size={6}>
                <span>后端当前连接模式：</span>
                <Tag color="green" style={{ margin: 0 }}>REAL 硬件</Tag>
              </Space>
            }
            description="串口已打开，TemperatureDriver 已就绪。CHI 测量仍需要在 CHI 桌面软件中执行（前端会自动调度，但仪器本身必须在线）。"
          />
        )}
        {hasPrefill && (
          <Alert
            type="success"
            showIcon
            style={{ marginBottom: 16 }}
            message={
              <Space size={6}>
                <Tag color="purple" style={{ margin: 0 }}>BO</Tag>
                <span>已采纳 <code>{prefillCampaign || 'campaign'}</code> 的下一组推荐：</span>
                <Tag color="blue">R = {prefillR}</Tag>
                <Tag color="blue">N = {prefillN}</Tag>
                {prefillParent && <span style={{ fontSize: 12, color: '#666' }}>← {prefillParent}</span>}
              </Space>
            }
            description="样品 ID 已建议，材料备注已记录 R/N。请在第 2 步确认温度参数后启动。"
          />
        )}

        {/*
          ===== 全局实验阶段开关 =====
          一次实验的 mode 在这里**先**选定，会影响：
            - 顶部 banner 提示
            - Step 2 是否显示「📋 加载 Stage1 推荐配方」按钮
            - Step 3 的自动后处理走 Stage0 only 还是 Stage0+Stage1
          冷启动阶段（去重配方数 < cold_start_threshold）禁用「正式优化」选项。
        */}
        <ExperimentPhaseBanner
          mode={postProc.runMode}
          onChangeMode={(v) => setPostProc((p) => ({ ...p, runMode: v }))}
          readiness={stage1Readiness}
          onApplyRecipe={({ R, N, parent, slug }) => {
            setExp((prev) => ({
              ...prev,
              material_note: `R=${R}, N=${N} (BO from ${slug}${parent ? `, parent=${parent}` : ''})`,
              sample_id: prev.sample_id || `ATA-${new Date().toISOString().slice(0, 10).replaceAll('-', '')}-R${R}-N${N}`,
            }))
            message.success(`已加载 Stage1 推荐配方 R=${R}, N=${N}`)
          }}
        />

        <Steps current={step} items={[
          { title: t('control.step1') },
          { title: t('control.step2') },
          { title: t('control.step3') },
          { title: t('control.step4') },
        ]} style={{ marginBottom: 32 }} />

        {step === 0 && (
          <Form layout="horizontal" labelCol={{ span: 6 }} wrapperCol={{ span: 14 }}>
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message="仅支持真实硬件模式"
              description="仿真模式已移除。请确保温控仪、CHI 软件与串口都已就绪；连接失败会直接报错并显示原因。"
            />
            <Form.Item label={t('control.port')} required>
              <Select
                value={conn.port}
                onChange={(v) => setConn({ ...conn, port: v })}
                options={COM_PORTS.map((p) => ({ value: p, label: p }))}
                style={{ width: 160 }}
              />
            </Form.Item>
            <Form.Item wrapperCol={{ offset: 6 }}>
              <Button type="primary" size="large" loading={connecting} onClick={handleConnect}>
                {t('control.connectHardware')}
              </Button>
            </Form.Item>
          </Form>
        )}

        {step === 1 && (
          <>
            <ManualTempCard
              currentTemp={currentTemp}
              defaultTarget={exp.t_start ?? 18}
              onSync={(v) => setExp((prev) => ({ ...prev, t_start: v }))}
              message={message}
            />

            <Form layout="horizontal" labelCol={{ span: 8 }} wrapperCol={{ span: 12 }}>
              <Divider orientation="left">{t('control.sectionId')}</Divider>
              <Form.Item label={t('control.sampleId')} required>
                <Input value={exp.sample_id} onChange={(e) => setExp({ ...exp, sample_id: e.target.value })}
                  placeholder={t('control.sampleIdPlaceholder')} />
              </Form.Item>

              <Divider orientation="left">{t('control.sectionTemp')}</Divider>
              <Form.Item label={`${t('control.tStart')} (°C)`}>
                <InputNumber value={exp.t_start} onChange={(v) => setExp({ ...exp, t_start: v })} min={-200} max={500} />
              </Form.Item>
              <Form.Item label={`${t('control.tEnd')} (°C)`}>
                <InputNumber value={exp.t_end} onChange={(v) => setExp({ ...exp, t_end: v })} min={-200} max={500} />
              </Form.Item>
              <Form.Item label={`${t('control.coarseStep')} (°C)`}>
                <InputNumber value={exp.coarse_step} onChange={(v) => setExp({ ...exp, coarse_step: v })} min={0.5} max={50} step={0.5} />
              </Form.Item>
              <Form.Item label={`${t('control.fineStep')} (°C)`}>
                <InputNumber value={exp.fine_step} onChange={(v) => setExp({ ...exp, fine_step: v })} min={0.1} max={10} step={0.1} />
              </Form.Item>

              <Divider orientation="left">{t('control.sectionPhys')}</Divider>
              <Form.Item label={`${t('control.thickness')} (m)`}>
                <InputNumber value={exp.thickness_m} onChange={(v) => setExp({ ...exp, thickness_m: v })} min={0.0001} max={0.01} step={0.0001} />
              </Form.Item>
              <Form.Item label={`${t('control.area')} (m²)`}>
                <InputNumber value={exp.area_m2} onChange={(v) => setExp({ ...exp, area_m2: v })} min={0.00001} max={0.001} step={0.00001} />
              </Form.Item>
              <Form.Item label={t('control.materialNote')}>
                <Input value={exp.material_note} onChange={(e) => setExp({ ...exp, material_note: e.target.value })}
                  placeholder={t('control.materialNotePh')} />
              </Form.Item>

              <Form.Item wrapperCol={{ offset: 8 }}>
                <Space>
                  <Button onClick={() => setStep(0)}>{t('common.prev')}</Button>
                  <Button type="primary" onClick={() => setStep(2)} disabled={!exp.sample_id}>{t('common.next')}</Button>
                </Space>
              </Form.Item>
            </Form>
          </>
        )}

        {step === 2 && (
          <>
            <Alert
              type="info"
              showIcon
              message={t('control.chiNote')}
              description={t('control.chiNoteBody')}
              style={{ marginBottom: 16 }}
            />
            <Form layout="horizontal" labelCol={{ span: 8 }} wrapperCol={{ span: 12 }}>
              <Form.Item label={`${t('control.highFreq')} (Hz)`}>
                <InputNumber value={chi.high_freq_Hz} onChange={(v) => setChi({ ...chi, high_freq_Hz: v })} min={1} max={1e7} />
              </Form.Item>
              <Form.Item label={`${t('control.lowFreq')} (Hz)`}>
                <InputNumber value={chi.low_freq_Hz} onChange={(v) => setChi({ ...chi, low_freq_Hz: v })} min={0.001} max={1e3} />
              </Form.Item>
              <Form.Item label={`${t('control.initVoltage')} (V)`}>
                <InputNumber value={chi.init_voltage_V} onChange={(v) => setChi({ ...chi, init_voltage_V: v })} min={-2} max={2} step={0.01} />
              </Form.Item>
              <Form.Item label={`${t('control.amplitude')} (mV)`}>
                <InputNumber value={chi.amplitude_mV} onChange={(v) => setChi({ ...chi, amplitude_mV: v })} min={1} max={100} />
              </Form.Item>

              <Form.Item wrapperCol={{ offset: 8 }}>
                <Space>
                  <Button onClick={() => setStep(1)}>{t('common.prev')}</Button>
                  <Button type="primary" onClick={() => setStep(3)}>{t('common.next')}</Button>
                </Space>
              </Form.Item>
            </Form>
          </>
        )}

        {step === 3 && (
          <>
            <Descriptions title={t('control.confirmBackend')} column={2} bordered size="small">
              <Descriptions.Item label={t('control.sampleId')}>{exp.sample_id}</Descriptions.Item>
              <Descriptions.Item label={t('control.tStart')}>{exp.t_start} °C</Descriptions.Item>
              <Descriptions.Item label={t('control.tEnd')}>{exp.t_end} °C</Descriptions.Item>
              <Descriptions.Item label={t('control.coarseStep')}>{exp.coarse_step} °C</Descriptions.Item>
              <Descriptions.Item label={t('control.fineStep')}>{exp.fine_step} °C</Descriptions.Item>
            </Descriptions>

            <Descriptions title={t('control.confirmMeta')} column={2} bordered size="small" style={{ marginTop: 20 }}>
              <Descriptions.Item label={t('control.thickness')}>{exp.thickness_m} m</Descriptions.Item>
              <Descriptions.Item label={t('control.area')}>{exp.area_m2} m²</Descriptions.Item>
              <Descriptions.Item label={t('control.materialNote')} span={2}>{exp.material_note || '—'}</Descriptions.Item>
              <Descriptions.Item label={t('control.freqRange')}>{chi.low_freq_Hz} → {chi.high_freq_Hz} Hz</Descriptions.Item>
              <Descriptions.Item label={t('control.amplitude')}>{chi.amplitude_mV} mV</Descriptions.Item>
            </Descriptions>

            <Stage1ReadinessPanel readiness={stage1Readiness} />

            <Card
              size="small"
              title={
                <Space>
                  <span>🚦 本次实验阶段（来自顶部开关，只读）</span>
                  <Tag color={postProc.runMode === 'formal' ? 'green' : 'orange'}>
                    {postProc.runMode === 'formal' ? '🚀 正式优化 (Stage0 + Stage1)' : '🧊 冷启动 (Stage0 only)'}
                  </Tag>
                </Space>
              }
              style={{ marginTop: 16 }}
              styles={{ body: { padding: '12px 16px' } }}
            >
              <div style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>
                {postProc.runMode === 'formal'
                  ? '✅ 本轮 Stage0 完成后将自动调用 run_optimization_loop.py；仅当 Stage0 valid 时写入 history_db 并生成下一组 R/N 推荐。'
                  : '🧊 本轮只跑 Stage0（测量 → CHI 复制 → bundle + 单样品 Closure），用于在 BO 解锁前覆盖参数空间。'}
                {' '}要切换请回到页面顶部的「实验阶段」开关。
              </div>
              <Checkbox
                checked={postProc.auto}
                onChange={(e) => setPostProc((p) => ({ ...p, auto: e.target.checked }))}
              >
                启用自动后处理（关闭后只测量、不复制 CHI、不跑 Stage0；之后用 <code>POST /api/control/postprocess</code> 补跑）
              </Checkbox>
            </Card>

            <Descriptions
              title="本轮即将执行"
              column={2}
              bordered
              size="small"
              style={{ marginTop: 16 }}
            >
              <Descriptions.Item label="自动后处理">
                <Tag color={postProc.auto ? 'green' : 'default'}>
                  {postProc.auto ? '是 — 实验结束后自动跑' : '否 — 测完手动处理'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Stage1 BO+LLM">
                <Tag color={postProc.auto && postProc.runMode === 'formal' ? 'green' : 'default'}>
                  {!postProc.auto
                    ? '— (未启用后处理)'
                    : postProc.runMode === 'formal'
                    ? '开 — 写 next_experiment_recipe.json'
                    : '关 — 冷启动积累数据'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="data/ao 子目录">
                {postProc.ao_folder || '(自动按样品 ID 日期派生)'}
              </Descriptions.Item>
              <Descriptions.Item label="管线" span={2}>
                <div style={{ fontSize: 12, color: '#666' }}>
                  1. 从 <code>E:\chi_data</code> 复制 <code>{exp.sample_id || '<sample_id>'}*_T*.txt</code> 与 <code>材料制备.txt</code>（或 <code>样品ID_材料制备.txt</code>）到 <code>data/ao/{postProc.ao_folder || '<日期__样品ID>'}/</code><br />
                  2. 跑 <code>process_ao_stage0.py</code> → 生成 bundle；随后<strong>自动生成</strong>单样品 Closure（环境变量 <code>CLOSURE_AFTER_STAGE0=0</code> 可关）<br />
                  3. {postProc.runMode === 'formal' ? <strong>跑 <code>run_optimization_loop.py</code> → Stage0 valid 时写入 history_db + 新 recipe；前端 <code>/optimization</code> 立即可读推荐</strong> : '（冷启动模式跳过此步）'}
                </div>
              </Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 24, textAlign: 'center' }}>
              <Space size="large">
                <Button size="large" onClick={() => setStep(2)}>{t('common.prev')}</Button>
                <Button type="primary" size="large" loading={starting} onClick={handleStart}
                  icon={<span>▶</span>}>
                  {t('control.startExperiment')}
                </Button>
              </Space>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}

/**
 * 🚦 全局「实验阶段」开关 + Banner
 *
 * 这是整个 Control 页面的顶层 mode 控制：用户用一个 Segmented 在两种模式间显式切换，
 * 切换后下方所有 Step 的提示、动作、按钮都会跟着调整。
 *
 *   🧊 冷启动模式 (Stage 0 only)
 *      —— 用于积累真机训练点。BO/LLM 关闭。Banner 显示当前 n_distinct / threshold 进度。
 *
 *   🚀 正式优化模式 (Stage 0 + Stage 1 BO + LLM)
 *      —— Stage 0 完成后自动调用 BO + LLM，写 next_experiment_recipe.json。
 *         Banner 内集成「📋 加载 Stage1 推荐配方」按钮，一键回填上一轮 BO 出的 R/N。
 *
 * 当 stage1_readiness.stage1_ready=false（去重配方数 < 阈值）时禁用「正式优化」选项，
 * 强制用户先把 cold start 跑完，避免在数据不足时启动 BO（其实那会走随机采样，无意义）。
 */
function ExperimentPhaseBanner({ mode, onChangeMode, readiness, onApplyRecipe }) {
  const { message } = AntdApp.useApp()
  const [loadingRecipe, setLoadingRecipe] = useState(false)
  const ready = !!readiness?.stage1_ready
  const slug = readiness?.slug || DEFAULT_CAMPAIGN_SLUG

  const handleApplyRecipe = async () => {
    setLoadingRecipe(true)
    try {
      const r = await campaignsApi.getNextRecipe(slug)
      const wrapper = r?.data?.recipe || r?.data
      const rec = wrapper?.recipe || wrapper
      const params = rec?.recommended_parameters || rec?.optimizer_suggestion || {}
      const R = params?.R
      const N = params?.N
      if (R == null || N == null) {
        message.warning('next_experiment_recipe.json 未找到 R/N，请先在 Stage1 输出目录运行 suggest_next.py')
        return
      }
      onApplyRecipe({
        R: Number(R).toFixed(2),
        N: Number(N).toFixed(2),
        parent: wrapper?.metadata?.source_tag || null,
        slug,
      })
    } catch (e) {
      message.error(
        '加载推荐失败：' + (e?.response?.data?.detail || e?.message || 'unknown') +
        '。请先跑一次 stage1_optimization/suggest_next.py 生成 recipe。'
      )
    } finally {
      setLoadingRecipe(false)
    }
  }

  return (
    <Card
      size="small"
      style={{ marginBottom: 16, borderColor: mode === 'formal' ? '#52c41a' : '#fa8c16' }}
      styles={{ body: { padding: '12px 16px' } }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>🚦 实验阶段</span>
          <Segmented
            size="large"
            value={mode}
            onChange={(v) => {
              if (v === 'formal' && readiness && !ready) {
                message.warning(
                  `还差 ${Math.max((readiness.cold_start_threshold || 5) - (readiness.n_distinct_recipes || 0), 0)} ` +
                  `个去重配方才能解锁正式优化模式（当前 ${readiness.n_distinct_recipes || 0}/${readiness.cold_start_threshold || 5}）`
                )
                return
              }
              onChangeMode(v)
            }}
            options={[
              { label: '🧊 冷启动 (Stage 0 only)', value: 'cold_start' },
              {
                label: (
                  <Tooltip title={ready ? '已达冷启动阈值，可进入 BO+LLM 优化' : '冷启动样品不足，先继续积累'}>
                    <span style={{ opacity: readiness && !ready ? 0.5 : 1 }}>🚀 正式优化 (Stage 0 + Stage 1)</span>
                  </Tooltip>
                ),
                value: 'formal',
                disabled: !!readiness && !ready,
              },
            ]}
          />
          {readiness && (
            <Tag color={ready ? 'green' : 'orange'} style={{ marginLeft: 4 }}>
              已积累 {readiness.n_distinct_recipes ?? 0} / {readiness.cold_start_threshold ?? 5} 配方
            </Tag>
          )}
        </div>
        {mode === 'formal' && (
          <Button
            type="primary"
            ghost
            loading={loadingRecipe}
            onClick={handleApplyRecipe}
          >
            📋 加载 Stage1 推荐配方
          </Button>
        )}
      </div>

      <Alert
        type={mode === 'formal' ? 'success' : 'warning'}
        showIcon
        style={{ marginTop: 12 }}
        message={mode === 'formal' ? '正式优化模式：Stage 0 + Stage 1 BO + LLM' : '冷启动模式：只跑 Stage 0，积累训练点'}
        description={
          mode === 'formal' ? (
            <span>
              本轮实验结束后，后端会调用 <code>run_optimization_loop.py</code>；仅当 Stage0 valid 时写入 <code>history_db</code>，
              并生成下一组 R/N 推荐到 <code>{readiness?.output_dir || 'campaign output_dir'}/next_experiment_recipe.json</code>。
              你可以在 <code>/optimization</code> 页查看，或点击右上「加载 Stage1 推荐配方」一键回填本表单。
            </span>
          ) : (
            <span>
              当前阶段目标是**覆盖参数空间边界**（R∈[0, 1.04]、N∈[0.5, 1.3]），手动配置 R/N。
              {readiness && (
                <>
                  {' '}已积累 <strong>{readiness.n_distinct_recipes}</strong>/{readiness.cold_start_threshold} 个去重配方
                  {ready ? '，已达阈值，建议切换到「🚀 正式优化」模式。' : `，还需 ${(readiness.cold_start_threshold || 5) - (readiness.n_distinct_recipes || 0)} 个。`}
                </>
              )}
            </span>
          )
        }
      />
    </Card>
  )
}

/**
 * 🔵 Stage1 BO 就绪面板 — 让用户在「开始实验」前就看到：
 *   - 当前 campaign / history_db 路径
 *   - 已积累的去重 (R,N) 配方数 / 冷启动阈值
 *   - 下一轮 BO 是 random sampling (cold_start) 还是 GP+EI (bayesian)
 * 数据源：GET /api/campaigns/{slug}/stage1-readiness（见 backend_api/routers/campaigns.py）
 */
function Stage1ReadinessPanel({ readiness }) {
  if (!readiness) {
    return (
      <Alert
        type="info"
        showIcon
        style={{ marginTop: 16 }}
        message="Stage1 就绪状态加载中…"
        description="未连上 /api/campaigns/{slug}/stage1-readiness；不影响本次实验测量，只是无法判断 BO 是否已脱离冷启动。"
      />
    )
  }
  const n = readiness.n_distinct_recipes || 0
  const th = readiness.cold_start_threshold || 5
  const ready = !!readiness.stage1_ready
  const pct = Math.min(100, Math.round((n / th) * 100))
  return (
    <Card
      size="small"
      style={{ marginTop: 16 }}
      title={
        <Space>
          <span>🔬 Stage1 BO 就绪状态</span>
          <Tag color={ready ? 'green' : 'orange'}>
            {ready ? 'BAYESIAN (GP+EI)' : 'COLD START (random sampling)'}
          </Tag>
        </Space>
      }
      styles={{ body: { padding: '12px 16px' } }}
    >
      <Descriptions column={2} size="small" bordered>
        <Descriptions.Item label="Campaign">{readiness.campaign_name}</Descriptions.Item>
        <Descriptions.Item label="参数维度">{(readiness.parameters || []).join(', ') || '—'}</Descriptions.Item>
        <Descriptions.Item label="已积累 trial">{readiness.n_trials_total ?? 0}</Descriptions.Item>
        <Descriptions.Item label="去重配方数">
          <strong style={{ color: ready ? '#389e0d' : '#d4380d' }}>{n}</strong> / {th}
        </Descriptions.Item>
        <Descriptions.Item label="history_db" span={2}>
          <code style={{ fontSize: 11 }}>{readiness.history_db}</code>
        </Descriptions.Item>
        <Descriptions.Item label="output_dir" span={2}>
          <code style={{ fontSize: 11 }}>{readiness.output_dir || '—'}</code>
        </Descriptions.Item>
      </Descriptions>
      <div style={{ marginTop: 10 }}>
        <Progress
          percent={pct}
          status={ready ? 'success' : 'active'}
          format={() => `${n} / ${th}`}
        />
        <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
          {ready
            ? '✅ 已达冷启动阈值：下一轮 Stage1 将走 GP + Expected Improvement，配合 LLM strategy_planner 给出物理合理的 R/N 推荐。'
            : `⚠️ 还差 ${Math.max(th - n, 0)} 个去重配方才能解锁 BO 正式优化；建议继续以「冷启动模式」覆盖 R/N 边界区域。`}
        </div>
      </div>
    </Card>
  )
}

/**
 * 🌡️ 手动温控卡片 —— 复刻旧 Vue Control.vue Step2 的温度面板：
 *   左侧大字号实时温度、右侧 InputNumber + "设定温度" / "同步到 T_start" 两个按钮。
 *   连接成功后即可在开实验前主动驱动温箱（用来预冷 / 回温 / 验证串口）。
 */
function ManualTempCard({ currentTemp, defaultTarget, onSync, message }) {
  const [target, setTarget] = useState(defaultTarget ?? 18)
  const [busy, setBusy] = useState(false)
  const hasTemp = currentTemp != null && !Number.isNaN(Number(currentTemp))

  const handleSet = async () => {
    if (target == null || Number.isNaN(Number(target))) {
      message.warning('请输入有效的目标温度')
      return
    }
    setBusy(true)
    try {
      const res = await controlApi.setTemperature(Number(target))
      const ok = res?.data?.success !== false
      if (ok) message.success(`已下发目标温度 ${target} °C`)
      else message.error(res?.data?.error || '设温失败')
    } catch (err) {
      message.error('设温失败: ' + (err?.response?.data?.detail || err?.message || 'unknown'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      type="inner"
      size="small"
      style={{
        marginBottom: 16,
        background: 'linear-gradient(135deg, #f8fbff 0%, #e8f4fd 100%)',
        borderRadius: 12,
      }}
      title={<span style={{ fontWeight: 600 }}>🌡️ 手动温控（连接成功后可直接驱动温箱）</span>}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
        <div style={{
          flex: '0 0 200px',
          textAlign: 'center',
          padding: '12px 16px',
          background: '#fff',
          borderRadius: 10,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        }}>
          <div style={{ fontSize: 12, color: '#7f8c8d', marginBottom: 6 }}>当前温度</div>
          <div style={{
            fontSize: 36,
            fontWeight: 'bold',
            fontFamily: '"Courier New", monospace',
            color: hasTemp ? '#e74c3c' : '#95a5a6',
          }}>
            {hasTemp ? Number(currentTemp).toFixed(1) : '--'} °C
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 260 }}>
          <Space size="small" wrap>
            <span style={{ fontWeight: 500, color: '#2c3e50' }}>目标温度：</span>
            <InputNumber
              value={target}
              onChange={(v) => setTarget(v)}
              min={-200}
              max={500}
              step={1}
              size="large"
              style={{ width: 130 }}
            />
            <Button type="primary" size="large" loading={busy} onClick={handleSet}>
              设定温度
            </Button>
            <Button
              size="large"
              onClick={() => {
                onSync?.(Number(target))
                message.success(`已同步到 T_start = ${target} °C`)
              }}
            >
              同步到 T_start
            </Button>
          </Space>
          <div style={{ fontSize: 12, color: '#7f8c8d', marginTop: 10 }}>
            💡 此处下发的目标温度只是手动控温，不会启动实验。等温度达到位再点下方"下一步"进入参数页。
          </div>
        </div>
      </div>
    </Card>
  )
}

export default Control
