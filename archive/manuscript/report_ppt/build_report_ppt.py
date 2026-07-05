# -*- coding: utf-8 -*-
"""Build the report slide deck (Chinese) for the acid-in-clay agentic discovery project.

Covers: paper thesis + 3 innovation points (with rationale), and the 3 ongoing
works (with rationale). Embeds the two result figures.

Run:  python manuscript/report_ppt/build_report_ppt.py
"""
from pathlib import Path

from pptx import Presentation
from pptx.util import Cm, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent
FIGDIR = ROOT.parent / "figures"
OUT = ROOT / "report_three_pillars.pptx"

# palette
NAVY = RGBColor(0x1F, 0x38, 0x64)
BLUE = RGBColor(0x2E, 0x5C, 0x9A)
TEAL = RGBColor(0x1F, 0x6F, 0x8B)
GREEN = RGBColor(0x14, 0x5A, 0x32)
ORANGE = RGBColor(0xB5, 0x65, 0x1D)
GREY = RGBColor(0x55, 0x55, 0x55)
LIGHT = RGBColor(0xF2, 0xF5, 0xFA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK = RGBColor(0x22, 0x22, 0x22)

CJK = "Microsoft YaHei"

EMU_W = Cm(33.867)
EMU_H = Cm(19.05)


def _set_cjk(run, name=CJK):
    run.font.name = name
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", name)


def add_text(tf_or_slide, text, *, size=18, bold=False, color=DARK, align=PP_ALIGN.LEFT,
             italic=False, space_after=6, level=0, new=False, para=None):
    """Add a paragraph of text to a text_frame."""
    tf = tf_or_slide
    if para is None:
        p = tf.paragraphs[0] if (len(tf.paragraphs) == 1 and not tf.paragraphs[0].runs and not new) else tf.add_paragraph()
    else:
        p = para
    p.alignment = align
    p.level = level
    p.space_after = Pt(space_after)
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    _set_cjk(r)
    return p


def textbox(slide, x, y, w, h):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    return tf


def rect(slide, x, y, w, h, fill, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
    sp.shadow.inherit = False
    return sp


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def title_bar(slide, kicker, title, accent=NAVY):
    """Top accent bar + kicker + title. Returns y where body can start."""
    rect(slide, 0, 0, EMU_W, Cm(0.35), accent)
    tf = textbox(slide, Cm(1.2), Cm(0.7), EMU_W - Cm(2.4), Cm(1.0))
    add_text(tf, kicker, size=13, bold=True, color=accent, space_after=0)
    tf2 = textbox(slide, Cm(1.2), Cm(1.5), EMU_W - Cm(2.4), Cm(1.8))
    add_text(tf2, title, size=27, bold=True, color=DARK, space_after=0)
    return Cm(3.5)


def footer(slide, idx):
    tf = textbox(slide, Cm(1.2), EMU_H - Cm(1.0), EMU_W - Cm(2.4), Cm(0.7))
    add_text(tf, "Acid-in-clay  ·  受治理的智能体材料发现  ·  汇报 2026-06-15", size=10, color=GREY)
    tf2 = textbox(slide, EMU_W - Cm(2.4), EMU_H - Cm(1.0), Cm(1.4), Cm(0.7))
    add_text(tf2, str(idx), size=10, color=GREY, align=PP_ALIGN.RIGHT)


def chip(slide, x, y, w, text, color):
    """A small rounded label chip."""
    sp = rect(slide, x, y, w, Cm(0.95), color)
    tf = sp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = text
    r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = WHITE
    _set_cjk(r)
    return sp


def card(slide, x, y, w, h, title, lines, accent):
    """A panel card with colored header strip + bullet lines."""
    rect(slide, x, y, w, h, LIGHT)
    rect(slide, x, y, w, Cm(0.12), accent)
    tf = textbox(slide, x + Cm(0.3), y + Cm(0.25), w - Cm(0.6), Cm(1.0))
    add_text(tf, title, size=15, bold=True, color=accent, space_after=2)
    body = textbox(slide, x + Cm(0.3), y + Cm(1.15), w - Cm(0.6), h - Cm(1.4))
    first = True
    for ln in lines:
        add_text(body, ln, size=12.5, color=DARK, space_after=5, new=not first)
        first = False


# --------------------------------------------------------------------------- #
def build():
    prs = Presentation()
    prs.slide_width = EMU_W
    prs.slide_height = EMU_H

    # ---------- 1. Title ----------
    s = blank(prs)
    rect(s, 0, 0, EMU_W, EMU_H, NAVY)
    rect(s, 0, EMU_H - Cm(6.2), EMU_W, Cm(6.2), RGBColor(0x18, 0x2C, 0x50))
    tf = textbox(s, Cm(1.6), Cm(3.2), EMU_W - Cm(3.2), Cm(2.0))
    add_text(tf, "受证据约束、主张受审计的智能体材料发现", size=20, bold=True,
             color=RGBColor(0x9D, 0xC3, 0xE6), space_after=0)
    tf2 = textbox(s, Cm(1.6), Cm(4.6), EMU_W - Cm(3.2), Cm(5.0))
    add_text(tf2, "把酸-黏土质子传导原理", size=34, bold=True, color=WHITE, space_after=2)
    add_text(tf2, "迁移到冷却韧性的生物聚合物–黏土膜", size=34, bold=True, color=WHITE, new=True)
    tf3 = textbox(s, Cm(1.6), EMU_H - Cm(5.6), EMU_W - Cm(3.2), Cm(4.5))
    add_text(tf3, "连接物理世界（EIS 实验）与数字世界（LLM / 贝叶斯优化 智能体）的一条可审计链路",
             size=16, color=RGBColor(0xCF, 0xDD, 0xF0), space_after=10)
    add_text(tf3, "汇报人：JZ        日期：2026-06-15", size=14, color=RGBColor(0x9D, 0xC3, 0xE6), new=True)

    # ---------- 2. Background / why this project ----------
    s = blank(prs)
    y = title_bar(s, "研究背景 · 为什么做这个课题", "两个真实痛点交汇")
    card(s, Cm(1.2), y, Cm(15.4), Cm(11.5), "痛点一 · 科学问题（物理世界）",
         ["固态质子导体在燃料电池、传感、离子电子学中应用广泛。",
          "",
          "但电导率在降温时常因质子通路结构重排、局部冻结而显著退化，",
          "形成“高室温电导、低温脆弱”的普遍困境。",
          "",
          "→ 如何设计在冷却过程中仍保持质子通路连续性的材料，",
          "    是该领域的关键科学问题。"], TEAL)
    card(s, Cm(17.2), y, Cm(15.4), Cm(11.5), "痛点二 · 可信性危机（数字世界）",
         ["“用 AI 自主发现新材料”成为热点，但两类可信性问题未解决：",
          "",
          "(i) 证据链与时间线不透明 —— 难以向审稿人证明",
          "     “AI 先推理、实验后验证”的真实顺序；",
          "",
          "(ii) 主张过度 —— 把数学建议 / 回溯拟合 / 偶发最优",
          "      误述为“发现”“收敛”“普适最优”。",
          "",
          "→ 缺的不是“更强模型”，而是“可被治理与审计”的发现流程。"], ORANGE)
    footer(s, 2)

    # ---------- 3. Core idea / thesis ----------
    s = blank(prs)
    y = title_bar(s, "核心思路 · 文章立场", "把“受治理”作为智能体材料发现的第一性要求")
    tf = textbox(s, Cm(1.2), y, EMU_W - Cm(2.4), Cm(2.4))
    add_text(tf, "我们以酸-黏土质子导体为母体系，构建并实现一个端到端、单向、可审计的"
                 "“发现 → 执行 → 审计”框架：让大语言模型/优化器的每一步都有据可溯、有界可控、"
                 "负面结果也被如实写入证据，而非掩盖。", size=16, color=DARK, space_after=4)
    chips = [("① 发现从哪来？\n证据约束迁移智能体", TEAL),
             ("② 判定对不对？\n冷却韧性通路连续性描述符", BLUE),
             ("③ 执行可信吗？\n物理/QC 门控的闭环执行 + 主张审计", GREEN)]
    cw = Cm(10.0); gap = Cm(0.7); x0 = Cm(1.2)
    for i, (txt, col) in enumerate(chips):
        x = x0 + i * (cw + gap)
        sp = rect(s, x, y + Cm(3.0), cw, Cm(3.4), col)
        tf2 = sp.text_frame; tf2.word_wrap = True; tf2.vertical_anchor = MSO_ANCHOR.MIDDLE
        for j, line in enumerate(txt.split("\n")):
            p = tf2.paragraphs[0] if j == 0 else tf2.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run(); r.text = line
            r.font.size = Pt(15 if j == 0 else 14); r.font.bold = (j == 0)
            r.font.color.rgb = WHITE; _set_cjk(r)
    tf3 = textbox(s, Cm(1.2), y + Cm(6.8), EMU_W - Cm(2.4), Cm(3.0))
    add_text(tf3, "这三问恰好把物理世界（EIS 实验证据）与数字世界（智能体推理/优化）"
                  "用一条可审计的链路连接起来 —— 这就是本文的灵魂，也是方法学型子刊最稀缺的贡献：",
             size=15, color=DARK, space_after=4)
    add_text(tf3, "主动“门控并写入”不确定性与负面结果，而不是掩盖。", size=16, bold=True,
             color=NAVY, new=True)
    footer(s, 3)

    # ---------- 4. Why these three (rationale) ----------
    s = blank(prs)
    y = title_bar(s, "为什么是这三个创新点", "它们是“可信 AI 材料发现”必须递进回答的三问")
    rows = [
        ("①", "证据约束迁移智能体", TEAL,
         "回答“发现从哪来、可信吗”：来源可溯（真实 LLM + 真实文献），推理时间戳早于实验。"
         "诚实定位为“选择并重组”，不声称独立发现。"),
        ("②", "冷却韧性通路连续性描述符", BLUE,
         "回答“判定对不对”：给出一个可证伪的物理判据，能在同等几何/QC 下区分"
         "韧性（LRS 正验证）与非韧性（壳聚糖 边界坍塌）。"),
        ("③", "物理/QC 门控的 EIS 闭环执行", GREEN,
         "回答“执行可信吗”：真实 BO+LLM 前瞻闭环，硬门禁 + 确定性主张审计守门，"
         "如实报告“未收敛/未超越”的诚实零结果。"),
    ]
    yy = y
    for num, name, col, why in rows:
        sp = rect(s, Cm(1.2), yy, Cm(1.5), Cm(3.0), col)
        tfn = sp.text_frame; tfn.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tfn.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = num; r.font.size = Pt(28); r.font.bold = True
        r.font.color.rgb = WHITE; _set_cjk(r)
        rect(s, Cm(2.9), yy, EMU_W - Cm(4.1), Cm(3.0), LIGHT)
        tfb = textbox(s, Cm(3.2), yy + Cm(0.2), EMU_W - Cm(4.6), Cm(2.7))
        add_text(tfb, name, size=17, bold=True, color=col, space_after=2)
        add_text(tfb, why, size=13.5, color=DARK, new=True)
        yy += Cm(3.4)
    tf = textbox(s, Cm(1.2), yy + Cm(0.1), EMU_W - Cm(2.4), Cm(1.6))
    add_text(tf, "三点合起来 = 发现（可溯）→ 验证（可证伪）→ 执行（可治理）的完整闭环，"
                 "正是子刊看重的“系统级方法学贡献”。", size=14, bold=True, color=NAVY)
    footer(s, 4)

    # ---------- 5. Pillar 1 ----------
    s = blank(prs)
    y = title_bar(s, "创新点 ① · 是什么 + 为什么", "证据约束迁移智能体", TEAL)
    card(s, Cm(1.2), y, Cm(15.4), Cm(11.3), "是什么",
         ["真实链路（代码层存在）：证据 → 假设 → 机制仲裁 → 描述符 →",
          "文献侦察（OpenAlex 真实接口）→ 候选家族 → 确定性重排 →",
          "前瞻注册 → 验证绑定 → 主张审计。",
          "",
          "具备真正的智能体支撑架构：记忆（仅追加、确定性回放）、",
          "自省（生成–批判–修订）、心跳、LLM 网关（temperature=0、模式校验）。",
          "",
          "从广义文献池“选择并重组”出莲藕淀粉（LRS）、壳聚糖（CHITO）",
          "等生物聚合物–黏土膜基元。"], TEAL)
    card(s, Cm(17.2), y, Cm(15.4), Cm(11.3), "为什么需要它",
         ["材料创新的第一道坎是“可信的灵感来源”：",
          "审稿人会问——智能体相对“读了同样几篇文献的专家”，多给了什么？",
          "",
          "答：把发现做成可溯、可复现、可审计的流程：",
          "• 推理时间戳早于实验（先推理后实验的硬证据）；",
          "• 主张上限被硬钉在“选择/重组”，禁止“独立发现”；",
          "• 候选实验前被冻结，事后由宽温 EIS 验证。",
          "",
          "→ 它把“AI 选材”从口号变成可被检验的证据链。"], TEAL)
    footer(s, 5)

    # ---------- 6. Pillar 2 ----------
    s = blank(prs)
    y = title_bar(s, "创新点 ② · 是什么 + 为什么", "冷却韧性描述符（可证伪的区分判据）", BLUE)
    card(s, Cm(1.2), y, Cm(15.4), Cm(11.3), "是什么（预注册多条件判据）",
         ["对分段电导做 Arrhenius 拟合（AICc 选段，段数 ≤ 3）。",
          "“冷却韧性”需同时满足（阈值预注册、未事后改）：",
          "• 高温段 Eₐ 低（LRS ~0.05 eV，淀粉 ~0.11–0.17 eV）；",
          "• 冷尾电导保留率高（σ233/273：LRS ~0.30 vs 壳聚糖 ~0.004）；",
          "• 结论建立在 KK 通过的高温段数据上（通过率 100%）。",
          "",
          "区分力的硬事实：到 233 K，壳聚糖电导坍塌近 2 个数量级",
          "（σ233≈5e-5），而 LRS 仍保留约三成（σ233≈1e-2）。",
          "→ LRS 正验证 CONFIRMED；壳聚糖 边界验证 CONFIRMED。"], BLUE)
    card(s, Cm(17.2), y, Cm(15.4), Cm(11.3), "为什么需要它 + 诚实边界",
         ["“低温性能好”若只看室温电导，无法判定、无法证伪。",
          "需要一个可证伪、可门控、可迁移的物理判据：",
          "• 正例（LRS）与反例（壳聚糖坍塌）都要给出；",
          "• 与 EIS 质量控制绑定，避免把噪声当机制。",
          "",
          "如实交代的边界（写进正文/SI）：",
          "• 区分靠“冷尾电导坍塌”，非“势垒发散”（壳聚糖冷段 Eₐ≈0.64）；",
          "• 冷尾分段 Eₐ 有拟合赝象，只作定性参考；",
          "• 厚度对照为跨批次（旧薄膜 vs 新厚膜），列为 limitation。"], BLUE)
    footer(s, 6)

    # ---------- 7. Pillar 3 ----------
    s = blank(prs)
    y = title_bar(s, "创新点 ③ · 是什么 + 为什么", "物理/QC 门控的 EIS 闭环执行", GREEN)
    card(s, Cm(1.2), y, Cm(15.4), Cm(11.3), "是什么",
         ["在凹凸棒土体系内实现真实的 BO+LLM 闭环执行：",
          "贝叶斯优化 / 多目标 MOBO 给配方建议 → LLM 物理护栏修正 →",
          "合成测量 → QC 门控 → 写回历史库 → 再建议下一轮。",
          "",
          "执行受一组硬门禁约束：仅追加写入、哈希绑定人工批准、",
          "批准前禁写、评分门控、确定性主张审计（禁止过度声称）。",
          "",
          "如实报告“未收敛、未超越初始点”的诚实零结果。"], GREEN)
    card(s, Cm(17.2), y, Cm(15.4), Cm(11.3), "为什么需要它",
         ["“AI 闭环优化”最容易被质疑造假 / 过度声称。",
          "",
          "本创新点的力量恰恰来自诚实：",
          "• 真实闭环（每轮有建议哈希 + 服务器时间戳）；",
          "• 零结果也照实写（绝对改进 = 0，最优仍是初始点）；",
          "• 确定性审计器硬性拒绝“发现/收敛/普适最优”。",
          "",
          "→ 证明的是“可信的执行机制”，不是“运气好的结果”。",
          "    这正是方法学型子刊的加分项。"], GREEN)
    footer(s, 7)

    # ---------- 8. Current work overview ----------
    s = blank(prs)
    y = title_bar(s, "目前在推进的三项工作", "每项工作对应一个创新点的“升级证据”")
    work = [
        ("工作 A · 智能体消融（M6）", TEAL, "创新点 ①",
         "量化“智能体相对简单基线的增量”，回应审稿人对 agent 价值的核心质疑。"),
        ("工作 B · 线 A 前瞻验证", BLUE, "创新点 ① + ②",
         "原生前瞻验证迁移候选；已测 LRS + 淀粉，尚缺壳聚糖（边界对照）。"),
        ("工作 C · 线 B 闭环执行", GREEN, "创新点 ③",
         "真实前瞻 BO+LLM 闭环；已测前瞻样品，尚未实现性能优化 / 闭环收敛。"),
    ]
    yy = y
    for name, col, maps, desc in work:
        rect(s, Cm(1.2), yy, EMU_W - Cm(2.4), Cm(3.0), LIGHT)
        rect(s, Cm(1.2), yy, Cm(0.18), Cm(3.0), col)
        tfn = textbox(s, Cm(1.7), yy + Cm(0.25), Cm(13.0), Cm(2.6))
        add_text(tfn, name, size=17, bold=True, color=col, space_after=2)
        add_text(tfn, desc, size=13.5, color=DARK, new=True)
        chip(s, EMU_W - Cm(6.4), yy + Cm(1.0), Cm(4.8), "支撑 " + maps, col)
        yy += Cm(3.5)
    tf = textbox(s, Cm(1.2), yy, EMU_W - Cm(2.4), Cm(1.2))
    add_text(tf, "共同纪律：所有前瞻实验都遵循“测量前冻结 → git 提交并推送盖时间戳 → 再动手”。",
             size=14, bold=True, color=NAVY)
    footer(s, 8)

    # ---------- 9. Work A: M6 ablation ----------
    s = blank(prs)
    y = title_bar(s, "工作 A · 为什么做 + 关键发现", "智能体基线消融（M6）", TEAL)
    card(s, Cm(1.2), y, Cm(15.4), Cm(11.3), "为什么做（理由）",
         ["子刊系统创新口要求量化“agent 的增量”：",
          "如果一个“读了同样文献的专家”也能得到一样的候选，",
          "那 agent 的价值何在？必须用消融正面回答。",
          "",
          "做法（不做实验、只读冻结产物 + 纯计算）：",
          "• 对比 随机 / 流行度 / 裸 LLM / 完整治理 agent；",
          "• 权重留一消融 + 200 seed 扰动稳健性；",
          "• 扩大候选池到数百，掺入真实高被引“离题干扰”。"], TEAL)
    card(s, Cm(17.2), y, Cm(15.4), Cm(11.3), "关键发现（诚实）",
         ["• “选中 LRS”不是护城河 —— 纯组分流行度也能选中第一。",
          "",
          "• 真正的增量在“构造可证伪对照对”：只有治理 agent 能",
          "   把“赢家 + 边界”同时放进前二（100% vs 基线 0–16%）。",
          "",
          "• 抗干扰是分水岭：宽池掺高被引离题项后，",
          "   流行度翻车（赢家被挤到 295/752），agent 守住第 1、",
          "   top-10 零离题污染。",
          "",
          "→ 叙事锚点：agent 价值 = 可证伪对照 + 可复现治理 + 抗噪，",
          "    而非“选材准”。"], TEAL)
    footer(s, 9)

    # ---------- 10. Work B: Line A (with figure) ----------
    s = blank(prs)
    y = title_bar(s, "工作 B · 为什么做 + 进展", "线 A：生物聚合物迁移的原生前瞻验证", BLUE)
    tf = textbox(s, Cm(1.2), y, Cm(15.4), Cm(11.5))
    add_text(tf, "为什么做（理由）", size=15, bold=True, color=BLUE, space_after=4)
    for ln in ["闭合创新点 ① + ②：把“冻结的排名”用原生前瞻实验检验。",
               "",
               "进展（已回数据，2026-06）：",
               "• 冻结于 06-07 → 06-11~15 合成测量（晚 4–8 天）= 原生前瞻；",
               "• LRS（藕粉）Eₐ 低 0.008–0.055 eV，显著优于淀粉 0.11–0.17 eV；",
               "• 智能体“LRS 优于淀粉”的排名被前瞻复现；",
               "• 厚膜（0.07 cm）仍低 Eₐ → 证伪“薄膜几何赝象”。",
               "",
               "尚缺：壳聚糖（CHITO）边界对照样 —— 它是描述符“区分力”",
               "的关键反例，补齐后“正验证 + 边界验证”的对照对才闭合。"]:
        add_text(tf, ln, size=13, color=(ORANGE if ln.startswith("尚缺") else DARK),
                 bold=ln.startswith("尚缺"), new=True)
    figA = FIGDIR / "Fig_lineA_arrhenius.png"
    if figA.exists():
        s.shapes.add_picture(str(figA), Cm(17.0), y + Cm(0.5), width=Cm(15.6))
        tfc = textbox(s, Cm(17.0), y + Cm(8.0), Cm(15.6), Cm(2.0))
        add_text(tfc, "图：线 A Arrhenius + 活化能对比（LRS≪淀粉，排名前瞻复现；厚膜对照）。",
                 size=11, italic=True, color=GREY)
    footer(s, 10)

    # ---------- 11. Work C: Line B (with figure) ----------
    s = blank(prs)
    y = title_bar(s, "工作 C · 为什么做 + 进展", "线 B：物理/QC 门控的 BO+LLM 闭环执行", GREEN)
    tf = textbox(s, Cm(1.2), y, Cm(15.4), Cm(11.5))
    add_text(tf, "为什么做（理由）", size=15, bold=True, color=GREEN, space_after=4)
    for ln in ["支撑创新点 ③：提供真实前瞻闭环执行的证据。",
               "",
               "进展（已回数据）：",
               "• 已执行前瞻配方（MOBO 原始解 → LLM 物理修正）；",
               "• 测量均晚于冻结/推送（盖服务器时间戳）= 原生前瞻；",
               "• 但综合得分未超过历史最优（诚实零净改进）。",
               "",
               "现状定位（如实）：",
               "“真实闭环执行 + 诚实零结果”——已跑通执行机制，",
               "但尚未实现性能优化 / 闭环收敛，继续迭代中。",
               "这一“未超越”本身就是创新点 ③ 的诚实素材。"]:
        add_text(tf, ln, size=13, color=DARK, new=True)
    figB = FIGDIR / "Fig_lineB_arrhenius.png"
    if figB.exists():
        s.shapes.add_picture(str(figB), Cm(17.0), y + Cm(0.5), width=Cm(15.6))
        tfc = textbox(s, Cm(17.0), y + Cm(8.0), Cm(15.6), Cm(2.0))
        add_text(tfc, "图：线 B 两轮前瞻配方 Arrhenius + 各轮综合得分"
                      "（新前瞻轮均低于历史最优，诚实呈现）。",
                 size=11, italic=True, color=GREY)
    footer(s, 11)

    # ---------- 12. Summary / next ----------
    s = blank(prs)
    rect(s, 0, 0, EMU_W, EMU_H, NAVY)
    tf = textbox(s, Cm(1.6), Cm(1.6), EMU_W - Cm(3.2), Cm(2.0))
    add_text(tf, "小结与下一步", size=30, bold=True, color=WHITE)
    card2_y = Cm(4.2)
    sumtf = textbox(s, Cm(1.6), card2_y, Cm(31.0), Cm(6.0))
    for ln in ["一句话：用一条可审计链路，把“酸-黏土质子传导原理”迁移到“冷却韧性生物聚合物膜”，",
               "并对发现、验证、执行全程做物理/QC/主张治理。",
               "",
               "三个创新点 = 发现可溯（迁移智能体）→ 判定可证伪（韧性描述符）→ 执行可治理（闭环 + 审计）。"]:
        add_text(sumtf, ln, size=16, color=RGBColor(0xDC, 0xE6, 0xF4),
                 new=(ln != "一句话：用一条可审计链路，把“酸-黏土质子传导原理”迁移到“冷却韧性生物聚合物膜”，"))
    nx = textbox(s, Cm(1.6), Cm(11.0), Cm(31.0), Cm(6.0))
    add_text(nx, "下一步", size=18, bold=True, color=RGBColor(0x9D, 0xC3, 0xE6), space_after=6)
    for ln in ["• 工作 A：（可选）用 key 让 LLM 真正跑一次候选生成，把创新点 ① 从“声称”推向“实证”。",
               "• 工作 B：补壳聚糖边界对照样，闭合“正验证 + 边界验证”。",
               "• 工作 C：继续前瞻闭环迭代；数据齐后重跑下游验证绑定 + 主张审计。",
               "• 论文：图像（架构/治理示意）完成后与初稿合并，补全参考文献，形成完整初稿。"]:
        add_text(nx, ln, size=15, color=WHITE, new=True, space_after=6)

    prs.save(str(OUT))
    print(f"[ok] wrote {OUT}  ({len(prs.slides)} slides)")


if __name__ == "__main__":
    build()

