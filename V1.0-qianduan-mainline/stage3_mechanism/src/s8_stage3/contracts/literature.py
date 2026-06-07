"""文献调研合同 — Step 05 (Mechanism Literature) 和 Step 08 (Material Literature)。

方案 D4（描述符级证据提取，见 tinging.md Layer-6 哲学）：
  每张材料文献卡现在除了 ``relevance_to_descriptors`` 这一段自然语言外，还
  可以携带一组结构化的 ``component_descriptor_claims``——每条 claim 是一个
  "组件 × 描述符 × 量化锚点" 三元组（加一句可引用的证据句）。这是 S08 → S09
  传递的**首要**信号：下游的 S09 不再从整段 summary 里猜哪个组分做哪个描述符，
  而是看到扁平化的独立 claim 池；S10 的 ``evidence_support`` 也可以按"我声称
  满足的 (component, descriptor) 里有多少被上游 claim 独立锚定"打分，从而
  终结"LLM 自报描述符覆盖、LLM 自己给自己打分"的循环。

  现存的 ``relevance_to_descriptors`` 字段作为兜底保留（D2 风格的自然语言
  描述）——当一张卡片没有 ``component_descriptor_claims``（例如旧卡、mock
  卡）时，``pack_for_s09`` 会退回到 D2 的原子化路径，不造成退化。
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ComponentDescriptorClaim(BaseModel):
    """方案 D4 的原子证据单元：组件 × 描述符 × 量化锚点。

    一张文献卡可以产生多条 claim。例如一篇 PBI/PA/HNT 的论文可以同时产生：

      1. (PBI, [D1], "dense H-bond network via imidazole N-H", "...")
      2. (HNT, [D2, D5], "tubular 1-D confinement + PA@HNT reduces leaching",
            "85.81 mS/cm at 180 °C, 0% RH")
      3. (H3PO4, [D3], "mobile proton carrier", "")

    这些 claim 相互独立：下游 S09 可以只引用 (HNT, D2) 这条证据把 HNT 放进
    一个完全不含 PBI 的新配方里，从而把组合级 anchor bias 彻底拆掉。
    """

    component: str = Field(
        ...,
        description="具体的物种/物质名（如 'attapulgite'、'halloysite nanotubes'）",
    )
    descriptor_ids: list[str] = Field(
        ...,
        description="该组件在此论文里满足的机理描述符 id 列表（如 ['D2'] 或 ['D1','D4']）",
    )
    quantitative_anchor: str = Field(
        "",
        description="可引用的量化锚点（例 '35.3 mS/cm at 80 °C'），无则留空字符串",
    )
    claim_text: str = Field(
        ...,
        description=(
            "一句话展示 (component × descriptor × quantitative_anchor) 的证据句，"
            "用于 S09/S10 在生成理由与排名时复用"
        ),
    )
    confidence: str = Field(
        "supported",
        description="supported | hint | disputed —— 对该 claim 的信心等级",
    )
    human_review_status: str = Field(
        "pending",
        description="pending | accepted | revised | rejected —— 人工审核状态",
    )
    reviewer: str = Field("", description="人工审核人")
    review_notes: str = Field("", description="人工审核备注")

    @field_validator("descriptor_ids", mode="before")
    @classmethod
    def coerce_descriptor_ids(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            parts = [p.strip() for p in v.replace(",", "/").replace(";", "/").split("/")]
            return [p for p in parts if p]
        return [str(v)]

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v):
        if not v:
            return "supported"
        s = str(v).strip().lower()
        if s not in {"supported", "hint", "disputed"}:
            return "supported"
        return s

    @field_validator("human_review_status", mode="before")
    @classmethod
    def coerce_review_status(cls, v):
        if not v:
            return "pending"
        s = str(v).strip().lower()
        if s not in {"pending", "accepted", "revised", "rejected"}:
            return "pending"
        return s


class LiteratureCard(BaseModel):
    """单条文献卡片。"""

    card_id: str = Field(..., description="卡片唯一标识")
    title: str = Field("", description="文献标题")
    authors: str = Field("", description="作者信息")
    year: int = Field(0, description="发表年份")
    doi: str = Field("", description="DOI")
    summary: str = Field("", description="文献摘要与关键发现")
    relevance_to_mechanism: str = Field("", description="与机理假说的关联（S05 用）")
    relevance_to_descriptors: str = Field("", description="与描述符的关联（S08 用，自然语言）")
    component_descriptor_claims: list[ComponentDescriptorClaim] = Field(
        default_factory=list,
        description=(
            "方案 D4：组件 × 描述符 × 量化锚点的结构化证据清单。S08 LLM 输出"
            "时每篇卡产出 ≥ 1 条 claim；pack_for_s09 会把所有卡的 claim 汇总"
            "成扁平 claim_pool 喂给 S09。"
        ),
    )
    supports_hypothesis_ids: list[str] = Field(default_factory=list)
    weakens_hypothesis_ids: list[str] = Field(default_factory=list)

    @field_validator("authors", mode="before")
    @classmethod
    def coerce_authors(cls, v):
        """LLM 有时返回 list，转为逗号分隔字符串。"""
        if isinstance(v, list):
            return ", ".join(str(a) for a in v)
        return str(v) if v is not None else ""

    @field_validator("year", mode="before")
    @classmethod
    def coerce_year(cls, v):
        if v is None:
            return 0
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    @field_validator("doi", mode="before")
    @classmethod
    def coerce_doi(cls, v):
        return str(v) if v is not None else ""


class LiteratureSurvey(BaseModel):
    """文献调研完整输出。"""

    step_id: str = Field(..., description="s05 或 s08")
    survey_scope: str = Field(..., description="mechanism_constraint | material_search")
    cards: list[LiteratureCard] = Field(default_factory=list)
    synthesis_notes: str = Field("")

    @field_validator("synthesis_notes", mode="before")
    @classmethod
    def coerce_synthesis_notes(cls, v):
        """LLM 有时返回 list 或 dict，转为字符串。"""
        if v is None:
            return ""
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return " ".join(str(item) for item in v)
        import json
        return json.dumps(v, ensure_ascii=False)
