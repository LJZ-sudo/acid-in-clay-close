"""[LEGACY] Chinese narration generator that writes to src/assets/audio/.

!!! WARNING !!!  This writes into src/assets/audio/, which now holds the ENGLISH
dub. Running it WILL OVERWRITE the English mp3s. For the Chinese-dub version use
`scripts/gen_audio_zh.py` instead — it writes to src/assets/audio_zh/ and its text
is kept in sync with the on-screen subtitle (subs.zh). This file is retained only
for reference; its NARRATION below is an older long-form Chinese script that does
NOT match the current subtitles.

Usage (only if you intentionally want to regenerate the English-slot dir):
    python scripts/gen_audio.py [--voice zh-CN-YunxiNeural] [--rate +0%]
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import edge_tts

# scene_id -> spoken text. Must match App.jsx SCENES[].narration.
NARRATION = {
    "hook": "在工业和科研里，AI 常常停在屏幕里——它能想，却很难真正动手。FactoryLab 要做的，就是把 AI 的思考连到真实世界：让它在数字世界里想清楚一个材料，再到物理世界里，把它真正做出来、测出来。",
    "overview": "这就是 FactoryLab 的 AIAF 操作系统。它把任何一个工业发现，拆成一条闭环：观测、理解、仿真授权、执行、再到反馈学习。每个环节，都由专门的智能体、标准化的能力，和真实的执行单元来完成。别人停在示意图，我们把整条闭环真正跑通了。",
    "capability": "更重要的是，支撑这条闭环的，是一整套通用的工程能力——让 AI 拿到对的信息、按标准流程稳定执行、把每一项技能像工具一样反复调用，还能自我检查、全程留痕、随时回滚。它们不绑定某一种测量、某一个行业；今天用来发现一种新材料，明天就能迁移到电子、化工、医药等各类制造场景。",
    "material": "先看数字世界的第一个成果——新材料。过去找一种新材料，往往要靠经验反复试错、耗上几个月；现在，智能体从海量文献和配方组合里自主推理，很快就筛出最有潜力的一批新材料，并给出清晰的排名。更关键的是，每一个结论都证据可追溯、结果可复现、全程可审计。",
    "physical": "数字世界选出的候选，立刻进入物理世界。真实的电化学工作站，真实的宽温阻抗谱测量，从常温一路降到极低温——这是 AI 的想法，第一次变成手里能测到的数据。",
    "mechanism": "在物理世界里，我们还发现了一个新机理。同样的体系，有的材料一到极端低温就罢工，有的却依然顺畅导电。AI 帮我们找到了背后的原因，并把它变成一把能迁移到别的材料的标尺。说得直白点——让材料在零下八十度还能导电，正是寒区电池、极端环境器件这类高价值场景，最需要的硬能力。",
    "closedloop": "数字与物理，就这样真实地来回迭代了六轮。AI 提出配方，自动合成与测量，数据回流，AI 再优化——每一步高风险动作，都先仿真、再授权、后执行，全程留痕。闭环一旦跑通，每一轮实验都在为下一次性能突破累积资产。这，就是一条能不断进化、可以规模化复制的发现闭环。",
    "outro": "其实，你刚刚看到的这个质子导体项目，只是 FactoryLab 能力库里的一个落点。它背后是同一套可复用的能力，能从一个项目，泛化到一家企业、一个园区，乃至整个行业——覆盖材料、电芯、PACK、制造、测试到回收的完整链路。FactoryLab，让工业知识真正变成可调用、可验证、可执行的产业能力。",
}

OUT_DIR = Path(__file__).resolve().parents[1] / "src" / "assets" / "audio"


async def synth(scene_id: str, text: str, voice: str, rate: str, retries: int = 5) -> None:
    out = OUT_DIR / f"{scene_id}.mp3"
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
            await communicate.save(str(out))
            if out.stat().st_size > 1024:
                print(f"  [ok] {out.name}  ({out.stat().st_size // 1024} KB)")
                return
            raise RuntimeError("empty output")
        except Exception as exc:  # transient edge-tts/network failures
            last_err = exc
            print(f"  [retry {attempt}/{retries}] {out.name}: {exc}")
            await asyncio.sleep(2.0 * attempt)
    raise RuntimeError(f"failed to synth {scene_id}: {last_err}")


async def main(voice: str, rate: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"voice={voice} rate={rate} -> {OUT_DIR}")
    for scene_id, text in NARRATION.items():
        await synth(scene_id, text, voice, rate)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="zh-CN-YunjianNeural")
    ap.add_argument("--rate", default="+8%")
    args = ap.parse_args()
    asyncio.run(main(args.voice, args.rate))
