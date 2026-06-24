# -*- coding: utf-8 -*-
"""Build the v1 Chinese manuscript draft (.docx) for advisor review.

Target framing: sub-journal (Digital Discovery / npj Computational Materials /
Communications Materials), structured with explicit "实验进行中 · 待插入" upgrade
slots so the in-progress prospective experiments (Line A biopolymer transfer,
Line B MOBO closed loop) can be dropped in later and, if strong enough, the
draft can be re-aimed at Nature Communications without rewrites.

Content is grounded in THREE_PILLARS_ANALYSIS_AND_WRITING_PLAN_20260608.md
(itself code/data-grounded). Numbers/paths are copied from there.

Run:
    python manuscript/build_draft_v1.py
Output:
    manuscript/acid-in-clay_draft_v1_zh.docx
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "acid-in-clay_draft_v1_zh.docx"

BODY_FONT = "宋体"
HEAD_FONT = "黑体"
LATIN_FONT = "Times New Roman"


# --------------------------------------------------------------------------- #
# low-level helpers
# --------------------------------------------------------------------------- #
def _set_east_asian(run, font_name: str) -> None:
    run.font.name = LATIN_FONT
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), font_name)
    rfonts.set(qn("w:ascii"), LATIN_FONT)
    rfonts.set(qn("w:hAnsi"), LATIN_FONT)


def style_doc(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = LATIN_FONT
    normal.font.size = Pt(10.5)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), BODY_FONT)


def para(doc, text="", *, size=10.5, bold=False, italic=False, color=None,
         align=None, font=BODY_FONT, space_after=6, space_before=0, indent_cm=None):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    pf.line_spacing = 1.25
    if indent_cm is not None:
        pf.first_line_indent = Cm(indent_cm)
    if text:
        r = p.add_run(text)
        r.bold = bold
        r.italic = italic
        r.font.size = Pt(size)
        if color is not None:
            r.font.color.rgb = color
        _set_east_asian(r, font)
    return p


def heading(doc, text, level=1):
    sizes = {0: 18, 1: 14, 2: 12, 3: 11}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12 if level <= 1 else 8)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(sizes.get(level, 11))
    r.font.color.rgb = RGBColor(0x1F, 0x38, 0x64) if level <= 1 else RGBColor(0x2B, 0x2B, 0x2B)
    _set_east_asian(r, HEAD_FONT)
    return p


def bullet(doc, text, *, level=0, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Cm(0.75 + 0.6 * level)
    p.paragraph_format.line_spacing = 1.2
    if bold_lead:
        r = p.add_run(bold_lead)
        r.bold = True
        r.font.size = Pt(10.5)
        _set_east_asian(r, BODY_FONT)
    r2 = p.add_run(text)
    r2.font.size = Pt(10.5)
    _set_east_asian(r2, BODY_FONT)
    return p


def callout(doc, title, lines, status="todo"):
    """A visually distinct slot. status='todo' (amber) or 'done' (green, data returned)."""
    if status == "done":
        title_fill, line_fill = "D4EDDA", "EAF7EE"
        title_color, line_color = RGBColor(0x14, 0x5A, 0x32), RGBColor(0x1B, 0x4D, 0x2E)
    else:
        title_fill, line_fill = "FFF3CD", "FFFBEA"
        title_color, line_color = RGBColor(0x8A, 0x61, 0x00), RGBColor(0x6B, 0x55, 0x10)
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    shade(p, title_fill)
    r = p.add_run("【" + title + "】")
    r.bold = True
    r.font.size = Pt(10.5)
    r.font.color.rgb = title_color
    _set_east_asian(r, HEAD_FONT)
    for ln in lines:
        q = doc.add_paragraph()
        q.paragraph_format.space_after = Pt(2)
        q.paragraph_format.left_indent = Cm(0.5)
        shade(q, line_fill)
        rr = q.add_run(ln)
        rr.font.size = Pt(10)
        rr.font.color.rgb = line_color
        _set_east_asian(rr, BODY_FONT)


def shade(paragraph, hex_fill):
    pPr = paragraph._p.get_or_add_pPr()
    shd = pPr.makeelement(qn("w:shd"), {})
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    pPr.append(shd)


def table(doc, headers, rows, *, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].paragraphs[0].clear()
        rr = hdr[i].paragraphs[0].add_run(h)
        rr.bold = True
        rr.font.size = Pt(9.5)
        _set_east_asian(rr, HEAD_FONT)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].paragraphs[0].clear()
            rr = cells[i].paragraphs[0].add_run(str(val))
            rr.font.size = Pt(9.5)
            _set_east_asian(rr, BODY_FONT)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def caption(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(text)
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    _set_east_asian(r, BODY_FONT)


def embed_fig(doc, filename, caption_text, width_cm=16):
    """Embed a figure (if present) centered, with a caption. No-op if missing."""
    fp = ROOT / "figures" / filename
    if not fp.exists():
        return False
    pic = doc.add_paragraph()
    pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pic.paragraph_format.space_before = Pt(4)
    pic.add_run().add_picture(str(fp), width=Cm(width_cm))
    caption(doc, caption_text)
    return True


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def build():
    doc = Document()
    style_doc(doc)
    for section in doc.sections:
        section.top_margin = Cm(2.2)
        section.bottom_margin = Cm(2.2)
        section.left_margin = Cm(2.4)
        section.right_margin = Cm(2.4)

    # ---- Title block ----
    para(doc, "初稿 v1（中文 · 供导师审阅；定稿后译英投稿）", size=9,
         color=RGBColor(0x99, 0x99, 0x99), align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=2)
    para(doc, "目标期刊（建议主投）：Digital Discovery / npj Computational Materials / "
              "Communications Materials；实验补强后可转投 Nature Communications", size=9,
         color=RGBColor(0x99, 0x99, 0x99), align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=10)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.paragraph_format.space_after = Pt(4)
    r = t.add_run("一个证据约束、主张受审计的智能体：将酸-黏土质子传导原理迁移到"
                  "冷却韧性的生物聚合物–黏土膜")
    r.bold = True
    r.font.size = Pt(16)
    r.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
    _set_east_asian(r, HEAD_FONT)

    te = doc.add_paragraph()
    te.alignment = WD_ALIGN_PARAGRAPH.CENTER
    te.paragraph_format.space_after = Pt(10)
    re = te.add_run("An evidence-constrained, claim-audited agent that transfers "
                    "acid-in-clay proton-conduction principles to cooling-resilient "
                    "biopolymer–clay membranes")
    re.italic = True
    re.font.size = Pt(11)
    re.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
    _set_east_asian(re, LATIN_FONT)

    para(doc, "作者：JZ；通讯/单位：____（待补）", size=10,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=12)

    # ---- Abstract ----
    heading(doc, "摘要", 1)
    para(doc,
         "质子导体的低温（冷却）性能退化是固态质子传导走向实用的核心瓶颈，而"
         "“用人工智能发现新材料”的叙事又常因证据链不透明、主张过度而难以取信。"
         "本工作提出并实现了一个受物理与质量控制（QC）约束、且对科学主张进行确定性"
         "审计（claim audit）的智能体材料发现框架，并以酸-黏土（acid-in-clay）质子导体"
         "为母体系给出端到端验证。其一，证据约束迁移智能体在真实大语言模型（LLM，"
         "OpenRouter，temperature=0、关闭缓存）与真实文献检索（OpenAlex）支持下，"
         "从广义生物质/聚合物/黏土文献池中“选择并重组”出莲藕淀粉（LRS）与壳聚糖（CHITO）"
         "等生物聚合物–黏土膜基元；该推理的时间戳（查询包 2026-04-17）早于首次实验。"
         "其二，提出“冷却韧性描述符”，以分段 Arrhenius 拟合，联合高温段表观活化能、冷尾电导保留率"
         "（σ(233K)/σ(273K)）与几何/QC 链共同判定；该描述符在同等几何与 QC 处理下能区分"
         "韧性（LRS，高温段 Eₐ 约 0.05 eV、冷尾电导保留约三成）与非韧性（CHITO 在约 233 K 电导坍塌"
         "近 2 个数量级）体系。其三，在"
         "凹凸棒土体系内实现物理/QC 门控的 EIS 闭环执行（BO+LLM），并如实报告其“未收敛、"
         "未超越初始点”的诚实零结果（绝对改进 = 0）。全过程由确定性主张"
         "审计器守门，硬性禁止“发现 LRS”“证明普适最优”“事后改分”等过度主张。本框架的"
         "方法学贡献——主张阶梯、确定性审计与执行引擎硬门禁——为可信的智能体材料发现"
         "提供了可复现的范式。",
         indent_cm=0.0, space_after=6)
    p = doc.add_paragraph()
    r = p.add_run("关键词：")
    r.bold = True; r.font.size = Pt(10); _set_east_asian(r, HEAD_FONT)
    r2 = p.add_run("智能体材料发现；质子传导；冷却韧性；电化学阻抗谱；贝叶斯优化；"
                   "大语言模型；主张审计；前瞻验证")
    r2.font.size = Pt(10); _set_east_asian(r2, BODY_FONT)

    para(doc, "（注：本初稿为“边实验边写”的 v1。绿色【数据已回】框为已完成的原生前瞻批次"
              "（2026-06 线 A 生物聚合物迁移、线 B MOBO 闭环 R1/R2），结论已就地写入正文；"
              "黄色框（若有）仍为待回插槽。S13/S14 下游审计待线 B 第 3 轮数据齐后一次性重跑。）", size=9,
         color=RGBColor(0x14, 0x5A, 0x32), space_before=4, space_after=10)

    # ---- 1 Introduction ----
    heading(doc, "1　引言", 1)
    para(doc,
         "固态质子导体在燃料电池、传感与离子电子学中应用广泛，但其电导率在降温时"
         "往往因质子通路的结构重排、局部冻结或体相化而显著退化，形成“高室温电导、"
         "低温脆弱”的普遍困境。如何设计在冷却过程中保持质子通路连续性的材料，是该"
         "领域的关键科学问题。", indent_cm=0.74)
    para(doc,
         "与此同时，借助贝叶斯优化（BO）与大语言模型（LLM）“自主发现新材料”成为热点，"
         "但两类可信性问题尚未被系统解决：(i) 证据链与时间线不透明——难以向审稿人证明"
         "“AI 先推理、实验后验证”的真实顺序；(ii) 主张过度——把数学上的建议、"
         "回溯性的拟合或偶发的最优误述为“发现”“收敛”“普适最优”。", indent_cm=0.74)
    para(doc,
         "本工作的核心立场是：把“受治理（governed）”作为智能体材料发现的第一性要求。"
         "我们以酸-黏土质子导体为母体系，构建并实现了一个端到端框架，其三个创新点为：",
         indent_cm=0.74)
    bullet(doc, "在真实 LLM + 真实文献检索约束下，从广义文献池“选择并重组”生物聚合物–黏土膜基元，"
                "且推理时间戳早于实验。", bold_lead="创新点 1（迁移智能体）：")
    bullet(doc, "提出冷却韧性描述符（可证伪的区分判据），对韧性/非韧性体系具备区分力（LRS 正验证、CHITO 边界验证）。",
           bold_lead="创新点 2（描述符）：")
    bullet(doc, "实现物理/QC 门控的 EIS 闭环执行（BO+LLM），并以确定性主张审计守门、"
                "如实报告诚实零结果、拒绝过度声称。", bold_lead="创新点 3（执行引擎）：")
    para(doc, "与既有“AI 发现材料”工作相比，本框架最稀缺的贡献是把不确定性与负面结果"
              "“主动门控并写入证据”，而非掩盖——这正是面向方法学型子刊的核心竞争力。",
         indent_cm=0.74, space_before=4)

    # ---- 2 System & Methods overview (the novelty, A-layer) ----
    heading(doc, "2　体系与方法学框架（核心创新，现有实现）", 1)
    para(doc, "本节给出框架的可复现要件；详细参数见第 6 节“方法”。主线是一条单向、"
              "可审计的“发现–执行–审计”链，锚定于凹凸棒土 AiCE 体系：", indent_cm=0.74)
    para(doc, "Stage0（EIS 测量与 QC/Rb/电导/分段 Arrhenius）→ Stage1（BO+LLM 真实闭环）→ "
              "Stage2（统计证据与种子）→ Stage3（LLM 机制/迁移候选/排序/注册/验证/主张审计）。",
         bold=True, indent_cm=0.0, space_after=6)

    heading(doc, "2.1　智能体支撑架构（agent harness）", 2)
    para(doc, "框架包含真正的智能体要件（而非仅一次性提示）：", indent_cm=0.74)
    bullet(doc, "仅追加（append-only）、确定性回放、不伪造时间戳。", bold_lead="记忆（memory）：")
    bullet(doc, "“生成–批判–修订”（produce-critique-revise）循环，内置过度声称（overclaim）检查规则。",
           bold_lead="自省（critic）：")
    bullet(doc, "活性遥测（liveness）。", bold_lead="心跳（heartbeat）：")
    bullet(doc, "结构化输出、缓存控制、temperature=0、JSON 模式（schema）校验。",
           bold_lead="策略规划 + LLM 网关：")
    para(doc, "诚实边界：上述智能体（agentic）层尚未接入主调度器（orchestrator），故本文不声称“具备记忆/自省"
              "的全自主智能体实时驱动了全流程”，仅声称其作为受控组件参与发现与审计。",
         size=10, color=RGBColor(0x8A, 0x4B, 0x00), indent_cm=0.0, space_before=2)

    heading(doc, "2.2　主张阶梯与确定性主张审计（S14）", 2)
    para(doc, "所有定量主张被分入三个证据带：主文级（Main-text，可作主结论）、补充级"
              "（Supplement，仅 SI）、探索级（Exploratory，仅探索、不作机制证据）。确定性审计器 S14 在管线末端"
              "对每条主张做规则化裁决，硬编码允许/禁止措辞（如允许“达到已报道最低势垒量级（record-level）”，"
              "禁止“世界纪录（world record）”“独立发现（independently discovered）”“发现了 LRS”）。", indent_cm=0.74)

    heading(doc, "2.3　执行引擎硬门禁（execution-engine gates）", 2)
    para(doc, "闭环执行受一组硬门禁约束：仅追加写入、哈希绑定人工批准、批准前禁写、"
              "仅手动 EIS（自动 CHI 工作站在取得宏命令/空池验证证据前被阻断）、原始 EIS 内容 QC、"
              "Stage0 提交门、手动 Rb 的 QC、评分门控（score gate）、禁覆盖当前结果包、无序列证据禁迟滞结论、"
              "无高级阻抗旁路数据（sidecar）禁机制证明。配套检查器默认取“保持（HOLD）”偏置。", indent_cm=0.74)

    heading(doc, "2.4　冷却韧性描述符（定义）", 2)
    para(doc, "对分段电导执行 σ(T)·T = Aᵢ·exp(−Eₐ⁽ⁱ⁾/k_BT)，以修正赤池信息量（AICc）选段、段数 ≤ 3；"
              "“冷却韧性”结论要求同时满足：高温段 Eₐ 低、冷尾电导保留率高（σ(233K)/σ(273K)）、且几何/QC 链通过。"
              "采用电导保留率而非冷尾分段 Eₐ 作为冷尾指标，因后者在深降温段存在拟合赝象（个别支为负值）。"
              "三个证据带的划分同上。", indent_cm=0.74)

    heading(doc, "2.5　EIS 质量控制（三带）", 2)
    para(doc, "QC 包含 KK（Kramers–Kronig）残差、手动与自动体相电阻（Rb）抽取的一致性、几何审计与"
              "泄漏排除。KK 采用开源 impedance.py 库的线性 KK（lin-KK，Schönleber 等[1]），以因果 RC(Voigt) 串联拟合、"
              "取逐点相对残差中位数 μ_median 判定（见 4.2 节：修正一处符号约定后，全样品 220 条谱"
              "μ_median≈0.005–0.012，KK 一致性良好）。KK 与 Rb 是两条独立 QC 轴：KK 评估谱的因果/"
              "线性/稳态，Rb 一致性评估体相电阻抽取；冷尾点因手动–自动 Rb 偏差大而降级至探索级。"
              "弛豫时间分布（DRT）当前以 max(G,0) 近似实现，仅作探索级，不作机制证据。",
         indent_cm=0.74)

    # ---- 3 Pillar 1 ----
    heading(doc, "3　创新点 1：证据约束迁移智能体", 1)
    para(doc, "链路（代码层真实存在）：Stage2 证据 → S04 假设 → S05/S06 机制仲裁 → "
              "S07 描述符 → S08 文献侦察（OpenAlex 真实接口，混合模式）→ S09 候选家族 → "
              "S10 确定性重排 → S12 前瞻注册 → S13 验证绑定 → S14 主张审计。", indent_cm=0.74)
    para(doc, "“先推理后实验”的硬证据：文献检索查询包的创建时间戳为 2026-04-17，"
              "其查询词包含“多糖质子交换膜 / 黏土–聚合物复合 / 淀粉–磷酸”等主题，"
              "早于 2026-04-25 的首次实验。", indent_cm=0.74)
    para(doc, "权威快照（2026-06-07 真实 LLM 跑数：实时调用、关闭缓存、temperature=0）"
              "给出冻结排名（前 5），其中前二名正对应本研究拟验证的体系：", indent_cm=0.74)
    table(doc,
          ["rank", "候选基元", "分数", "对应实验"],
          [["1", "Starch/PVA/有机改性凹凸棒土/H₃PO₄（指向莲藕淀粉 LRS）", "0.883", "淀粉 / LRS（正验证）"],
           ["2", "Chitosan/有机改性凹凸棒土/H₃PO₄", "0.823", "CHITO（边界验证）"],
           ["3", "Halloysite 纳米管/PA/PVA", "0.819", "另一种黏土（列为未来工作）"],
           ["4", "PVA/chitosan/Nb₂O₅/H₃PO₄", "0.738", "—"],
           ["5", "PAAm-g-starch/PA 水凝胶", "0.708", "—"]],
          widths=[1.3, 8.5, 1.6, 4.5])
    caption(doc, "表 1　冻结的前瞻候选注册表排名（来自 2026-06-07 真实 LLM 跑数；"
                 "术语泄漏惩罚为 0，即排序未参考任何生物聚合物实验结果）。前二名为本研究验证目标。")
    para(doc, "当前证据强度评定为 B+（充分但需加固）：支撑架构真实、LLM 真实、主张审计通过、"
              "排名稳定（top1=1.0、top3 Jaccard=1.0）；末端审计（S14）已把上限钉死为“选择/重组”，"
              "禁止“独立发现”。把强度提升至 A 需要原生（非重建）的前瞻验证，见下框。",
         indent_cm=0.74)
    callout(doc, "数据已回（2026-06）· 线 A 原生前瞻验证：排名被复现",
            ["顺序（原生前瞻）：候选清单冻结于 2026-06-07 注册表（注册表哈希已固定、提交已推送盖戳）→ "
             "随后于 2026-06-11～15 合成生物聚合物–黏土新膜并测宽温 EIS（至 −88～−90 °C），合成晚于冻结 4～8 天。",
             "结果：LRS（藕粉）Eₐ_high≈0.008～0.055 eV、σ_max≈3.2～3.6×10⁻²；玉米淀粉对照 Eₐ_high≈0.11～0.17 eV。"
             "智能体“LRS 优于淀粉”的实验前排名被前瞻复现，且各有 2 支重复样、Stage0 全样 KK 0 警告。",
             "绑定：4 条验证记录已仅追加（append-only）写入实验反馈库，未改动冻结排名；"
             "下游验证绑定（S13）+ 原生主张裁决（S14）留待数据全部到位后一次性重跑。",
             "措辞：前瞻验证状态由“重建通过”升级为“原生通过（测量在冻结之后）”；仍禁“独立发现 LRS”。"],
            status="done")
    embed_fig(doc, "Fig_lineA_arrhenius.png",
              "图 1　线 A 原生前瞻验证（2026-06，测量晚于 20260607 排名冻结 4–8 天）。面板 a：ln σ vs 1000/T "
              "（实心拟合线为高温段）。莲藕淀粉（LRS，蓝/青）在全温区电导高于玉米淀粉对照（橙/红），且高温段斜率更平。"
              "面板 b：高温段活化能 Eₐ_high——LRS（0.008/0.054 eV）显著低于淀粉（0.167/0.112 eV），"
              "前瞻复现了智能体“LRS 优于淀粉”的实验前排名。各组 2 支重复样、Stage0 全样 KK 0 警告。")

    # ---- 4 Pillar 2 ----
    heading(doc, "4　创新点 2：冷却韧性描述符（可证伪的区分判据）", 1)
    para(doc, "本描述符是一个预注册的多条件判据（阈值取自 line_A 预注册 §4、未事后改动）：判定“冷却韧性”"
              "需同时满足——高温段 Eₐ 低、冷尾电导保留率高（σ(233K)/σ(273K)）、且结论建立在 KK 通过的"
              "高温段数据上。其区分力来自一个稳健事实：到 233 K，非韧性体系（壳聚糖 CHITO）电导坍塌近 2 个"
              "数量级，而韧性体系（LRS）仍保留约三成。正验证（LRS）与边界验证（CHITO）在同等几何/QC 处理下"
              "对比如下：", indent_cm=0.74)
    table(doc,
          ["样品", "厚度/cm", "Eₐ_high/eV", "σ(273K)", "σ(233K)", "σ233/273†", "KK警告‡"],
          [["5.9CS（薄膜·标志样）", "0.022", "0.037", "1.85e-2", "3.63e-3", "0.20", "0/35"],
           ["4.29CS（薄膜重复）", "0.02", "0.042", "1.79e-2", "4.34e-3", "0.24", "0/36"],
           ["藕粉 6.12（厚膜·前瞻）", "0.074", "0.008", "3.07e-2", "1.09e-2", "0.36", "0/37"],
           ["藕粉 6.15（厚膜·前瞻）", "0.070", "0.054", "3.48e-2", "1.04e-2", "0.30", "0/59"],
           ["玉米淀粉 6.11/6.13", "0.063/0.074", "0.11–0.17", "~1.0e-2", "~1.8e-3", "0.17–0.19", "0"],
           ["CHITO 4.30CS/5.1CS", "0.05/0.06", "0.05/0.099", "~1.1e-2", "≈4–6e-5", "0.003–0.005", "0"]],
          widths=[3.0, 1.9, 2.4, 1.9, 1.9, 1.9, 1.5])
    caption(doc, "表 2　LRS 正验证 vs 玉米淀粉泛化 vs CHITO 边界验证（主线 stage0 重算，阈值取自预注册）。"
                 "区分力的核心是冷尾电导保留率 σ233/273：LRS≈0.20–0.36、淀粉≈0.17–0.19、"
                 "而 CHITO 仅 0.003–0.005（到 233 K 坍塌约 190–290×，≥1 个数量级）。"
                 "新增 2 支 2026-06 原生前瞻厚膜 LRS（0.070–0.074 cm，约为薄膜 3 倍）在厚膜下 Eₐ_high 仍低、σ 仍高，"
                 "表明低 Eₐ 非薄膜几何赝象（但厚/薄为跨批次对照，见正文）。"
                 "†σ233/273 = σ(233K)/σ(273K)，单调电导保留率，作为冷尾退化的稳健指标。"
                 "‡KK 警告为符号修正后计数（μ_median<0.2 为通过）：修正前因一处复数阻抗符号约定 bug "
                 "误报（如 5.9CS 27/35），符号修正 + 高频感性尾裁剪后全样品 0 警告、μ_median≈0.007，"
                 "详见 4.2 节。Eₐ/σ 由 Rb 过零点拟合得到，与 KK 无关、数值不受影响。")
    para(doc, "与文献最低势垒对标：LRS 高温段 Eₐ 保守取约 0.05 eV（厚膜重复支 0.054、薄膜 0.037–0.042；"
              "6.12 支 0.008 因高温段窗口敏感偏低，仅列为区间下限），与多孔有机聚合物 POP-2020[2]（0.039 eV）、"
              "金属–有机框架 MFM-300(Cr)[3]（0.040 eV）可比，并显著低于母体系凹凸棒土–海泡石 "
              "AiCE（约 0.12 eV）。据此允许的措辞限定为“达到已报道最低势垒量级（record-level）”，"
              "禁用“世界纪录（world record）”。", indent_cm=0.74)
    para(doc, "本创新点早期的主要科学软肋是厚度×家族混淆：低 Eₐ 此前仅见于 0.02–0.022 cm 薄膜。"
              "2026-06 的原生前瞻厚膜 LRS（0.070–0.074 cm）直接检验了这一点——在约 3 倍厚度下 Eₐ_high 仍低、"
              "σ 仍高、冷尾电导保留率仍高（σ233/273≈0.30–0.36），说明低 Eₐ 与冷却韧性是材料家族属性而非薄膜"
              "几何赝象；据此主张可由“薄膜几何 + 家族共同效应”上修为“家族属性在厚膜下仍成立”。",
         indent_cm=0.74)
    para(doc, "三点必须如实交代的边界（写入 SI）：(i) 描述符的区分力来自“冷尾电导坍塌”而非“势垒发散”——"
              "CHITO 冷段 Eₐ 实测仅约 0.64 eV、并未发散到 >1 eV，故措辞用“电导坍塌”。"
              "(ii) 冷尾分段 Eₐ 存在拟合赝象（个别支为负值），仅作定性参考，不作机制结论。"
              "(iii) 厚/薄膜对照为跨批次（旧 LRS 薄膜 0.02 cm vs 6 月新 LRS 厚膜 0.07 cm），非同批同温序，"
              "趋势支持内禀但列为 limitation；最强主张仍建议补一支同批 thin/thick。"
              "（另注：早期曾以为标志样品 KK 最脏，4.2 节查明这是一处符号约定 bug 的伪影，修正后数据 KK 干净。）",
         indent_cm=0.74)

    heading(doc, "4.2　QC 加固与一处 KK 方法学更正（用现有数据，无新表征）", 2)
    para(doc, "本工作用现有原始谱与冻结 QC 工件做了三项可复现分析（分析脚本见文末“数据与代码可得性”）：",
         indent_cm=0.74)
    bullet(doc, "对 6 个有效样品作 Eₐ_high–厚度散点（4.25CS 已弃用、剔除）。最低 Eₐ_high"
                "（LRS 4.29CS=0.042、5.9CS=0.037）只出现在 0.02–0.022 cm 薄膜；玉米淀粉对照"
                "（0.06 cm）Eₐ_high≈0.21。→ 明确披露低 Eₐ 是“薄膜几何 + 材料家族”共同效应，"
                "不声称材料内禀。（图：Fig_pillar2_qc 面板 A）",
           bold_lead="厚度混淆作图：")
    bullet(doc, "对每条温度谱独立复算 lin-KK 时发现：数据解析器把文件虚部列原样读入（即真实 Im(Z)，"
                "容抗弧为负），而 KK 校验旧代码假设虚部为正幅值、用 Z=Zr−jZi，等于把每条谱翻成反因果共轭，"
                "使 lin-KK 残差被系统性抬高、产生大量假警告。修正为 Z=Zr+jZi（并裁去高频感性尾 Im(Z)>0）后，"
                "全样品 220 条谱 KK 警告由 133（60%）降为 0，μ_median 由 ~0.21–0.28 降至 ~0.005–0.012。",
           bold_lead="KK 方法学更正（关键）：")
    bullet(doc, "修正后 LRS 标志样品数据在主窗口与冷尾均 KK 干净（μ_median：主窗口 0.007、补充 0.005、"
                "冷尾 0.012，全部 « 0.2）。→ 标志样品的低 Eₐ 现有 KK 一致的数据背书；此前“KK 最脏”的担忧是"
                "符号 bug 伪影，已消除。Eₐ/σ 由 Rb 过零点拟合得到，与 KK 无关、数值不受影响。"
                "（见图 Fig_pillar2_qc 面板 B；按证据带的 KK 警告比例表见 SI）",
           bold_lead="结果：")
    bullet(doc, "手动与自动 Rb 偏差按证据带统计：5.9CS 主窗口中位 10.8%、冷尾最大 96.7%；"
                "4.29CS 主窗口中位 13.1%、冷尾最大 49.6%。→ 冷尾点仍因 Rb 抽取不一致降级至探索级（Exploratory，与 KK 无关的独立轴）。"
                "（Rb 门控表见 SI）",
           bold_lead="Rb 一致性门控：")
    para(doc, "小结：KK 与 Rb 是两条独立 QC 轴。修正 KK 符号后，强主张由“KK 一致 + 主窗口 Rb 一致 + 有界高温段 Eₐ”"
              "三重支撑；冷尾点按 Rb 不一致降级。主动暴露并修正方法学错误，是本框架主张治理的实例。",
         indent_cm=0.74, space_before=2)
    fig_path = ROOT / "figures" / "Fig_pillar2_qc.png"
    if fig_path.exists():
        pic = doc.add_paragraph()
        pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pic.add_run().add_picture(str(fig_path), width=Cm(16))
        caption(doc, "Fig_pillar2_qc　面板 A：Eₐ_high vs 厚度（4.25CS 已弃用剔除），最低 Eₐ 集中于"
                     "0.02–0.022 cm LRS 薄膜，体现厚度×家族混淆。面板 B：符号修正后逐温度 KK lin-KK 残差 "
                     "μ_median（○ 5.9CS、□ 4.29CS），全部远低于 0.2 阈值——数据 KK 一致（修正前因符号 bug 误报）。")
    callout(doc, "数据已回（2026-06）· Pillar 2 加固：厚膜对照证伪“几何赝象”",
            ["原计划用薄膜重复样消混淆；实际回来的是更强的证据——厚膜 LRS（0.070–0.074 cm，约 3 倍厚度）"
             "在 Stage0 同口径下 Eₐ_high 仍为 0.008–0.055 eV、σ 仍高、冷尾仍连续（KK 0 警告）。",
             "含义：低 Eₐ + 冷却韧性不随厚度消失 → 是材料家族属性，而非薄膜几何效应。已并入表 2。",
             "另已落实（无需新表征）：KK 符号 bug 修正、逐点 KK residual 复算、Eₐ_high vs 厚度作图、"
             "selected_rb_qc 门控表——见第 7 节 P1。",
             "诚实保留：藕粉冷尾分段 Eₐ_low 出现负值，属冷尾拟合赝象（非机制），冷尾仅作定性连续性讨论。"],
            status="done")

    # ---- 5 Pillar 3 ----
    heading(doc, "5　创新点 3：物理/QC 门控的 EIS 闭环执行", 1)
    para(doc, "在凹凸棒土体系内实现 BO+LLM 真实闭环，关键闭环指标如下："
              "闭环轮数为 6、来源全部为真实测量（6/6）、闭环有效性为“真实前瞻”，"
              "每轮均有建议哈希（suggestion hash）与时间戳（05-11→05-17）。",
         indent_cm=0.74)
    para(doc, "诚实的“非发现/非收敛”是本创新点的力量来源而非缺陷：绝对改进为 0、"
              "最终最优等于初始最优（最优为 Trial 1，R=0.186/N=1.029）、收敛未触发、"
              "几何修复计数为 7（8 个 trial 中 7 个受厚度静默回退（silent-fallback）影响，已事后修复并写入局限）。"
              "据此定位为“真实闭环执行证明 + 诚实零结果”，明确不写“收敛”“发现”。", indent_cm=0.74)
    para(doc, "演进：上述 6 轮回顾闭环为单目标 BO；2026-06 起 MOBO(ParEGO) + 真实 LLM 护栏已驱动 "
              "2 轮原生前瞻闭环（线 B，详见下框），构成“多轮原生前瞻执行链”。仍如实报告净改进为零、"
              "未超历史最优，不声称收敛或发现。", indent_cm=0.74)
    callout(doc, "数据已回（2026-06）· 线 B 真实前瞻 MOBO 闭环：诚实执行、未超基准",
            ["接线：优化闭环已接入 MOBO(ParEGO) + 真实 LLM 物理护栏（guardrail，OpenRouter gpt-5.4，temperature=0）。",
             "已执行 2 轮原生前瞻（均“冻结 + 推送盖戳 → 之后合成测量”，测量晚于冻结 1～2 天）："
             "R1 原始 MOBO 解 R=0.0285/N=0.9841 → LLM 物理修正 R=0.28/N=0.96；"
             "R2 原始解 R=0.245/N=0.923 → LLM 修正 R=0.42/N=1.02。",
             "结果（已追加至历史数据库，trial 9/10）：两轮综合得分均未超过历史最优"
             "（trial 1，R=0.186/N=1.029，得分≈−1.94）；R=0.42/N=1.02 探到低 Eₐ_high 区但综合得分仍较低。",
             "定位：这是“真实闭环执行 + 诚实零净改进”的又一前瞻证据，明确不写“收敛/发现/普适最优”。"
             "创新点 3 由“单轮回顾闭环”升级为“多轮原生前瞻执行链”，证据强度 B+ → A−（净改进仍为零，如实报告）。",
             "余项：线 B 第 3 轮 R=0.36/N=0.84 待测；数据齐后一次性重跑 S13/S14。"],
            status="done")
    embed_fig(doc, "Fig_lineB_arrhenius.png",
              "图 2　线 B 物理/QC 门控的 MOBO+LLM 前瞻闭环执行（2026-06）。面板 a：两轮原生前瞻配方的 "
              "ln σ 对 1000/T 曲线（R=0.28/N=0.96 为第 1 轮、R=0.42/N=1.02 为第 2 轮，均“冻结 + 推送盖戳 → 之后合成测量”）。"
              "面板 b：优化活动各轮的综合得分（越高越好）。新前瞻轮 T9/T10（橙）均低于历史最优 "
              "T1（绿色虚线，R=0.186/N=1.029）。这是“真实闭环执行 + 诚实零净改进”的前瞻证据，"
              "据此不声称收敛/发现/普适最优。")

    # ---- 6 Methods ----
    heading(doc, "6　方法", 1)
    heading(doc, "6.1　EIS 测量与处理（Stage0）", 2)
    para(doc, "处理流程：宽温 EIS → 质量审查 → KK → 体相电阻 Rb → 电导 σ → 分段 Arrhenius → 结果打包。"
              "KK 为警告级（非硬门禁）；几何采用实测厚度/面积；温序与手动 Rb 的 QC 按预注册的描述符定义执行。"
              "弛豫时间分布（DRT）以 max(G,0) 近似，仅作探索级。", indent_cm=0.74)
    heading(doc, "6.2　BO+LLM 闭环（Stage1）", 2)
    para(doc, "单目标 BO（高斯过程 + 期望改进 EI）为当前主闭环；多目标 MOBO(ParEGO) "
              "已实现并可选用。LLM 物理护栏经 OpenRouter（gpt-5.4，temperature=0、最大 8000 tokens）调用，"
              "记录提供方/模型/提示词 SHA256/token 数作为溯源（provenance）。"
              "设计变量为 R（酸/水摩尔比）、N（液/黏土质量比）；多目标为室温电导 σ_RT↑、高温段 Eₐ_high↓、冷尾超额活化能↓。",
         indent_cm=0.74)
    heading(doc, "6.3　统计与机制（Stage2/Stage3）", 2)
    para(doc, "Stage2 做证据清洗与机制种子导出；Stage3 经 S03–S14 全链路，真实 LLM + "
              "混合（hybrid）文献检索（OpenAlex），末端为确定性主张审计（S14）。权威投稿级输出为 "
              "2026-06-07 的 OpenRouter 发布快照（详见“数据与代码可得性”）。", indent_cm=0.74)
    heading(doc, "6.4　可复现与溯源", 2)
    para(doc, "前瞻主张遵循“测量前冻结 → git 提交 + 推送以盖服务器时间戳 → 再动手”的纪律。"
              "代码与配置使用相对路径，机器相关项经环境变量覆盖。", indent_cm=0.74)

    # ---- 7 Integrity & Limitations ----
    heading(doc, "7　诚信声明与局限（投稿前必修项）", 1)
    para(doc, "本节主动暴露并门控不确定性——在方法学型子刊，这是录用的加分项。", indent_cm=0.74)
    heading(doc, "7.1　P0：诚信/一致性（必修）", 2)
    bullet(doc, "原候选注册表在一次清理提交（commit 4b6ee61）中被误删；其预注册时间戳（2026-05-08）"
                "由保留的文件名时间戳与溯源记录重建，前瞻余量仅 1 天、5 选 2。据此主张降级为"
                "“LLM 排名候选在实验前被冻结并随后由宽温 EIS 验证（前瞻锚点为重建、已透明记录）”，"
                "并主打 04-17/04-19 的早期查询包与文献卡片作为“推理先于实验”的硬证据；"
                "线 A 完成后升级为原生通过。", bold_lead="时间锚点（timing anchor）透明化：")
    bullet(doc, "已弃用 4.25CS，但宽温性能汇总表仍含其行；须从图件/正文剔除或明确标注弃用理由，"
                "避免与已剔除的对标表不一致。",
           bold_lead="4.25CS 数据一致性：")
    bullet(doc, "明确 5.9CS 厚度 0.022 cm 为卡尺/SEM 实测，与 Stage1 的 0.022 几何回退（fallback）bug 无关；"
                "援引几何审计表（SI）并解释几何冲突旗标的处置。",
           bold_lead="几何巧合澄清：")
    heading(doc, "7.2　P1：创新点 2 科学加固（已用现有数据落实，见 4.2 节）", 2)
    bullet(doc, "已作 Eₐ_high–厚度散点（4.25CS 剔除）；明确低 Eₐ 是“薄膜几何 + 家族”共同效应，"
                "Main 主张限定为“可比薄膜几何下 LRS Eₐ_high 显著低于玉米淀粉对照”。已落实。",
           bold_lead="厚度混淆：")
    bullet(doc, "逐温度谱 KK 复算查明并修正了一处复数阻抗符号约定 bug（解析器输出真实 Im(Z)，旧 KK 代码却按"
                "正幅值再取负，致谱被翻成反因果共轭）。修正 Z=Zr+jZi + 高频感性尾裁剪后，全样 220 条谱 KK 警告"
                "由 133 降为 0、μ_median≈0.007。→ LRS 标志样品主窗口实为 KK 干净，强主张由“KK 一致 + 主窗口 Rb 一致 + "
                "有界高温段 Eₐ”支撑。（这是相对原计划的诚实更正：原以为高温窗口 KK 脏，实为方法学伪影。"
                "Eₐ/σ 与 KK 无关、数值不变；相关诊断脚本见“数据与代码可得性”，可复现。）",
           bold_lead="KK（关键方法学更正）：")
    bullet(doc, "改用非负最小二乘（NNLS），或明确“DRT 仅作探索级、不作机制证据”。", bold_lead="DRT：")
    heading(doc, "7.3　P2：创新点 3 措辞与代码对齐", 2)
    bullet(doc, "不写“收敛/发现”；BO 绝对改进为 0、最优仍为 Trial 1，据此定位为“执行证明 + 诚实零结果”；"
                "7 次几何修复写入 SI。", bold_lead="措辞：")
    bullet(doc, "第 4 轮（R4）改称“智能体/人工护栏复核”，除非补充真实 LLM API 调用记录"
                "（线 B 已具备模型 + 提示词哈希 + temperature=0）。", bold_lead="R4：")

    # ---- 8 Conclusion ----
    heading(doc, "8　结论与展望", 1)
    para(doc, "本工作以酸-黏土质子导体为母体系，给出一个受物理/QC/主张治理的智能体材料"
              "发现框架：证据约束迁移智能体选择/重组生物聚合物–黏土膜基元，冷却韧性描述符对"
              "韧性/非韧性体系具备区分力，物理/QC 门控的 BO+LLM 闭环如实报告诚实零结果，"
              "全程由确定性主张审计守门。其方法学贡献（主张阶梯 + 确定性审计 + 执行引擎门禁）"
              "为可信智能体材料发现提供了可复现范式。", indent_cm=0.74)
    para(doc, "升级路线（与本文并行推进的实验）：线 A（生物聚合物前瞻）将把创新点 1 提升至 A；"
              "线 B（真实前瞻 MOBO 闭环）将把创新点 3 提升至 A 并产出原生多目标 Pareto 前沿。"
              "两线均严格执行“测量前冻结 → 推送盖戳 → 再动手”。若两线证据到位，本文可由子刊"
              "升级转投 Nature Communications。", indent_cm=0.74)

    # ---- Figures ----
    heading(doc, "图件清单", 1)
    para(doc, "已就绪并嵌入正文的结果图：", indent_cm=0.74, space_after=2)
    for fid, desc in [
        ("图 1（§3，已嵌入）", "线 A 原生前瞻：Arrhenius ln σ–1000/T（LRS×2 厚膜 vs 淀粉×2）"
                          "+ 高温段活化能柱状对比（LRS≪淀粉，排名前瞻复现）。"),
        ("图 2（§5，已嵌入）", "线 B 闭环：两轮前瞻配方 Arrhenius + campaign 各轮综合得分"
                          "（新前瞻轮均低于历史最优，诚实零净改进）。"),
        ("Fig_pillar2_qc（§4.2，已嵌入）", "面板 A 高温段活化能–厚度散点（厚度×家族混淆）；"
                                       "面板 B 符号修正后逐温度 KK 残差（全部 « 0.2，数据 KK 一致）。"),
    ]:
        bullet(doc, desc, bold_lead=fid + "：")
    para(doc, "计划补充的示意/汇总图（schematic，待 AI 生成 + 矢量精修）：", indent_cm=0.74,
         space_before=4, space_after=2)
    for fid, desc in [
        ("Fig 架构", "智能体工作流与支撑架构（记忆/自省/心跳 + LLM 网关 + 主张审计门控）。"),
        ("Fig 治理", "主张治理示意：证据带划分与允许/禁止措辞裁决。"),
        ("Fig 排名稳定性", "迁移候选排名稳定性（top1=1.0、top3 Jaccard=1.0）。"),
        ("Fig 活化能对标", "高温段活化能基准对标（含厚度标注，对标 POP-2020/MFM-300(Cr)/母体系）。"),
    ]:
        bullet(doc, desc, bold_lead=fid + "：")

    heading(doc, "SI 大纲", 1)
    para(doc, "（以下括注为对应的数据/脚本文件名，便于复现；正文已不再内联文件名。）",
         size=9, color=RGBColor(0x88, 0x88, 0x88), indent_cm=0.74, space_after=2)
    for s in [
        "时间锚点重建说明与 git 取证（清理提交 commit 4b6ee61、文件名时间戳、1 天余量、5 选 2）。",
        "完整闭环指标（绝对改进为 0、7 次几何修复、局限清单）。",
        "逐温度 KK 残差表（kk_residual_per_temperature.csv，独立 lin-KK 复算）+ "
        "按证据带的 KK 警告比例（kk_warning_fraction_by_band_LRS.csv）+ Rb 一致性门控表"
        "（kk_rb_band_gating_table.csv，含手动与自动 Rb 对比）。",
        "高温段活化能 vs 厚度散点（ea_vs_thickness.csv / Fig_pillar2_qc 面板 A）与几何审计"
        "（geometry_audit_v2.csv，几何冲突处置）；4.25CS 弃用说明见 DEPRECATED_SAMPLES.md。",
        "主张审计完整裁决（允许/禁止措辞、各证据带）。",
        "线 A / 线 B 预注册包与推送时间戳（原生前瞻证据）。",
    ]:
        bullet(doc, s)

    # ---- References ----
    heading(doc, "参考文献", 1)
    para(doc, "（占位：以下为正文引用文献的占位条目，待按目标期刊格式补全卷期页与 DOI。）",
         size=9, color=RGBColor(0x88, 0x88, 0x88), indent_cm=0.0, space_after=4)
    refs = [
        "Schönleber, M.; Klotz, D.; Ivers-Tiffée, E. A method for improving the "
        "robustness of linear Kramers–Kronig validity tests. Electrochimica Acta 131, "
        "20–27 (2014). [lin-KK 方法]",
        "[POP-2020] 待补：多孔有机聚合物质子导体，报道 Eₐ≈0.039 eV（作者/期刊/年/卷期页/DOI 待补）。",
        "[MFM-300(Cr)] 待补：金属–有机框架质子导体，报道 Eₐ≈0.040 eV（出处待补）。",
        "[酸-黏土母体系 AiCE] 待补：本课题组/文献的凹凸棒土–海泡石酸-黏土质子导体（出处待补）。",
        "[综述-低温质子传导] 待补：固态质子导体低温性能退化机理综述（出处待补）。",
        "[BO 材料优化] 待补：贝叶斯优化用于材料配方/工艺优化的代表工作（出处待补）。",
        "[LLM 智能体材料发现] 待补：大语言模型/智能体驱动材料发现的代表工作（出处待补）。",
    ]
    for i, rf in enumerate(refs, 1):
        bullet(doc, rf, bold_lead=f"[{i}]  ")

    # ---- Data & Code availability ----
    heading(doc, "数据与代码可得性", 1)
    para(doc, "支撑本研究结论的原始 EIS 谱、处理产物（σ(T)/分段 Arrhenius）、闭环历史数据库、"
              "前瞻注册表与预注册包、以及全部分析/绘图脚本，均在项目仓库内按相对路径组织、可复现获取；"
              "关键脚本包括 KK 诊断/复算（kk_diagnostic.py、kk_verify_all.py）、Pillar 2 QC 工件"
              "（build_pillar2_qc_artifacts.py）与结果作图（plot_results.py）。前瞻主张的服务器时间戳"
              "由 git 提交/推送记录佐证。具体路径与版本将于投稿时整理为数据可得性声明。",
         indent_cm=0.74)

    para(doc, "——初稿 v1 结束（绿色框为已完成的原生前瞻批次；黄色框（若有）为待回插槽）——", size=9,
         color=RGBColor(0x99, 0x99, 0x99), align=WD_ALIGN_PARAGRAPH.CENTER, space_before=10)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT))
    print(f"[ok] wrote {OUT}")


if __name__ == "__main__":
    build()
