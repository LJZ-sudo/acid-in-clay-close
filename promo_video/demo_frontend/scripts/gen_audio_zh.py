"""Generate CHINESE narration MP3s (edge-tts) for the Chinese-dub version.

Voice: zh-CN-YunjianNeural (mature Mandarin documentary male), the same family
used by the original Chinese cut. Output goes to src/assets/audio_zh/ so it does
NOT overwrite the English mp3s in src/assets/audio/. App.jsx serves audio_zh/
when ?lang=zh is selected.

IMPORTANT: NARRATION below MUST stay identical (character for character) to the
joined subs.zh[] sentences in src/App.jsx. Those exact sentences are shown as
the on-screen subtitle and used to time it, so any drift desyncs voice<->caption.

Usage:
  python scripts/gen_audio_zh.py                                  # default Yunjian +8%
  python scripts/gen_audio_zh.py --voice zh-CN-YunxiNeural --rate +0%
  python scripts/gen_audio_zh.py --only hook
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import edge_tts

OUT_DIR = Path(__file__).resolve().parents[1] / "src" / "assets" / "audio_zh"

# scene_id -> spoken text == "".join(subs.zh) in src/App.jsx (keep in sync!)
NARRATION = {
    "hook": "在工业与科研中，AI 常常被困在屏幕里。它能思考，却很难真正动手。FactoryLab 要把 AI 的推理，连接到物理世界。它在数字世界里想清楚一种新材料，再到现实里把它做出来、测出来。",
    "overview": "这就是 FactoryLab 的 AIAF 操作系统。它把任何工业发现拆成闭环：观测、理解、仿真授权、执行、反馈学习。每个环节，都由专门的智能体、标准化能力和真实执行单元完成。别人止步于示意图，我们把整条闭环真正跑通。",
    "capability": "支撑这条闭环的，是一整套通用的工程能力。它让 AI 拿到对的信息、按流程稳定执行、把每项技能像工具一样复用。还能自我检查、全程留痕、随时回滚——不绑定任何单一行业。今天发现一种新材料，明天就能迁移到电子、化工、医药。",
    "material": "数字世界的第一个成果——新材料。过去找一种新材料，往往要反复试错、耗上几个月。如今智能体在海量文献与配方组合中推理，筛出最有潜力的候选。而每一个结论都证据可追溯、结果可复现、全程可审计。",
    "physical": "数字世界选出的候选，立刻进入物理世界。真实的电化学工作站，真实的宽温阻抗谱测量，从常温一路降到极低温。这是 AI 的想法，第一次变成手里能测到的数据。",
    "mechanism": "在物理世界里，我们还发现了一个新机理。同样的体系，有的材料一到极端低温就失效，有的却依然顺畅导电。AI 找到了背后的原因，并把它变成一把能迁移到别的材料的标尺。让材料在零下八十度还能稳定导电，正是极端低温、极端环境场景最稀缺的硬能力。",
    "closedloop": "数字与物理，如今连成了一条闭环，一轮接一轮地迭代。AI 提出配方，自动合成、自动测量，数据实时回流，AI 随即再优化。每一步高风险动作，都先仿真、再授权、后执行，全程可追溯。每迭代一轮，它就更聪明一分——这是一台能不断进化、并可复制到更多产线与材料的发现引擎。",
    "outro": "你刚刚看到的质子导体项目，只是 FactoryLab 能力库里的一个落点。它背后是同一套可复用能力——从项目，泛化到企业、园区，乃至整个行业。覆盖材料、电芯、PACK、制造、测试到回收的完整链路。FactoryLab，让工业知识变成可调用、可验证、可执行的产业能力。",
}


async def synth(scene_id: str, text: str, voice: str, rate: str, retries: int = 5) -> None:
    out = OUT_DIR / f"{scene_id}.mp3"
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
            await communicate.save(str(out))
            size = out.stat().st_size
            if size < 2048:
                raise RuntimeError(f"tiny output ({size} bytes)")
            print(f"  [ok] {out.name}  ({size // 1024} KB)")
            return
        except Exception as exc:  # transient edge-tts/network failures
            last_err = exc
            print(f"  [retry {attempt}/{retries}] {scene_id}: {exc}")
            await asyncio.sleep(2.0 * attempt)
    print(f"  [FAIL] {scene_id}: {last_err}", file=sys.stderr)


async def main(voice: str, rate: str, only: str | None) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"voice={voice} rate={rate} -> {OUT_DIR}")
    items = NARRATION.items() if not only else [(only, NARRATION[only])]
    for scene_id, text in items:
        await synth(scene_id, text, voice, rate)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="zh-CN-YunjianNeural")
    ap.add_argument("--rate", default="-2%")  # slightly slower than natural for clearer narration
    ap.add_argument("--only", default=None, help="only this scene id")
    args = ap.parse_args()
    asyncio.run(main(args.voice, args.rate, args.only))
