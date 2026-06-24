"""Generate ENGLISH documentary-style narration MP3s (edge-tts).

Voice: en-US-GuyNeural (mature American documentary male). Output overwrites the
scene-id mp3s in src/assets/audio so the app uses English automatically.
The matching Chinese subtitle text lives in src/App.jsx (subs.zh).

Usage:
  python scripts/gen_audio_en.py                       # default Guy voice
  python scripts/gen_audio_en.py --voice en-US-BrianNeural --rate -4%
"""
import argparse
import asyncio
import sys
from pathlib import Path

import edge_tts

OUT_DIR = Path(__file__).resolve().parents[1] / "src" / "assets" / "audio"

# English narration per scene. MUST stay identical to subs.en[] in src/App.jsx,
# joined with a space — App.jsx uses these exact sentences to time the Chinese
# subtitle, so any wording drift here desyncs the subtitle. en[] is never shown
# on screen (only subs.zh is), so acronyms are spelled for correct pronunciation.
NARRATION = {
    "hook": "In industry and research, AI too often stays trapped behind the screen. It can think, but it struggles to truly act. FactoryLab was built to connect the reasoning of AI to the physical world. It reasons out a new material in the digital world — then makes it, and measures it, in the real one.",
    "overview": "This is FactoryLab's A.I.A.F. operating system. It turns any industrial discovery into a closed loop: observe, understand, simulate and authorize, execute, and learn. Every stage runs on dedicated agents, standardized skills, and real execution units. Where others stop at a diagram, we run the entire loop for real.",
    "capability": "Powering this loop is a complete set of general-purpose engineering capabilities. They give the AI the right information, keep it executing step by step, and let every skill be reused like a tool. With self-checking, full traceability, and rollback at any time — not tied to any single industry. What discovers a material today can move tomorrow into electronics, chemicals, and pharmaceuticals.",
    "material": "The first result from the digital world: a new material. Finding one used to mean months of trial and error. Now agents reason across vast literature and countless formulations, surfacing the most promising candidates. And every conclusion is traceable, reproducible, and fully auditable.",
    "physical": "The candidates chosen in the digital world move immediately into the physical one. A real electrochemical workstation — real wide-temperature impedance measurements, from room temperature to extreme cold. This is where an idea, for the first time, becomes data you can hold in your hands.",
    "mechanism": "In the physical world, we uncovered a new mechanism. In the same system, some materials fail in extreme cold, while others keep conducting smoothly. AI found the reason, and turned it into a yardstick that transfers to other materials. Keeping a material conductive at minus eighty degrees is exactly the kind of hard capability that extreme-cold, extreme-environment applications need most.",
    "closedloop": "Digital and physical now form one closed loop, iterating round after round. The AI proposes a formulation; it is synthesized and measured automatically; the data flows straight back, and the AI optimizes again. Every high-risk action is simulated, then authorized, then executed — fully traceable. Each round makes it smarter — a discovery engine that keeps improving and can be replicated across product lines and materials.",
    "outro": "The proton-conductor project you just saw is only one landing point in FactoryLab's library of capabilities. Behind it lies a single reusable foundation — scaling from a project to an enterprise, a park, and an entire industry. Across the full chain: materials, cells, packs, manufacturing, testing, and recycling. FactoryLab — turning industrial knowledge into capability that can be called, verified, and executed.",
}


async def synth(scene_id: str, text: str, voice: str, rate: str) -> None:
    out = OUT_DIR / f"{scene_id}.mp3"
    last_err = None
    for attempt in range(5):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(str(out))
            size = out.stat().st_size
            if size < 2048:
                raise RuntimeError(f"tiny output ({size} bytes)")
            print(f"  [ok] {out.name}  ({size // 1024} KB)")
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            await asyncio.sleep(1.5 * (attempt + 1))
    print(f"  [FAIL] {scene_id}: {last_err}", file=sys.stderr)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="en-US-AndrewMultilingualNeural")
    ap.add_argument("--rate", default="-3%")
    ap.add_argument("--only", default=None, help="only this scene id")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"voice={args.voice} rate={args.rate} -> {OUT_DIR}")
    items = NARRATION.items() if not args.only else [(args.only, NARRATION[args.only])]
    for scene_id, text in items:
        await synth(scene_id, text, args.voice, args.rate)


if __name__ == "__main__":
    asyncio.run(main())
