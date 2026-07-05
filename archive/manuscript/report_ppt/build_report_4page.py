# -*- coding: utf-8 -*-
"""Focused 4-page report deck (reuses styling helpers from build_report_ppt).

Page 1: one-sentence thesis + why-this-thesis
Page 2: agent increment (M6 -> M7/M8 upgraded three-stage evidence chain)
Page 3: Line A native prospective validation (with figure)
Page 4: Line B physics/QC-gated closed loop (with figure)

Run:  python manuscript/report_ppt/build_report_4page.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_report_ppt import (  # noqa: E402
    Presentation, Cm, Pt, RGBColor, PP_ALIGN, MSO_ANCHOR,
    NAVY, BLUE, TEAL, GREEN, ORANGE, GREY, LIGHT, WHITE, DARK,
    EMU_W, EMU_H, _set_cjk, add_text, textbox, rect, blank, title_bar, card, FIGDIR,
)

OUT = Path(__file__).resolve().parent / "report_4page.pptx"


def foot(slide, idx):
    tf = textbox(slide, Cm(1.2), EMU_H - Cm(1.0), EMU_W - Cm(2.4), Cm(0.7))
    add_text(tf, "Acid-in-clay · 受治理的智能体材料发现 · 汇报 2026-06-15", size=10, color=GREY)
    tf2 = textbox(slide, EMU_W - Cm(2.4), EMU_H - Cm(1.0), Cm(1.4), Cm(0.7))
    add_text(tf2, str(idx), size=10, color=GREY, align=PP_ALIGN.RIGHT)


def build():
    prs = Presentation()
    prs.slide_width = EMU_W
    prs.slide_height = EMU_H

    # ===================== Page 1: one-sentence thesis =====================
    s = blank(prs)
    rect(s, 0, 0, EMU_W, EMU_H, NAVY)
    rect(s, 0, EMU_H - Cm(6.6), EMU_W, Cm(6.6), RGBColor(0x18, 0x2C, 0x50))

    tf = textbox(s, Cm(1.8), Cm(2.4), EMU_W - Cm(3.6), Cm(1.2))
    add_text(tf, "文章立意 · 一句话", size=15, bold=True,
             color=RGBColor(0x9D, 0xC3, 0xE6))

    tf2 = textbox(s, Cm(1.8), Cm(3.7), EMU_W - Cm(3.6), Cm(6.5))
    add_text(tf2, "我们做的不是“用 AI 发现材料”，", size=30, bold=True, color=WHITE, space_after=2)
    add_text(tf2, "而是给 AI 材料发现装上“诚信的刹车与方向盘”——", size=30, bold=True,
             color=WHITE, new=True, space_after=2)
    add_text(tf2, "用酸-黏土质子导体这一真实体系，证明发现可溯源、判定可证伪、执行可治理。",
             size=26, bold=True, color=RGBColor(0xCF, 0xDD, 0xF0), new=True)

    tf3 = textbox(s, Cm(1.8), EMU_H - Cm(6.2), EMU_W - Cm(3.6), Cm(5.6))
    add_text(tf3, "为什么这样立意（三条理由）", size=15, bold=True,
             color=RGBColor(0x9D, 0xC3, 0xE6), space_after=6)
    for ln in [
        "1  瓶颈不在“模型不够强”，而在“不可信”——证据链与时间线不透明、主张普遍过度（发现/收敛/普适最优）。",
        "2  与其再造一个“更准的选材器”，不如把“受治理（governed）”当作第一性要求：每一步可溯源、有界、负面结果也照实写入。",
        "3  选酸-黏土做载体，是因为它有真实且未解的科学痛点（质子导体降温坍塌），逼着数字世界的推理落到可证伪的物理实验上。",
    ]:
        add_text(tf3, ln, size=14.5, color=RGBColor(0xDC, 0xE6, 0xF4), new=True, space_after=7)
    foot(s, 1)

    # ===================== Page 2: agent increment M6->M8 =====================
    s = blank(prs)
    y = title_bar(s, "智能体的真实增量 · 为什么做 + 关键发现",
                  "从消融到三阶段证据链（M6 → M7/M8）", TEAL)
    card(s, Cm(1.2), y, Cm(15.4), Cm(11.6), "为什么做（理由）",
         ["顶刊对“AI 发现材料”的第一刀：一个只挑高频组分的笨基线",
          "（流行度/随机）是不是也能得到同样结果？agent 的边际价值在哪？",
          "第二刀：你这到底算不算 agent，还是一次性 prompt 套壳？",
          "",
          "→ 必须用消融正面量化两件事：",
          "• agent 相对简单基线的增量；",
          "• agent 的闭环机制（记忆/自省/护栏）是否真实运转。",
          "",
          "做法（全部旁路、不碰主线、不做物理实验）：",
          "真 LLM(gpt-5.4)跑 S09 生成×多 seed，对比随机/流行度；",
          "向证据池注入高被引“离题干扰项”；再用独立模型跨家族盲评。"], TEAL)
    card(s, Cm(17.2), y, Cm(15.4), Cm(11.6), "关键发现（已升级 · 诚实）",
         ["① 生成阶段(M7) 杀手级抗干扰：注入 6 张高频离题卡后，",
          "   流行度基线 100% 崩盘，治理 agent 5/5 seed 纹丝不动",
          "   （干扰项纳入 0.00、on-topic 0.99、引用 100% 可溯源）。",
          "② 排序阶段(M8)：真 LLM 排序器把干扰项整体压到底部",
          "   （治理均分 0.704 vs 干扰 0.27，≈2.6×）。",
          "③ 跨模型盲评(M8)：异构评审(gemini-2.5-flash)匿名打分",
          "   治理 4.0/4.8 ≫ 随机 2.33/3.33 ≫ 流行度 1.0/1.0。",
          "④ 闭环机制(M8)：critic+memory 自纠，过度声称 40→0、",
          "   9 条记忆持久化——真组件、非套壳。",
          "",
          "锚点：护城河不是“选材准”，而是“在又宽又杂的噪声池里，",
          "只挑机理证据扎实的、抗住热度诱惑、全程可审计可自纠”。"], TEAL)
    tf = textbox(s, Cm(1.2), y + Cm(11.8), EMU_W - Cm(2.4), Cm(1.2))
    add_text(tf, "诚实边界：以上为冻结主线之后的旁路能力演示（与预注册证据分层、未改主线产物）；"
                 "方向性/机制性证据，非统计显著性；critic 为词面级护栏；不声称“发现 LRS/收敛/普适最优”。",
             size=11, color=GREY)
    foot(s, 2)

    # ===================== Page 3: Line A =====================
    s = blank(prs)
    y = title_bar(s, "线 A · 为什么做 + 进展", "生物聚合物迁移的原生前瞻验证", BLUE)
    tf = textbox(s, Cm(1.2), y, Cm(15.4), Cm(11.6))
    add_text(tf, "为什么做（理由）", size=15, bold=True, color=BLUE, space_after=4)
    for ln in ["把“冻结的 LLM 排名”用原生前瞻实验检验——回答审稿人",
               "“你到底先推理还是先实验”的硬证据（闭合创新点 ① + ②）。",
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
        tfc = textbox(s, Cm(17.0), y + Cm(8.0), Cm(15.6), Cm(2.4))
        add_text(tfc, "图：线 A Arrhenius + 活化能对比（LRS≪淀粉，排名前瞻复现）。"
                      "厚膜对照为跨批次（旧薄膜 vs 6 月新厚膜），列为 limitation。",
                 size=11, italic=True, color=GREY)
    foot(s, 3)

    # ===================== Page 4: Line B =====================
    s = blank(prs)
    y = title_bar(s, "线 B · 为什么做 + 进展", "物理/QC 门控的 BO+LLM 闭环执行", GREEN)
    tf = textbox(s, Cm(1.2), y, Cm(15.4), Cm(11.6))
    add_text(tf, "为什么做（理由）", size=15, bold=True, color=GREEN, space_after=4)
    for ln in ["价值不在“调出更好配方”，而在证明“物理/QC 门控的真实",
               "前瞻闭环”能跑通且不造假——“未超越”本身就是诚实素材",
               "（支撑创新点 ③）。",
               "",
               "进展（已回数据）：",
               "• 已执行前瞻配方（MOBO 原始解 → LLM 物理修正）；",
               "• 测量均晚于冻结/推送（盖服务器时间戳）= 原生前瞻；",
               "• 但综合得分未超过历史最优（诚实零净改进）。",
               "",
               "现状定位（如实）：",
               "“真实闭环执行 + 诚实零结果”——执行机制已跑通，",
               "尚未实现性能优化 / 闭环收敛，继续迭代中。"]:
        add_text(tf, ln, size=13, color=DARK, new=True)
    figB = FIGDIR / "Fig_lineB_arrhenius.png"
    if figB.exists():
        s.shapes.add_picture(str(figB), Cm(17.0), y + Cm(0.5), width=Cm(15.6))
        tfc = textbox(s, Cm(17.0), y + Cm(8.0), Cm(15.6), Cm(2.4))
        add_text(tfc, "图：线 B 两轮前瞻配方 Arrhenius + 各轮综合得分。"
                      "新前瞻轮（T9/T10）均低于历史最优 T1，如实呈现，不事后改分。",
                 size=11, italic=True, color=GREY)
    foot(s, 4)

    prs.save(str(OUT))
    print(f"[ok] wrote {OUT}  ({len(prs.slides)} slides)")


if __name__ == "__main__":
    build()
