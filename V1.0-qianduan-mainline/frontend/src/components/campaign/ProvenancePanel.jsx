import { useEffect, useState } from 'react'
import { Card, Descriptions, Tag, Typography, Collapse, Space, Tooltip } from 'antd'
import { provenanceApi } from '../../api/provenance'

const { Text, Paragraph } = Typography

/**
 * ProvenancePanel — read-only tamper-evidence anchors for the prospective story.
 * Renders { git, llm, preregistration } from GET /api/provenance.
 * Pure display: it never triggers or alters any optimisation/analysis logic.
 */
function ProvenancePanel() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    provenanceApi.get()
      .then((r) => setData(r?.data || null))
      .catch(() => setError(true))
  }, [])

  if (error) return null
  if (!data) return null

  const git = data.git || {}
  const llm = data.llm || {}
  const pre = data.preregistration || {}
  const lineB = data.line_b || {}

  const mono = { fontFamily: 'monospace' }
  const fmtRN = (o) => (o && o.R != null && o.N != null)
    ? `R=${Number(o.R).toFixed(o.R < 0.1 ? 4 : 2)}, N=${Number(o.N).toFixed(2)}`
    : '—'

  return (
    <Card
      title={
        <Space>
          <span>前瞻性溯源 · Provenance</span>
          <Text type="secondary" style={{ fontWeight: 'normal', fontSize: 12 }}>
            只读 · 冻结 → push 时间戳 → 再测量
          </Text>
        </Space>
      }
      bordered={false}
      size="small"
    >
      <Descriptions column={{ xs: 1, sm: 2, lg: 3 }} size="small" bordered>
        <Descriptions.Item label="Git 锚点">
          {git.commit_short ? (
            <Space size={6} wrap>
              <Tooltip title={git.commit}>
                <Tag color="geekblue" style={mono}>{git.commit_short}</Tag>
              </Tooltip>
              {git.branch && <Tag>{git.branch}</Tag>}
            </Space>
          ) : <Text type="secondary">不可用</Text>}
        </Descriptions.Item>
        <Descriptions.Item label="提交时间">
          <Text style={{ fontSize: 12 }}>{git.committed_at || '—'}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="LLM">
          {llm.model
            ? <Tag color="purple" style={mono}>{(llm.provider || 'openrouter')} · {llm.model}</Tag>
            : <Text type="secondary">—</Text>}
        </Descriptions.Item>
        {git.subject && (
          <Descriptions.Item label="提交信息" span={3}>
            <Text style={{ fontSize: 12 }}>{git.subject}</Text>
          </Descriptions.Item>
        )}
      </Descriptions>

      {lineB.available && (
        <div style={{ marginTop: 12, border: '1px solid #e6f4ff', background: '#f5fbff', borderRadius: 8, padding: 12 }}>
          <Space wrap style={{ marginBottom: 8 }}>
            <Text strong>线 B · 真实前瞻 MOBO + LLM 闭环</Text>
            {lineB.round != null && <Tag color="blue">第 {lineB.round} 轮</Tag>}
            {lineB.safety_passed && <Tag color="green">safety passed</Tag>}
            {lineB.llm_used && <Tag color="purple">LLM 实时修正</Tag>}
            {lineB.frozen_at && <Tag style={{ fontSize: 11 }}>冻结 {lineB.frozen_at}</Tag>}
            {lineB.freeze_commit && (
              <Tag color="geekblue" style={mono}>{lineB.freeze_commit}</Tag>
            )}
          </Space>

          <Descriptions column={{ xs: 1, sm: 3 }} size="small" bordered>
            <Descriptions.Item label="左脑 raw MOBO">
              <Tag style={mono}>{fmtRN(lineB.raw_mobo)}</Tag>
              {lineB.raw_mobo?.mode && (
                <Text type="secondary" style={{ fontSize: 11 }}> · {lineB.raw_mobo.mode}</Text>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="右脑 LLM 终值">
              <Tag color="green" style={mono}>{fmtRN(lineB.llm_final)}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="置信度">
              <Text>{lineB.confidence != null ? lineB.confidence : '—'}</Text>
            </Descriptions.Item>
          </Descriptions>

          {lineB.reasoning_zh && (
            <Paragraph type="secondary" style={{ fontSize: 12, margin: '8px 0 0', whiteSpace: 'pre-wrap' }}>
              <Text strong style={{ fontSize: 12 }}>物理修正理由：</Text>{lineB.reasoning_zh}
            </Paragraph>
          )}

          {lineB.llm_provenance && (
            <Collapse
              size="small"
              ghost
              style={{ marginTop: 4 }}
              items={[{
                key: 'prov',
                label: 'LLM provenance（模型 + prompt SHA256，可事后核验）',
                children: (
                  <Space direction="vertical" size={2} style={{ width: '100%', fontSize: 12 }}>
                    <div style={mono}>model: {lineB.llm_provenance.model} · T={lineB.llm_provenance.temperature}</div>
                    <div style={mono}>system_prompt_sha256: {lineB.llm_provenance.system_prompt_sha256}</div>
                    <div style={mono}>user_prompt_sha256: {lineB.llm_provenance.user_prompt_sha256}</div>
                    <div style={mono}>
                      tokens: {lineB.llm_provenance.prompt_tokens} in / {lineB.llm_provenance.completion_tokens} out · seed={lineB.seed}
                    </div>
                  </Space>
                ),
              }]}
            />
          )}

          {lineB.allowed_claim && (
            <div style={{ marginTop: 8 }}>
              <Paragraph style={{ margin: 0, fontSize: 12 }}>
                <Text type="success">✓ allowed：</Text>{lineB.allowed_claim}
              </Paragraph>
            </div>
          )}
        </div>
      )}

      {pre.available && (
        <div style={{ marginTop: 12 }}>
          <Space wrap style={{ marginBottom: 8 }}>
            <Text strong>预注册</Text>
            <Tag color="blue">preregistered_at: {pre.preregistered_at}</Tag>
            {pre.run_id && <Tag style={mono}>run {pre.run_id}</Tag>}
            {pre.discovery_mode && <Tag color="cyan">{pre.discovery_mode}</Tag>}
            {pre.reconstructed && (
              <Tooltip title="该时间锚点为按文件名/哈希重建，仅作 timing reference，不作论文内容来源。">
                <Tag color="warning">RECONSTRUCTED 锚点</Tag>
              </Tooltip>
            )}
          </Space>

          <Collapse
            size="small"
            ghost
            items={[
              {
                key: 'cands',
                label: `LLM 预选候选 (${(pre.candidates || []).length}) · 实验前排名 + claim 边界`,
                children: (
                  <Space direction="vertical" style={{ width: '100%' }} size={10}>
                    {(pre.candidates || []).map((c) => (
                      <div key={c.candidate_id}
                        style={{ border: '1px solid #f0f0f0', borderRadius: 6, padding: 10 }}>
                        <Space wrap style={{ marginBottom: 4 }}>
                          <Tag style={mono}>{c.candidate_id}</Tag>
                          {c.rank_before_experiment != null &&
                            <Tag color="gold">实验前 rank #{c.rank_before_experiment}</Tag>}
                          {c.validation_status &&
                            <Tag color={c.validation_status.includes('consistent') ? 'green' : 'default'}>
                              {c.validation_status}
                            </Tag>}
                        </Space>
                        <div style={{ fontSize: 13, marginBottom: 6 }}>{c.instance_name}</div>
                        {c.allowed_claim && (
                          <Paragraph style={{ margin: 0, fontSize: 12 }}>
                            <Text type="success">✓ allowed：</Text>{c.allowed_claim}
                          </Paragraph>
                        )}
                      </div>
                    ))}
                  </Space>
                ),
              },
              ...(pre.notes ? [{
                key: 'notes',
                label: '锚点来源 / 重建说明',
                children: (
                  <Paragraph type="secondary" style={{ fontSize: 12, whiteSpace: 'pre-wrap', margin: 0 }}>
                    {pre.notes}
                  </Paragraph>
                ),
              }] : []),
            ]}
          />
        </div>
      )}
    </Card>
  )
}

export default ProvenancePanel
